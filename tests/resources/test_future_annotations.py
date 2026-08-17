#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Conversion under `from __future__ import annotations`.

This module deliberately enables postponed evaluation, so every attrs field type
here is a STRING. That is the idiomatic modern style, and it is the case where a
converter that introspects `field.type` without resolving it sees nothing to
introspect.
"""

from __future__ import annotations

from attrs import define

from pyvider.cty import CtyList, CtyMap, CtyObject, CtyString
from pyvider.resources.base import BaseResource


@define
class Cfg:
    name: str
    targets: list[str] | None = None
    env: dict[str, str] | None = None


def _cfg_value(payload: dict):
    obj = CtyObject(
        {
            "name": CtyString(),
            "targets": CtyList(element_type=CtyString()),
            "env": CtyMap(element_type=CtyString()),
        }
    )
    return obj.validate(payload)


def test_list_elements_are_plain_strings() -> None:
    """A `list[str]` must arrive as strings, not CtyValue wrappers.

    Anything treating an element as a str — `", ".join(targets)` — raises
    "expected str instance, CtyValue found" otherwise.
    """
    out = BaseResource.from_cty(_cfg_value({"name": "caddy", "targets": ["sbc", "appliance"], "env": {}}), Cfg)

    assert out.targets == ["sbc", "appliance"]
    assert all(isinstance(t, str) for t in out.targets)
    assert ", ".join(out.targets) == "sbc, appliance"


def test_map_values_are_plain_strings() -> None:
    out = BaseResource.from_cty(_cfg_value({"name": "caddy", "targets": [], "env": {"A": "1"}}), Cfg)

    assert out.env == {"A": "1"}
    assert all(isinstance(v, str) for v in out.env.values())


def test_scalar_is_plain() -> None:
    out = BaseResource.from_cty(_cfg_value({"name": "caddy", "targets": [], "env": {}}), Cfg)

    assert out.name == "caddy"
    assert isinstance(out.name, str)
