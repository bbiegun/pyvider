#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Backend resolution, chunk-size negotiation, and registration."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pyvider.hub import hub
from pyvider.state_stores import (
    BaseStateStore,
    FileSystemStateStore,
    InMemoryStateStore,
    StateStoreConfigurationError,
    StateStoreManager,
    default_backend_name,
    default_lock_ttl_seconds,
    normalize_chunk_size,
    register_state_store,
    state_store_manager,
)
from pyvider.state_stores.defaults import (
    BACKEND_FILESYSTEM,
    BACKEND_MEMORY,
    DEFAULT_LOCK_TTL_SECONDS,
    DEFAULT_STATE_STORE_CHUNK_SIZE,
    ENV_BACKEND,
    ENV_LOCK_TTL,
    ENV_PATH,
)


@pytest.fixture
def manager() -> Iterator[StateStoreManager]:
    instance = StateStoreManager()
    yield instance
    instance.reset()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (ENV_BACKEND, ENV_PATH, ENV_LOCK_TTL):
        monkeypatch.delenv(name, raising=False)


def test_default_backend_is_the_non_durable_one() -> None:
    assert default_backend_name() == BACKEND_MEMORY


def test_setting_a_state_path_implies_the_durable_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_PATH, str(tmp_path))

    assert default_backend_name() == BACKEND_FILESYSTEM


def test_explicit_backend_wins_over_an_implied_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_PATH, str(tmp_path))
    monkeypatch.setenv(ENV_BACKEND, BACKEND_MEMORY)

    assert default_backend_name() == BACKEND_MEMORY


def test_resolve_uses_the_selected_default_backend(
    manager: StateStoreManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_PATH, str(tmp_path))

    assert isinstance(manager.resolve("s3"), FileSystemStateStore)


def test_resolve_returns_the_same_instance_for_a_type(manager: StateStoreManager) -> None:
    assert manager.resolve("s3") is manager.resolve("s3")


def test_resolve_isolates_distinct_types(manager: StateStoreManager) -> None:
    assert manager.resolve("s3") is not manager.resolve("gcs")


def test_unknown_backend_name_is_rejected(manager: StateStoreManager, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_BACKEND, "carrier-pigeon")

    with pytest.raises(StateStoreConfigurationError, match="carrier-pigeon"):
        manager.resolve("s3")


def test_registered_backend_takes_precedence_over_the_default(manager: StateStoreManager) -> None:
    class RegisteredStore(InMemoryStateStore):
        pass

    hub.register("state_store", "custom_store", RegisteredStore)
    try:
        assert isinstance(manager.resolve("custom_store"), RegisteredStore)
    finally:
        hub.unregister("state_store", "custom_store")


def test_registered_non_backend_is_rejected(manager: StateStoreManager) -> None:
    class NotAStore:
        pass

    hub.register("state_store", "bogus_store", NotAStore)
    try:
        with pytest.raises(StateStoreConfigurationError, match="BaseStateStore"):
            manager.resolve("bogus_store")
    finally:
        hub.unregister("state_store", "bogus_store")


def test_backend_that_cannot_be_constructed_is_reported(manager: StateStoreManager) -> None:
    class ExplodingStore(InMemoryStateStore):
        def __init__(self) -> None:
            raise RuntimeError("no credentials")

    hub.register("state_store", "exploding_store", ExplodingStore)
    try:
        with pytest.raises(StateStoreConfigurationError, match="no credentials"):
            manager.resolve("exploding_store")
    finally:
        hub.unregister("state_store", "exploding_store")


def test_an_explicit_instance_can_be_bound_to_a_type(manager: StateStoreManager) -> None:
    backend = InMemoryStateStore()
    manager.register_instance("s3", backend)

    assert manager.resolve("s3") is backend


def test_default_factory_override_is_used_for_unregistered_types(manager: StateStoreManager) -> None:
    backend = InMemoryStateStore()
    manager.set_default_backend_factory(lambda: backend)

    assert manager.resolve("anything") is backend


def test_chunk_size_defaults_until_negotiated(manager: StateStoreManager) -> None:
    assert manager.chunk_size("s3") == DEFAULT_STATE_STORE_CHUNK_SIZE


def test_chunk_size_is_recorded_per_type(manager: StateStoreManager) -> None:
    assert manager.set_chunk_size("s3", 4096) == 4096

    assert manager.chunk_size("s3") == 4096
    assert manager.chunk_size("gcs") == DEFAULT_STATE_STORE_CHUNK_SIZE


@pytest.mark.parametrize("supplied", [0, -1])
def test_non_positive_chunk_size_falls_back_to_the_default(manager: StateStoreManager, supplied: int) -> None:
    assert manager.set_chunk_size("s3", supplied) == DEFAULT_STATE_STORE_CHUNK_SIZE


def test_normalize_chunk_size_passes_through_positive_values() -> None:
    assert normalize_chunk_size(17) == 17


@pytest.mark.asyncio
async def test_reset_clears_instances_chunk_sizes_and_data(manager: StateStoreManager) -> None:
    backend = manager.resolve("s3")
    assert isinstance(backend, InMemoryStateStore)
    await backend.write_state("s3", "main", b"payload")
    manager.set_chunk_size("s3", 4096)

    manager.reset()

    assert manager.chunk_size("s3") == DEFAULT_STATE_STORE_CHUNK_SIZE
    assert manager.resolve("s3") is not backend
    assert await backend.read_state("s3", "main") is None


def test_describe_reports_resolved_backends(manager: StateStoreManager) -> None:
    manager.resolve("s3")
    manager.set_chunk_size("s3", 2048)

    described = manager.describe()

    assert described["s3"]["backend"] == "InMemoryStateStore"
    assert described["s3"]["durable"] is False
    assert described["s3"]["chunk_size"] == 2048


def test_lock_ttl_defaults_when_unset() -> None:
    assert default_lock_ttl_seconds() == DEFAULT_LOCK_TTL_SECONDS


def test_lock_ttl_honors_the_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_LOCK_TTL, "42.5")

    assert default_lock_ttl_seconds() == 42.5


@pytest.mark.parametrize("value", ["not-a-number", "0", "-5"])
def test_unusable_lock_ttl_override_falls_back(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_LOCK_TTL, value)

    assert default_lock_ttl_seconds() == DEFAULT_LOCK_TTL_SECONDS


def test_register_state_store_decorator_registers_in_the_hub() -> None:
    @register_state_store("decorated_store")
    class DecoratedStore(InMemoryStateStore):
        pass

    try:
        assert hub.get_component("state_store", "decorated_store") is DecoratedStore
        assert DecoratedStore._registered_name == "decorated_store"
        assert DecoratedStore._is_registered_state_store is True
    finally:
        hub.unregister("state_store", "decorated_store")


def test_register_state_store_rejects_a_non_backend() -> None:
    with pytest.raises(TypeError, match="BaseStateStore"):

        @register_state_store("invalid_store")
        class NotAStore:  # type: ignore[misc]
            pass


@pytest.mark.asyncio
async def test_base_class_hooks_default_to_permissive_no_ops() -> None:
    class MinimalStore(InMemoryStateStore):
        pass

    store: BaseStateStore = MinimalStore()

    assert MinimalStore.get_schema() is None
    assert await store.validate({"anything": True}) == []
    assert await BaseStateStore.configure(store, None, 128) is None


def test_module_level_manager_is_a_manager() -> None:
    assert isinstance(state_store_manager, StateStoreManager)


def test_backend_config_class_defaults_to_none() -> None:
    config_class: type[Any] | None = InMemoryStateStore.config_class
    assert config_class is None


# 🐍🏗️🔚
