#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Ephemeral resource registration, including the test-only marker.

Every other registrar -- resources, data sources, functions, actions, list
resources, state stores -- can mark a component test-only, which is what keeps
demo components out of a published provider's schema. Ephemeral resources were
the one exception, so an ephemeral demo component could only be shipped by
putting it in front of real users.
"""

from collections.abc import Iterator

import pytest

from pyvider.ephemerals import register_ephemeral_resource
from pyvider.hub import hub

NAME = "registration_probe_ephemeral"


@pytest.fixture(autouse=True)
def _unregister() -> Iterator[None]:
    yield
    if hub.get_component("ephemeral_resource", NAME):
        hub.unregister("ephemeral_resource", NAME)


def test_registers_under_the_given_name() -> None:
    @register_ephemeral_resource(NAME)
    class Probe:
        pass

    assert hub.get_component("ephemeral_resource", NAME) is Probe


def test_defaults_to_production_visible() -> None:
    """Omitting the flag must not hide a component from real users."""

    @register_ephemeral_resource(NAME)
    class Probe:
        pass

    assert getattr(Probe, "_is_test_only", False) is False


def test_test_only_marks_the_component() -> None:
    """The marker the component filter reads, matching every other registrar."""

    @register_ephemeral_resource(NAME, test_only=True)
    class Probe:
        pass

    assert Probe._is_test_only is True
