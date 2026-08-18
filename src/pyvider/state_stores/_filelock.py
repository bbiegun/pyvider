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
    else:  # pragma: no cover - exercised only on non-POSIX hosts
        _acquire_sentinel(path, timeout)


def _release(handle: IO[bytes], path: Path) -> None:
    if HAVE_FCNTL:
        fcntl.lockf(handle.fileno(), fcntl.LOCK_UN)
    else:  # pragma: no cover - exercised only on non-POSIX hosts
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


def _sentinel_path(path: Path) -> Path:  # pragma: no cover - non-POSIX fallback
    return path.with_name(path.name + ".mutex")


def _acquire_sentinel(path: Path, timeout: float) -> None:  # pragma: no cover - non-POSIX fallback
    sentinel = _sentinel_path(path)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise FileMutexTimeoutError(
                    f"Timed out after {timeout}s waiting for the state mutex at {path}."
                ) from exc
            time.sleep(_FALLBACK_POLL_SECONDS)


# 🐍🏗️🔚
