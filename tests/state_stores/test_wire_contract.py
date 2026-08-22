#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""What Terraform Core actually requires of the state-store stream.

These rules are read out of Core rather than inferred from the proto comments.
`internal/plugin6/grpc_provider.go` receives the read stream and sends the write
stream; `internal/backend/pluggable/chunks` holds the sizes it will accept.
Getting them wrong does not degrade gracefully -- one of them panics the
Terraform process.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from pyvider.handler import ProviderHandler
from pyvider.protocols.tfprotov6.handlers.state_store_handlers import reset_state_stores
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.state_stores import FileSystemStateStore, state_store_manager
from pyvider.state_stores.defaults import (
    DEFAULT_STATE_STORE_CHUNK_SIZE,
    MAX_STATE_STORE_CHUNK_SIZE,
)
from pyvider.state_stores.manager import normalize_chunk_size

TYPE_NAME = "wire_contract_store"

#: `chunks.DefaultStateStoreChunkSize` -- Core proposes this on Configure.
CORE_DEFAULT_CHUNK_SIZE = 8 << 20
#: `chunks.MaxStateStoreChunkSize` -- above this Core refuses to negotiate.
CORE_MAX_CHUNK_SIZE = 128 << 20


@pytest.fixture(autouse=True)
def _reset_manager() -> Iterator[None]:
    reset_state_stores()
    yield
    reset_state_stores()


@pytest.fixture
def backend(tmp_path: Path) -> FileSystemStateStore:
    store = FileSystemStateStore(root=tmp_path / "state")
    state_store_manager.register_instance(TYPE_NAME, store)
    return store


async def _write(handler: ProviderHandler, state_id: str, payload: bytes) -> None:
    async def chunks() -> AsyncIterator[pb.WriteStateBytes.RequestChunk]:
        # Core's own form: `End: totalBytesProcessed + len(chunk) - 1`.
        yield pb.WriteStateBytes.RequestChunk(
            meta=pb.RequestChunkMeta(type_name=TYPE_NAME, state_id=state_id),
            bytes=payload,
            total_length=len(payload),
            range=pb.StateRange(start=0, end=len(payload) - 1),
        )

    await handler.WriteStateBytes(chunks(), context=None)


async def _read(handler: ProviderHandler, state_id: str) -> list[pb.ReadStateBytes.Response]:
    request = pb.ReadStateBytes.Request(type_name=TYPE_NAME, state_id=state_id)
    return [response async for response in handler.ReadStateBytes(request, context=None)]


class TestChunkSizeNegotiation:
    def test_the_default_is_the_one_core_proposes(self) -> None:
        assert DEFAULT_STATE_STORE_CHUNK_SIZE == CORE_DEFAULT_CHUNK_SIZE

    def test_the_maximum_is_the_one_core_enforces(self) -> None:
        assert MAX_STATE_STORE_CHUNK_SIZE == CORE_MAX_CHUNK_SIZE

    def test_an_oversized_proposal_is_clamped_rather_than_echoed(self) -> None:
        """Core fails configuration on an answer above its own maximum.

        Echoing the proposal back turns a client's mistake into this provider's
        error: "Failed to negotiate acceptable chunk size".
        """
        assert normalize_chunk_size(CORE_MAX_CHUNK_SIZE * 2) == CORE_MAX_CHUNK_SIZE

    @pytest.mark.parametrize("proposed", [0, -1])
    def test_an_absent_proposal_falls_back_to_the_default(self, proposed: int) -> None:
        assert normalize_chunk_size(proposed) == CORE_DEFAULT_CHUNK_SIZE

    def test_a_reasonable_proposal_is_honoured(self) -> None:
        assert normalize_chunk_size(64 * 1024) == 64 * 1024


class TestReadStateBytesRange:
    @pytest.mark.asyncio
    async def test_an_absent_state_still_carries_a_range(self, backend: FileSystemStateStore) -> None:
        """Core dereferences `chunk.Range.End` on every chunk, with no nil check.

        Sending no range makes that a nil `*StateRange` on the other side, and
        the dereference panics the Terraform process -- on the first read of a
        workspace that has no state yet, which is the ordinary case.
        """
        responses = await _read(ProviderHandler(), "never-written")

        assert responses, "an empty state must still produce one response"
        for response in responses:
            assert response.HasField("range")

    @pytest.mark.asyncio
    async def test_the_end_index_is_inclusive(self, backend: FileSystemStateStore) -> None:
        """Core sends `End: start + len(chunk) - 1` and reads it back the same way.

        It decides which chunk is the last one with `Range.End < TotalLength-1`,
        so an exclusive end moves that boundary by a byte.
        """
        handler = ProviderHandler()
        payload = b'{"version": 4, "serial": 1}'
        await _write(handler, "inclusive", payload)

        responses = await _read(handler, "inclusive")

        assert responses
        assert responses[-1].range.end == len(payload) - 1
        for response in responses:
            assert response.range.end - response.range.start + 1 == len(response.bytes)

    @pytest.mark.asyncio
    async def test_chunks_are_contiguous_and_reassemble(self, backend: FileSystemStateStore) -> None:
        handler = ProviderHandler()
        payload = bytes(range(256)) * 64
        await _write(handler, "chunked", payload)
        state_store_manager.set_chunk_size(TYPE_NAME, 4096)

        responses = await _read(handler, "chunked")

        assert b"".join(r.bytes for r in responses) == payload
        assert all(r.total_length == len(payload) for r in responses)

        expected_start = 0
        for response in responses:
            assert response.range.start == expected_start
            expected_start = response.range.end + 1
        assert expected_start == len(payload)

    @pytest.mark.asyncio
    async def test_every_chunk_but_the_last_is_exactly_the_agreed_size(
        self, backend: FileSystemStateStore
    ) -> None:
        """Core warns and names the provider when a middle chunk is short."""
        handler = ProviderHandler()
        chunk_size = 4096
        payload = b"x" * (chunk_size * 2 + 17)
        await _write(handler, "sizes", payload)
        state_store_manager.set_chunk_size(TYPE_NAME, chunk_size)

        responses = await _read(handler, "sizes")

        assert len(responses) == 3
        for response in responses[:-1]:
            assert len(response.bytes) == chunk_size
        assert len(responses[-1].bytes) == 17


class TestChunkBoundaries:
    """The sizes at which an off-by-one in `range.end` actually shows.

    Core classifies a chunk as the last one with `Range.End < TotalLength-1`.
    An exclusive end shifts that test by a byte, and the shift only becomes
    visible when the payload ends exactly one byte past a chunk boundary.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "extra",
        [
            pytest.param(0, id="exactly-two-chunks"),
            pytest.param(1, id="one-byte-past-the-boundary"),
            pytest.param(-1, id="one-byte-short-of-the-boundary"),
        ],
    )
    async def test_the_last_chunk_is_the_one_core_thinks_it_is(
        self, backend: FileSystemStateStore, extra: int
    ) -> None:
        handler = ProviderHandler()
        chunk_size = 1024
        payload = b"z" * (chunk_size * 2 + extra)
        await _write(handler, f"boundary{extra}", payload)
        state_store_manager.set_chunk_size(TYPE_NAME, chunk_size)

        responses = await _read(handler, f"boundary{extra}")

        # Core's own rule, applied to what the provider sent.
        is_last = [r.range.end >= r.total_length - 1 for r in responses]
        assert is_last[-1] is True, "the final chunk must read as final"
        assert not any(is_last[:-1]), "no earlier chunk may read as final"

        # And its size rule for everything before the last.
        for response in responses[:-1]:
            assert len(response.bytes) == chunk_size

        assert b"".join(r.bytes for r in responses) == payload


# 🐍🔌🔚
