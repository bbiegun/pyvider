#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Test-mode resolution for component filtering.

Terraform asks for the provider schema *before* it calls ConfigureProvider, so
``provider_context`` does not exist yet when the schema is computed — and the
schema is computed exactly once per process. Without an environment fallback,
test-only components can therefore never appear in the schema, no matter what
the provider block says.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers.utils import get_filtered_components

COMPONENT_TYPE = "resource"


class _Production:
    _is_test_only = False


class _TestOnly:
    _is_test_only = True


@pytest.fixture
def registered_components(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Serve a fixed component map without touching the real registry."""
    components = {"prod_thing": _Production, "test_thing": _TestOnly}

    def fake_get_components(component_type: str) -> dict[str, Any]:
        return dict(components) if component_type == COMPONENT_TYPE else {}

    monkeypatch.setattr(hub, "get_components", fake_get_components)
    yield components


@pytest.fixture(autouse=True)
def no_provider_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate the pre-ConfigureProvider window: no provider_context registered."""

    def fake_get_component(dimension: str, name: str) -> Any:
        if name == "provider_context":
            raise KeyError(name)
        return None

    monkeypatch.setattr(hub, "get_component", fake_get_component)


def test_test_only_hidden_without_env(
    registered_components: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no context and no env var, production filtering still applies."""
    monkeypatch.delenv("PYVIDER_TESTMODE", raising=False)

    assert set(get_filtered_components(COMPONENT_TYPE)) == {"prod_thing"}


def test_env_var_reveals_test_only_before_configure(
    registered_components: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """PYVIDER_TESTMODE is honoured when no provider_context exists yet.

    This is the schema-generation path: Terraform requests the schema first, so
    the environment is the only signal available at that point.
    """
    monkeypatch.setenv("PYVIDER_TESTMODE", "true")

    assert set(get_filtered_components(COMPONENT_TYPE)) == {"prod_thing", "test_thing"}


@pytest.mark.parametrize("value", ["false", "0", "no", ""])
def test_falsey_env_values_keep_filtering(
    registered_components: dict[str, Any], monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Only a truthy PYVIDER_TESTMODE unlocks test-only components."""
    monkeypatch.setenv("PYVIDER_TESTMODE", value)

    assert set(get_filtered_components(COMPONENT_TYPE)) == {"prod_thing"}


def test_provider_context_still_wins_when_present(
    registered_components: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registered context enabling test mode works without the env var."""

    class _Context:
        test_mode_enabled = True

    monkeypatch.setattr(hub, "get_component", lambda dimension, name: _Context())
    monkeypatch.delenv("PYVIDER_TESTMODE", raising=False)

    assert set(get_filtered_components(COMPONENT_TYPE)) == {"prod_thing", "test_thing"}
