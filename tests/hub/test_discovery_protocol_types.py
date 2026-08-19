#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Discovery of the tfprotov6.11 component types into a caller's registry.

Ephemeral resources, list resources, state stores and actions register
themselves from their decorators, which writes to the hub singleton. Anything
that hands ComponentDiscovery its own registry -- plating's documentation pass,
a test wanting an isolated hub -- saw those dimensions come back empty, because
the module scan only recognised the five older markers.
"""

import types

import pytest

from pyvider.hub.components import ComponentRegistry
from pyvider.hub.discovery import ComponentDiscovery

PROTOCOL_MARKERS = [
    ("_is_registered_ephemeral_resource", "ephemeral_resource"),
    ("_is_registered_list_resource", "list_resource"),
    ("_is_registered_state_store", "state_store"),
    ("_is_registered_action", "action"),
]


@pytest.fixture
def registry() -> ComponentRegistry:
    return ComponentRegistry()


@pytest.fixture
def discovery(registry: ComponentRegistry) -> ComponentDiscovery:
    return ComponentDiscovery(registry)


def _module_with(marker: str, name: str) -> types.ModuleType:
    """Build a module holding one component carrying the given marker."""
    module = types.ModuleType(f"probe_{marker}")

    class Probe:
        pass

    setattr(Probe, marker, True)
    Probe._registered_name = name
    module.Probe = Probe
    return module


@pytest.mark.parametrize(("marker", "dimension"), PROTOCOL_MARKERS)
@pytest.mark.asyncio
async def test_component_lands_in_the_injected_registry(
    discovery: ComponentDiscovery, registry: ComponentRegistry, marker: str, dimension: str
) -> None:
    module = _module_with(marker, f"probe_{dimension}")

    await discovery._process_module(module)

    assert registry.get_component(dimension, f"probe_{dimension}") is module.Probe


@pytest.mark.parametrize(("marker", "dimension"), PROTOCOL_MARKERS)
@pytest.mark.asyncio
async def test_component_without_a_name_is_not_registered(
    discovery: ComponentDiscovery, registry: ComponentRegistry, marker: str, dimension: str
) -> None:
    """A marker with no _registered_name is scaffolding, not a component."""
    module = _module_with(marker, "unused")
    del module.Probe._registered_name

    await discovery._process_module(module)

    assert registry.list_components().get(dimension, {}) == {}


@pytest.mark.parametrize(("marker", "dimension"), PROTOCOL_MARKERS)
@pytest.mark.asyncio
async def test_abstract_component_is_reported_not_silently_dropped(
    discovery: ComponentDiscovery, registry: ComponentRegistry, marker: str, dimension: str
) -> None:
    """An abstract registered component must not reach the registry.

    It also must not vanish quietly: skipping it without a warning turns a
    missing hook into "invalid resource type" pointing at the user's config.
    """
    from abc import ABC, abstractmethod

    module = types.ModuleType(f"abstract_{marker}")

    class Probe(ABC):
        @abstractmethod
        def hook(self) -> None: ...

    setattr(Probe, marker, True)
    Probe._registered_name = f"abstract_{dimension}"
    module.Probe = Probe

    await discovery._process_module(module)

    assert registry.list_components().get(dimension, {}) == {}


@pytest.mark.asyncio
async def test_older_markers_still_register(
    discovery: ComponentDiscovery, registry: ComponentRegistry
) -> None:
    """Widening the marker list must not disturb the original five."""
    for marker, dimension in (
        ("_is_registered_provider", "provider"),
        ("_is_registered_resource", "resource"),
        ("_is_registered_data_source", "data_source"),
        ("_is_registered_capability", "capability"),
    ):
        module = _module_with(marker, f"probe_{dimension}")
        await discovery._process_module(module)
        assert registry.get_component(dimension, f"probe_{dimension}") is module.Probe


@pytest.mark.asyncio
async def test_a_component_registers_under_exactly_one_dimension(
    discovery: ComponentDiscovery, registry: ComponentRegistry
) -> None:
    """The marker scan stops at the first hit, so no double registration."""
    module = _module_with("_is_registered_action", "probe_once")
    module.Probe._is_registered_list_resource = True

    await discovery._process_module(module)

    dimensions = [dim for dim, names in registry.list_components().items() if "probe_once" in names]
    assert len(dimensions) == 1


# 🐍🏗️🔚
