#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""A short-lived, cross-process mutex over a single file.

This guards the read-modify-write of a lease record, not the lease itself. The
distinction matters: the lease can outlive the process that took it (that is the
point of an expiry), whereas this mutex is held for microseconds and is released
by the kernel if the holder dies. Building the lease on top of a real kernel
mutex is what makes "check the lease, then claim it" a single atomic step
instead of a race between concurrent providers.

POSIX record locks (``fcntl.lockf``) are used rather than ``flock`` because they
are the variant NFS implements; state directories on a network share are a
normal deployment for remote state.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import time
from typing import IO

from provide.foundation import logger

try:  # pragma: no cover - the fallback path is platform-specific
    import fcntl

    HAVE_FCNTL = True
except ImportError:  # pragma: no cover - Windows and other non-POSIX hosts
    HAVE_FCNTL = False

# How long to wait for the mutex before giving up. The critical section is a
# small read plus a small write, so anything approaching this bound means a peer
# process died mid-section or the filesystem is not honoring locks.
DEFAULT_MUTEX_TIMEOUT_SECONDS = 10.0

# Poll interval for the non-fcntl fallback.
_FALLBACK_POLL_SECONDS = 0.01

# Floor for treating a fallback sentinel as abandoned. Independent of the
# caller's timeout so that a very short timeout cannot reclaim a sentinel a
# live holder only just created.
_MIN_SENTINEL_STALE_SECONDS = 30.0


class FileMutexTimeoutError(TimeoutError):
    """Raised when the cross-process mutex could not be acquired in time."""


@contextmanager
def exclusive_file_mutex(
    path: Path,
    *,
    timeout: float = DEFAULT_MUTEX_TIMEOUT_SECONDS,
    file_mode: int = 0o600,
) -> Iterator[IO[bytes]]:
    """Hold an exclusive cross-process lock on ``path`` for the block's duration.

    Yields the open file handle so the caller can read and rewrite the record
    without reopening it, which would reintroduce the race the mutex closes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Opened r+b-style via os.open so the file is created if absent without
    # truncating an existing lease record.
    fd = os.open(path, os.O_RDWR | os.O_CREAT, file_mode)
    handle: IO[bytes] = os.fdopen(fd, "r+b")
    acquired = False
    try:
        _acquire(handle, path, timeout)
        acquired = True
        yield handle
    finally:
        if acquired:
            _release(handle, path)
        handle.close()


def _acquire(handle: IO[bytes], path: Path, timeout: float) -> None:
    if HAVE_FCNTL:
        _acquire_fcntl(handle, path, timeout)
    else:
        _acquire_sentinel(path, timeout)


def _release(handle: IO[bytes], path: Path) -> None:
    if HAVE_FCNTL:
        fcntl.lockf(handle.fileno(), fcntl.LOCK_UN)
    else:
        _sentinel_path(path).unlink(missing_ok=True)


def _acquire_fcntl(handle: IO[bytes], path: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.lockf(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            if time.monotonic() >= deadline:
                raise FileMutexTimeoutError(
                    f"Timed out after {timeout}s waiting for the state mutex at {path}."
                ) from exc
            time.sleep(_FALLBACK_POLL_SECONDS)


def _sentinel_path(path: Path) -> Path:
    return path.with_name(path.name + ".mutex")


def _sentinel_is_stale(sentinel: Path, timeout: float) -> bool:
    """Report whether a sentinel is old enough that its holder must be gone.

    A POSIX record lock is owned by the kernel and released when the holder
    dies. The sentinel is an ordinary file with no such guarantee, so a process
    killed inside the critical section would otherwise wedge this state
    forever -- defeating the very thing the lease expiry exists to prevent.

    The critical section is a small read plus a small write, so a sentinel
    older than the caller's whole timeout budget cannot belong to a live
    holder that is merely slow.
    """
    try:
        age = time.time() - sentinel.stat().st_mtime
    except OSError:
        # It vanished between the check and the stat: not stale, just gone.
        return False
    return age > max(timeout, _MIN_SENTINEL_STALE_SECONDS)


def _acquire_sentinel(path: Path, timeout: float) -> None:
    sentinel = _sentinel_path(path)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return
        except FileExistsError as exc:
            if _sentinel_is_stale(sentinel, timeout):
                logger.warning(
                    "Reclaiming a stale state mutex sentinel",
                    operation="acquire_file_mutex",
                    path=str(path),
                )
                sentinel.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise FileMutexTimeoutError(
                    f"Timed out after {timeout}s waiting for the state mutex at {path}."
                ) from exc
            time.sleep(_FALLBACK_POLL_SECONDS)


# 🐍🏗️🔚
