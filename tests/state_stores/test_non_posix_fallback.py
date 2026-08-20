#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""The cross-process mutex on hosts without POSIX record locks.

Windows has no ``fcntl``, so the mutex falls back to an ``O_EXCL`` sentinel
file. That fallback used to be excluded from coverage with a pragma, which
meant the Windows locking path shipped untested. These tests force
``HAVE_FCNTL`` off and exercise it on any platform, so the behaviour is pinned
down here rather than discovered in production on Windows.

The important difference: a POSIX record lock is released by the kernel when
its holder dies, and a sentinel file is not. Without explicit staleness
handling a killed process would wedge the state permanently -- exactly what
the lease expiry exists to prevent.
"""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
import time

import pytest

from pyvider.state_stores import _filelock
from pyvider.state_stores._filelock import (
    FileMutexTimeoutError,
    _sentinel_path,
    exclusive_file_mutex,
)


@pytest.fixture
def without_fcntl(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pretend this host has no fcntl, the way Windows does."""
    monkeypatch.setattr(_filelock, "HAVE_FCNTL", False)
    yield


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    return tmp_path / "state.tflock"


def test_the_fallback_acquires_and_releases(without_fcntl: None, lock_path: Path) -> None:
    with exclusive_file_mutex(lock_path, timeout=1) as handle:
        handle.write(b"lease")
        assert _sentinel_path(lock_path).exists()

    assert not _sentinel_path(lock_path).exists()


def test_the_fallback_can_be_re_acquired_after_release(without_fcntl: None, lock_path: Path) -> None:
    with exclusive_file_mutex(lock_path, timeout=1):
        pass
    with exclusive_file_mutex(lock_path, timeout=1):
        pass


def test_the_fallback_refuses_while_a_live_sentinel_exists(without_fcntl: None, lock_path: Path) -> None:
    sentinel = _sentinel_path(lock_path)
    fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)

    with pytest.raises(FileMutexTimeoutError, match="Timed out"):
        with exclusive_file_mutex(lock_path, timeout=0.05):
            pass  # pragma: no cover - the block must not be entered

    # The live sentinel is left alone: refusing is correct, stealing is not.
    assert sentinel.exists()


def test_a_stale_sentinel_is_reclaimed_rather_than_wedging_the_state(
    without_fcntl: None, lock_path: Path
) -> None:
    """A process killed inside the critical section must not block forever.

    This is the case the fcntl path gets for free from the kernel.
    """
    sentinel = _sentinel_path(lock_path)
    fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    # Backdate it well past the staleness floor, as a crashed holder would be.
    ancient = time.time() - (_filelock._MIN_SENTINEL_STALE_SECONDS + 60)
    os.utime(sentinel, (ancient, ancient))

    with exclusive_file_mutex(lock_path, timeout=0.5) as handle:
        handle.write(b"reclaimed")

    assert lock_path.read_bytes() == b"reclaimed"


def test_a_recently_created_sentinel_is_not_reclaimed_by_a_short_timeout(
    without_fcntl: None, lock_path: Path
) -> None:
    """A tiny timeout must not license stealing a mutex someone just took."""
    sentinel = _sentinel_path(lock_path)
    fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)

    with pytest.raises(FileMutexTimeoutError):
        with exclusive_file_mutex(lock_path, timeout=0.01):
            pass  # pragma: no cover - the block must not be entered

    assert sentinel.exists()


def test_a_sentinel_that_disappears_mid_check_is_not_stale(tmp_path: Path) -> None:
    """Vanished is not the same as abandoned; the next O_EXCL simply wins."""
    assert _filelock._sentinel_is_stale(tmp_path / "never-created.mutex", timeout=1) is False


def test_the_fallback_reports_the_contended_path_on_timeout(without_fcntl: None, lock_path: Path) -> None:
    sentinel = _sentinel_path(lock_path)
    fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)

    with pytest.raises(FileMutexTimeoutError) as excinfo:
        with exclusive_file_mutex(lock_path, timeout=0.01):
            pass  # pragma: no cover - the block must not be entered

    assert str(lock_path) in str(excinfo.value)


# 🐍🏗️🔚
