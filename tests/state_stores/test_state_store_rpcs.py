#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""State-store RPCs driven end to end against a durable backend."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from pyvider.conversion import marshal
from pyvider.handler import ProviderHandler
from pyvider.protocols.tfprotov6.handlers.state_store_handlers import (
    ConfigureStateStoreHandler,
    DeleteStateHandler,
    GetStatesHandler,
    LockStateHandler,
    UnlockStateHandler,
    ValidateStateStoreConfigHandler,
    reset_state_stores,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import PvsSchema, a_str, s_provider
from pyvider.state_stores import (
    FileSystemStateStore,
    InMemoryStateStore,
    StateStoreError,
    state_store_manager,
)

TYPE_NAME = "durable_store"


@pytest.fixture(autouse=True)
def _reset_manager() -> Iterator[None]:
    reset_state_stores()
    yield
    reset_state_stores()


@pytest.fixture
def durable_backend(tmp_path: Path) -> FileSystemStateStore:
    backend = FileSystemStateStore(root=tmp_path / "state")
    state_store_manager.register_instance(TYPE_NAME, backend)
    return backend


async def _write(handler: ProviderHandler, state_id: str, payload: bytes) -> pb.WriteStateBytes.Response:
    async def chunks() -> AsyncIterator[pb.WriteStateBytes.RequestChunk]:
        yield pb.WriteStateBytes.RequestChunk(
            meta=pb.RequestChunkMeta(type_name=TYPE_NAME, state_id=state_id),
            bytes=payload,
            total_length=len(payload),
            range=pb.StateRange(start=0, end=len(payload)),
        )

    return await handler.WriteStateBytes(chunks(), context=None)


async def _read(handler: ProviderHandler, state_id: str) -> list[pb.ReadStateBytes.Response]:
    request = pb.ReadStateBytes.Request(type_name=TYPE_NAME, state_id=state_id)
    return [response async for response in handler.ReadStateBytes(request, context=None)]


@pytest.mark.asyncio
async def test_write_then_read_round_trips_through_the_durable_backend(
    durable_backend: FileSystemStateStore,
) -> None:
    handler = ProviderHandler()

    write_response = await _write(handler, "main", b"durable-payload")
    responses = await _read(handler, "main")

    assert list(write_response.diagnostics) == []
    assert b"".join(chunk.bytes for chunk in responses) == b"durable-payload"
    assert await durable_backend.read_state(TYPE_NAME, "main") == b"durable-payload"


@pytest.mark.asyncio
async def test_written_state_is_visible_to_a_fresh_backend_instance(
    durable_backend: FileSystemStateStore,
) -> None:
    handler = ProviderHandler()
    await _write(handler, "main", b"survives")

    restarted = FileSystemStateStore(root=durable_backend.root)

    assert await restarted.read_state(TYPE_NAME, "main") == b"survives"


@pytest.mark.asyncio
async def test_read_is_chunked_at_the_negotiated_size(durable_backend: FileSystemStateStore) -> None:
    handler = ProviderHandler()
    await _write(handler, "main", b"0123456789")

    configure = pb.ConfigureStateStore.Request(type_name=TYPE_NAME)
    configure.capabilities.chunk_size = 4
    await ConfigureStateStoreHandler(configure, context=None)

    responses = await _read(handler, "main")

    assert [chunk.bytes for chunk in responses] == [b"0123", b"4567", b"89"]
    assert {chunk.total_length for chunk in responses} == {10}


@pytest.mark.asyncio
async def test_read_reports_storage_failure_as_a_diagnostic(
    durable_backend: FileSystemStateStore,
) -> None:
    async def explode(type_name: str, state_id: str) -> bytes | None:
        raise StateStoreError("bucket unreachable")

    durable_backend.read_state = explode  # type: ignore[method-assign]
    responses = await _read(ProviderHandler(), "main")

    assert len(responses) == 1
    assert responses[0].diagnostics[0].severity == pb.Diagnostic.ERROR
    assert "bucket unreachable" in responses[0].diagnostics[0].detail


@pytest.mark.asyncio
async def test_write_reports_storage_failure_as_a_diagnostic(
    durable_backend: FileSystemStateStore,
) -> None:
    async def explode(type_name: str, state_id: str, payload: bytes) -> None:
        raise StateStoreError("disk full")

    durable_backend.write_state = explode  # type: ignore[method-assign]
    response = await _write(ProviderHandler(), "main", b"payload")

    assert response.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert "disk full" in response.diagnostics[0].detail


@pytest.mark.asyncio
async def test_lock_then_conflicting_lock_is_refused(durable_backend: FileSystemStateStore) -> None:
    request = pb.LockState.Request(type_name=TYPE_NAME, state_id="main", operation="apply")

    first = await LockStateHandler(request, context=None)
    second = await LockStateHandler(request, context=None)

    assert first.lock_id
    assert list(first.diagnostics) == []
    assert second.lock_id == ""
    assert second.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert second.diagnostics[0].summary == "State is already locked"


@pytest.mark.asyncio
async def test_unlocking_allows_the_next_lock(durable_backend: FileSystemStateStore) -> None:
    lock_request = pb.LockState.Request(type_name=TYPE_NAME, state_id="main", operation="apply")
    first = await LockStateHandler(lock_request, context=None)

    unlock = await UnlockStateHandler(
        pb.UnlockState.Request(type_name=TYPE_NAME, state_id="main", lock_id=first.lock_id),
        context=None,
    )
    second = await LockStateHandler(lock_request, context=None)

    assert list(unlock.diagnostics) == []
    assert second.lock_id
    assert list(second.diagnostics) == []


@pytest.mark.asyncio
async def test_unlock_with_a_lock_id_that_does_not_hold_warns(
    durable_backend: FileSystemStateStore,
) -> None:
    await LockStateHandler(
        pb.LockState.Request(type_name=TYPE_NAME, state_id="main", operation="apply"), context=None
    )

    response = await UnlockStateHandler(
        pb.UnlockState.Request(type_name=TYPE_NAME, state_id="main", lock_id="not-the-holder"),
        context=None,
    )

    # A warning, not an error: releasing a lock you do not hold is a caller
    # mistake, but it leaves the state exactly as it was.
    assert response.diagnostics[0].severity == pb.Diagnostic.WARNING
    assert response.diagnostics[0].summary == "UnlockState lock not held"


@pytest.mark.asyncio
async def test_lock_failure_other_than_conflict_is_reported(
    durable_backend: FileSystemStateStore,
) -> None:
    async def explode(*args: object, **kwargs: object) -> None:
        raise StateStoreError("lock directory unwritable")

    durable_backend.lock_state = explode  # type: ignore[method-assign]
    response = await LockStateHandler(
        pb.LockState.Request(type_name=TYPE_NAME, state_id="main", operation="apply"), context=None
    )

    assert response.lock_id == ""
    assert response.diagnostics[0].summary == "State lock could not be acquired"


@pytest.mark.asyncio
async def test_get_states_and_delete_state_use_the_backend(
    durable_backend: FileSystemStateStore,
) -> None:
    handler = ProviderHandler()
    await _write(handler, "alpha", b"a")
    await _write(handler, "beta", b"b")

    listed = await GetStatesHandler(pb.GetStates.Request(type_name=TYPE_NAME), context=None)
    await DeleteStateHandler(pb.DeleteState.Request(type_name=TYPE_NAME, state_id="alpha"), context=None)
    remaining = await GetStatesHandler(pb.GetStates.Request(type_name=TYPE_NAME), context=None)

    assert set(listed.state_id) == {"alpha", "beta"}
    assert set(remaining.state_id) == {"beta"}


@pytest.mark.asyncio
async def test_delete_failure_is_reported(durable_backend: FileSystemStateStore) -> None:
    async def explode(type_name: str, state_id: str) -> None:
        raise StateStoreError("permission denied")

    durable_backend.delete_state = explode  # type: ignore[method-assign]
    response = await DeleteStateHandler(
        pb.DeleteState.Request(type_name=TYPE_NAME, state_id="main"), context=None
    )

    assert response.diagnostics[0].summary == "State could not be deleted"


@pytest.mark.asyncio
async def test_configure_reports_the_negotiated_chunk_size(
    durable_backend: FileSystemStateStore,
) -> None:
    request = pb.ConfigureStateStore.Request(type_name=TYPE_NAME)
    request.capabilities.chunk_size = 8192

    response = await ConfigureStateStoreHandler(request, context=None)

    assert response.capabilities.chunk_size == 8192
    assert list(response.diagnostics) == []


@pytest.mark.asyncio
async def test_configure_failure_is_reported_with_capabilities_intact(
    durable_backend: FileSystemStateStore,
) -> None:
    async def explode(config: object, chunk_size: int) -> None:
        raise StateStoreError("cannot create root")

    durable_backend.configure = explode  # type: ignore[method-assign]
    request = pb.ConfigureStateStore.Request(type_name=TYPE_NAME)
    request.capabilities.chunk_size = 512

    response = await ConfigureStateStoreHandler(request, context=None)

    assert response.capabilities.chunk_size == 512
    assert response.diagnostics[0].summary == "State store could not be configured"


class _SchemaBackend(InMemoryStateStore):
    """A backend that declares configuration, so the decode path is exercised."""

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_provider(attributes={"bucket": a_str(required=True)})

    async def validate(self, config: object) -> list[str]:
        bucket = config["bucket"].value if config is not None else None  # type: ignore[index]
        if bucket != "allowed":
            return [f"bucket '{bucket}' is not permitted"]
        return []


def _config_for(bucket: str) -> pb.DynamicValue:
    return marshal({"bucket": bucket}, schema=_SchemaBackend.get_schema().block)


@pytest.mark.asyncio
async def test_validate_delegates_to_the_backend_and_accepts() -> None:
    state_store_manager.register_instance(TYPE_NAME, _SchemaBackend())
    request = pb.ValidateStateStore.Request(type_name=TYPE_NAME, config=_config_for("allowed"))

    response = await ValidateStateStoreConfigHandler(request, context=None)

    assert list(response.diagnostics) == []


@pytest.mark.asyncio
async def test_validate_surfaces_backend_errors_as_diagnostics() -> None:
    state_store_manager.register_instance(TYPE_NAME, _SchemaBackend())
    request = pb.ValidateStateStore.Request(type_name=TYPE_NAME, config=_config_for("denied"))

    response = await ValidateStateStoreConfigHandler(request, context=None)

    assert len(response.diagnostics) == 1
    assert response.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert "not permitted" in response.diagnostics[0].summary


@pytest.mark.asyncio
async def test_validate_reports_an_undecodable_config() -> None:
    state_store_manager.register_instance(TYPE_NAME, _SchemaBackend())
    request = pb.ValidateStateStore.Request(type_name=TYPE_NAME)
    request.config.msgpack = b"\xc1not-msgpack"

    response = await ValidateStateStoreConfigHandler(request, context=None)

    assert response.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert response.diagnostics[0].summary == "State store configuration is invalid"


@pytest.mark.asyncio
async def test_validate_passes_none_when_the_backend_declares_no_schema(
    durable_backend: FileSystemStateStore,
) -> None:
    seen: list[object] = []

    async def record(config: object) -> list[str]:
        seen.append(config)
        return []

    durable_backend.validate = record  # type: ignore[method-assign]
    request = pb.ValidateStateStore.Request(type_name=TYPE_NAME)
    request.config.msgpack = b"\x80"

    response = await ValidateStateStoreConfigHandler(request, context=None)

    assert list(response.diagnostics) == []
    assert seen == [None]


# 🐍🏗️🔚
