#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Assertions on details that full line coverage does not pin down.

Mutation testing surfaced these: every line below was already executed by the
existing suites, but nothing asserted the *value* being produced, so a mutant
could change it and still pass. The cases here are the ones where the value is
part of the contract — error codes surfaced in diagnostics, the identifying
detail in a lock-conflict message, and the attribute name the config reader
looks for.
"""

from __future__ import annotations

from pathlib import Path

from attrs import define
import pytest

from pyvider.state_stores import (
    FileSystemStateStore,
    StateLock,
    StateLockConflictError,
    StateStoreConfigurationError,
    StateStoreError,
    normalize_chunk_size,
)
from pyvider.state_stores._filelock import HAVE_FCNTL, exclusive_file_mutex
from pyvider.state_stores.defaults import DEFAULT_STATE_STORE_CHUNK_SIZE
from pyvider.state_stores.filesystem import _config_root

TYPE_NAME = "hardened_store"


@define
class AttrsStoreConfig:
    """The shape the RPC layer actually produces via cty_to_attrs_instance.

    The existing tests passed dicts, so nothing exercised the getattr branch --
    the one every real ConfigureStateStore call takes.
    """

    path: str | None = None


# --- error codes are part of the diagnostic surface ------------------------


def test_each_state_store_error_reports_its_own_code() -> None:
    assert StateStoreError("x")._default_code() == "STATE_STORE_ERROR"
    assert StateStoreConfigurationError("x")._default_code() == "STATE_STORE_CONFIG_ERROR"

    conflict = StateLockConflictError(StateLock(lock_id="abc", type_name=TYPE_NAME, state_id="main"))
    assert conflict._default_code() == "STATE_LOCK_CONFLICT"


def test_a_lock_conflict_names_everything_needed_to_break_the_lease_by_hand() -> None:
    existing = StateLock(
        lock_id="lock-123",
        type_name="s3",
        state_id="production",
        operation="apply",
        holder="build-box/4242",
    )

    error = StateLockConflictError(existing)

    # Each of these is what turns "state is locked" into an actionable message.
    message = str(error)
    assert "s3/production" in message
    assert "build-box/4242" in message
    assert "apply" in message
    assert "lock-123" in message
    assert error.existing is existing


def test_a_lock_conflict_carries_structured_context() -> None:
    existing = StateLock(lock_id="lock-123", type_name="s3", state_id="production", holder="build-box/4242")

    context = StateLockConflictError(existing).context

    assert context["state_store.type_name"] == "s3"
    assert context["state_store.state_id"] == "production"
    assert context["state_store.lock_id"] == "lock-123"
    assert context["state_store.holder"] == "build-box/4242"


# --- the config reader, on the shape production actually sends -------------


def test_config_root_reads_the_path_attribute_of_an_attrs_config() -> None:
    assert _config_root(AttrsStoreConfig(path="/tmp/state")) == "/tmp/state"


def test_config_root_reads_the_path_key_of_a_dict_config() -> None:
    assert _config_root({"path": "/tmp/state"}) == "/tmp/state"


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(None, id="no-config"),
        pytest.param({}, id="empty-dict"),
        pytest.param({"path": None}, id="null-path"),
        pytest.param({"path": "   "}, id="whitespace-path"),
        pytest.param(AttrsStoreConfig(path=None), id="attrs-null-path"),
        pytest.param(AttrsStoreConfig(path=""), id="attrs-empty-path"),
        pytest.param(object(), id="object-without-a-path-attribute"),
    ],
)
def test_config_root_reports_no_root_when_none_is_usable(config: object) -> None:
    assert _config_root(config) is None


@pytest.mark.asyncio
async def test_configure_accepts_an_attrs_config(tmp_path: Path) -> None:
    store = FileSystemStateStore(root=tmp_path / "original")
    relocated = tmp_path / "relocated"

    await store.configure(AttrsStoreConfig(path=str(relocated)), chunk_size=1024)

    assert store.root == relocated


@pytest.mark.asyncio
async def test_validate_rejects_an_attrs_config_whose_root_is_a_file(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    store = FileSystemStateStore(root=tmp_path / "state")

    errors = await store.validate(AttrsStoreConfig(path=str(blocker)))

    assert len(errors) == 1
    assert str(blocker) in errors[0]


# --- boundaries the happy-path values step straight over -------------------


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        pytest.param(1, 1, id="smallest-usable-size"),
        pytest.param(2, 2, id="just-above-the-boundary"),
        pytest.param(0, DEFAULT_STATE_STORE_CHUNK_SIZE, id="zero-means-unset"),
        pytest.param(-1, DEFAULT_STATE_STORE_CHUNK_SIZE, id="negative-means-unset"),
    ],
)
def test_chunk_size_normalization_at_the_boundary(supplied: int, expected: int) -> None:
    """1 is a legal chunk size; only non-positive values mean "not negotiated".

    Mutation testing caught this: the existing tests used 0, -1 and 17, so
    changing the guard from `> 0` to `> 1` broke nothing. That mutant would
    have silently replaced a client's request for single-byte chunks with the
    32 KiB default.
    """
    assert normalize_chunk_size(supplied) == expected


def test_a_lock_records_an_empty_operation_when_none_is_given() -> None:
    """The operation lands in the lease record a human reads when breaking it."""
    lock = StateLock(lock_id="x", type_name=TYPE_NAME, state_id="main")

    assert lock.operation == ""
    assert lock.to_dict()["operation"] == ""


@pytest.mark.asyncio
async def test_locking_without_an_operation_stores_an_empty_one(tmp_path: Path) -> None:
    store = FileSystemStateStore(root=tmp_path / "state")

    lock = await store.lock_state(TYPE_NAME, "main")

    assert lock.operation == ""
    held = await store.get_lock(TYPE_NAME, "main")
    assert held is not None
    assert held.operation == ""


# --- the mutex timeout message identifies which lock is stuck --------------


@pytest.mark.skipif(not HAVE_FCNTL, reason="POSIX record locks; the sentinel fallback has its own suite")
def test_the_mutex_timeout_message_names_the_contended_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the path, a timeout says only that *something* is locked."""
    import errno
    import fcntl

    def always_busy(fd: int, operation: int) -> None:
        raise OSError(errno.EAGAIN, "resource temporarily unavailable")

    monkeypatch.setattr(fcntl, "lockf", always_busy)
    lock_path = tmp_path / "identifiable.tflock"

    with pytest.raises(TimeoutError) as excinfo:
        with exclusive_file_mutex(lock_path, timeout=0.01):
            pass  # pragma: no cover - the block must not be entered

    assert str(lock_path) in str(excinfo.value)
    assert "0.01" in str(excinfo.value)


# 🐍🏗️🔚
