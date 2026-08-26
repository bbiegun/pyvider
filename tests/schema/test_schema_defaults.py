#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""`resolve_schema_defaults` puts a schema default into the configuration itself.

Resolving a default on the plan alone is not enough. `ctx.config` is what a
resource's own apply hook reads, so a default that never reaches it produces a
final state that does not match the state Terraform planned -- pyvider rejects
that as `ResourceLifecycleContractError`, and Terraform as a provider-produced
inconsistency.
"""

import attrs

from pyvider.cty import CtyBool, CtyString, CtyValue
from pyvider.resources.base import BaseResource
from pyvider.schema import a_bool, a_str, b_list, b_single, resolve_schema_defaults, s_resource

SCHEMA = s_resource(
    attributes={
        "name": a_str(required=True),
        "size": a_str(default="small"),
        "learning": a_bool(default=True),
        "explicit_null": a_str(),
        "secret": a_str(write_only=True, default="hunter2"),
        "mandatory": a_str(required=True, default="ignored"),
    }
)

BLOCK_TYPE = SCHEMA.block.to_cty_type()


def _config(**overrides: object) -> CtyValue:
    values: dict[str, object] = {
        "name": "example",
        "size": CtyValue.null(CtyString()),
        "learning": CtyValue.null(CtyBool()),
        "explicit_null": CtyValue.null(CtyString()),
        "secret": CtyValue.null(CtyString()),
        "mandatory": CtyValue.null(CtyString()),
    }
    values.update(overrides)
    return BLOCK_TYPE.validate(values)


class TestAttributeResolution:
    def test_null_attribute_takes_the_schema_default(self) -> None:
        resolved = resolve_schema_defaults(_config(), SCHEMA.block)

        assert resolved.value["size"].value == "small"
        assert resolved.value["learning"].value is True

    def test_configured_value_is_left_alone(self) -> None:
        resolved = resolve_schema_defaults(_config(size="large"), SCHEMA.block)

        assert resolved.value["size"].value == "large"

    def test_unknown_value_is_left_unknown(self) -> None:
        resolved = resolve_schema_defaults(_config(size=CtyValue.unknown(CtyString())), SCHEMA.block)

        assert resolved.value["size"].is_unknown

    def test_attribute_without_a_default_stays_null(self) -> None:
        resolved = resolve_schema_defaults(_config(), SCHEMA.block)

        assert resolved.value["explicit_null"].is_null

    def test_write_only_attribute_is_not_filled(self) -> None:
        # A write-only value is never stored, so a default would be written into
        # a plan that must show null.
        resolved = resolve_schema_defaults(_config(), SCHEMA.block)

        assert resolved.value["secret"].is_null

    def test_required_attribute_is_not_filled(self) -> None:
        # Otherwise a default would mask a missing required attribute from the
        # required-attribute check that runs over this same value.
        resolved = resolve_schema_defaults(_config(), SCHEMA.block)

        assert resolved.value["mandatory"].is_null

    def test_value_is_returned_unchanged_when_nothing_needs_resolving(self) -> None:
        already = resolve_schema_defaults(_config(), SCHEMA.block)

        assert resolve_schema_defaults(already, SCHEMA.block) is already

    def test_null_and_unknown_configurations_pass_through(self) -> None:
        null_config = CtyValue.null(BLOCK_TYPE)
        unknown_config = CtyValue.unknown(BLOCK_TYPE)

        assert resolve_schema_defaults(null_config, SCHEMA.block) is null_config
        assert resolve_schema_defaults(unknown_config, SCHEMA.block) is unknown_config
        assert resolve_schema_defaults(None, SCHEMA.block) is None


NESTED_SCHEMA = s_resource(
    attributes={"name": a_str(required=True)},
    block_types=[
        b_single("options", attributes={"mode": a_str(default="fast")}),
        b_list("port", attributes={"enabled": a_bool(default=True)}),
    ],
)

NESTED_TYPE = NESTED_SCHEMA.block.to_cty_type()


class TestNestedBlockResolution:
    def test_single_nested_block_gets_its_defaults(self) -> None:
        config = NESTED_TYPE.validate(
            {"name": "n", "options": {"mode": CtyValue.null(CtyString())}, "port": []}
        )

        resolved = resolve_schema_defaults(config, NESTED_SCHEMA.block)

        assert resolved.value["options"].value["mode"].value == "fast"

    def test_every_element_of_a_list_block_gets_its_defaults(self) -> None:
        config = NESTED_TYPE.validate(
            {
                "name": "n",
                "options": CtyValue.null(NESTED_SCHEMA.block.block_types[0].block.to_cty_type()),
                "port": [{"enabled": CtyValue.null(CtyBool())}, {"enabled": False}],
            }
        )

        resolved = resolve_schema_defaults(config, NESTED_SCHEMA.block)

        ports = resolved.value["port"].value
        assert ports[0].value["enabled"].value is True
        assert ports[1].value["enabled"].value is False


@attrs.define
class SwitchConfig:
    """A config class that declares no default of its own.

    This is the shape that made the plan-only fix insufficient: attrs has
    nothing to fall back on, so the default has to already be in the cty value.
    """

    name: str
    learning: bool | None = None


class TestDecodingWithoutAnAttrsDefault:
    def test_default_reaches_a_config_class_that_declares_none(self) -> None:
        resolved = resolve_schema_defaults(_config(), SCHEMA.block)

        config = BaseResource.from_cty(resolved, SwitchConfig)

        assert config is not None
        assert config.learning is True


# 🐍🏗️🔚
