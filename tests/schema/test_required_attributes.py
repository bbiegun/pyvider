#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""The required-attribute check, which moved here out of `pyvider.cty`.

cty deliberately accepts a null for any object attribute now, matching go-cty,
so this walk is the only thing standing between a practitioner omitting a
required value and a provider being handed it. The paths matter as much as the
refusals: a diagnostic without a path points Terraform at the whole resource.
"""

from __future__ import annotations

from typing import Any

import pytest

from pyvider.cty import CtyList, CtyNumber, CtyObject, CtyString, CtyValue
from pyvider.cty.exceptions import CtyAttributeValidationError
from pyvider.schema import (
    PvsSchema,
    a_num,
    a_obj,
    a_str,
    b_list,
    b_map,
    b_set,
    b_single,
    s_resource,
)
from pyvider.schema.required import check_required_attributes


def _path_of(error: CtyAttributeValidationError) -> str:
    return error.path.string() if error.path else ""


class TestFlatAttributes:
    def test_a_null_for_a_required_attribute_is_refused(self) -> None:
        schema = s_resource({"name": a_str(required=True)})

        with pytest.raises(CtyAttributeValidationError) as caught:
            schema.validate_config({"name": None})

        assert "Attribute cannot be null" in str(caught.value)
        assert _path_of(caught.value) == "name"

    def test_a_null_for_an_optional_attribute_is_accepted(self) -> None:
        """This is the case Terraform sends constantly."""
        schema = s_resource({"name": a_str(required=True), "note": a_str(optional=True)})

        schema.validate_config({"name": "n", "note": None})

    def test_an_absent_required_attribute_is_left_to_cty(self) -> None:
        """Absent and null are different, and cty answers for absent."""
        schema = s_resource({"name": a_str(required=True)})

        with pytest.raises(CtyAttributeValidationError, match="Missing required attribute"):
            schema.validate_config({})

    def test_a_present_non_null_required_attribute_passes(self) -> None:
        schema = s_resource({"name": a_str(required=True), "size": a_num(optional=True)})

        schema.validate_config({"name": "n", "size": 1})


class TestObjectAttributes:
    """`a_obj` keeps the nested schema, so required-ness survives one level in."""

    def test_a_null_inside_an_object_attribute_is_refused(self) -> None:
        schema = s_resource({"cfg": a_obj(attributes={"retries": a_num(required=True)}, required=True)})

        with pytest.raises(CtyAttributeValidationError) as caught:
            schema.validate_config({"cfg": {"retries": None}})

        assert _path_of(caught.value) == "cfg.retries"

    def test_a_null_object_attribute_does_not_recurse_into_itself(self) -> None:
        schema = s_resource({"cfg": a_obj(attributes={"retries": a_num(required=True)}, optional=True)})

        schema.validate_config({"cfg": None})


class TestNestedBlocks:
    def test_a_list_block_reports_the_element_index(self) -> None:
        schema = s_resource(block_types=[b_list("rule", attributes={"port": a_num(required=True)})])

        with pytest.raises(CtyAttributeValidationError) as caught:
            schema.validate_config({"rule": [{"port": 80}, {"port": None}]})

        assert _path_of(caught.value) == "rule[1].port"

    def test_a_map_block_reports_the_element_key(self) -> None:
        schema = s_resource(block_types=[b_map("svc", attributes={"image": a_str(required=True)})])

        with pytest.raises(CtyAttributeValidationError) as caught:
            schema.validate_config({"svc": {"api": {"image": None}}})

        assert _path_of(caught.value) == "svc['api'].image"

    def test_a_single_block_reports_the_block_name(self) -> None:
        schema = s_resource(block_types=[b_single("conn", attributes={"host": a_str(required=True)})])

        with pytest.raises(CtyAttributeValidationError) as caught:
            schema.validate_config({"conn": {"host": None}})

        assert _path_of(caught.value) == "conn.host"

    def test_a_set_block_reports_the_block_without_inventing_a_position(self) -> None:
        """A set element has no index, and the proto path has no step for one."""
        schema = s_resource(block_types=[b_set("tag", attributes={"key": a_str(required=True)})])

        with pytest.raises(CtyAttributeValidationError) as caught:
            schema.validate_config({"tag": [{"key": None}]})

        assert _path_of(caught.value) == "tag.key"

    def test_a_null_block_is_skipped(self) -> None:
        schema = s_resource(block_types=[b_list("rule", attributes={"port": a_num(required=True)})])

        schema.validate_config({"rule": None})

    def test_an_absent_block_is_skipped(self) -> None:
        schema = s_resource(block_types=[b_list("rule", attributes={"port": a_num(required=True)})])

        schema.validate_config({})

    def test_deep_nesting_composes_the_whole_path(self) -> None:
        schema = s_resource(
            block_types=[
                b_list(
                    "env",
                    attributes={"name": a_str()},
                    block_types=[
                        b_map(
                            "svc",
                            attributes={"image": a_str()},
                            block_types=[b_list("vol", attributes={"path": a_str(required=True)})],
                        )
                    ],
                )
            ]
        )
        config = {"env": [{"name": "prod", "svc": {"api": {"vol": [{"path": None}]}}}]}

        with pytest.raises(CtyAttributeValidationError) as caught:
            schema.validate_config(config)

        assert _path_of(caught.value) == "env[0].svc['api'].vol[0].path"


class TestCtyValuePayloads:
    """The one production caller passes an unmarshalled value, not raw Python.

    `validate_ephemeral_resource_config` hands over `config_cty.value`, whose
    attributes are `CtyValue`s -- so a null there is `CtyValue.null`, not `None`,
    and a walk that only knows about `None` would pass everything.
    """

    def test_a_cty_null_is_recognised(self) -> None:
        schema = s_resource({"name": a_str(required=True)})

        with pytest.raises(CtyAttributeValidationError) as caught:
            check_required_attributes(schema.block, {"name": CtyValue.null(CtyString())})

        assert _path_of(caught.value) == "name"

    def test_a_cty_object_payload_is_walked(self) -> None:
        """The payload is built directly rather than through `validate`.

        Routing it through `block.to_cty_type().validate({"rule": [{"port":
        None}]})` reads better and is wrong: a cty that accepts a null for a
        non-optional attribute is exactly the paired change this check exists to
        make safe, so the fixture would only build against an unreleased cty and
        the test would fail on every installed one. What is under test is the
        walk, not cty's constructor, so the shape is assembled here.
        """
        schema = s_resource(block_types=[b_list("rule", attributes={"port": a_num(required=True)})])
        element = CtyValue(
            vtype=CtyObject(attribute_types={"port": CtyNumber()}),
            value={"port": CtyValue.null(CtyNumber())},
        )
        rules = CtyValue(vtype=CtyList(element_type=element.type), value=(element,))
        config = CtyValue(vtype=CtyObject(attribute_types={"rule": rules.type}), value={"rule": rules})

        with pytest.raises(CtyAttributeValidationError) as caught:
            check_required_attributes(schema.block, config)

        assert _path_of(caught.value) == "rule[0].port"


class TestMalformedPayloads:
    """The walk runs before cty validates, so it sees whatever the caller passed."""

    @pytest.mark.parametrize("config", ["not a mapping", 42, None], ids=str)
    def test_a_non_mapping_config_is_left_to_cty(self, config: Any) -> None:
        schema = s_resource({"name": a_str(required=True)})

        check_required_attributes(schema.block, config)

    @pytest.mark.parametrize("payload", ["not a list", 42], ids=str)
    def test_a_list_block_holding_the_wrong_shape_is_left_to_cty(self, payload: Any) -> None:
        schema = s_resource(block_types=[b_list("rule", attributes={"port": a_num(required=True)})])

        check_required_attributes(schema.block, {"rule": payload})

    @pytest.mark.parametrize("payload", ["not a mapping", 42], ids=str)
    def test_a_map_block_holding_the_wrong_shape_is_left_to_cty(self, payload: Any) -> None:
        schema = s_resource(block_types=[b_map("svc", attributes={"image": a_str(required=True)})])

        check_required_attributes(schema.block, {"svc": payload})

    def test_a_set_block_holding_the_wrong_shape_is_left_to_cty(self) -> None:
        schema = s_resource(block_types=[b_set("tag", attributes={"key": a_str(required=True)})])

        check_required_attributes(schema.block, {"tag": "not a set"})


def test_an_explicit_starting_path_is_extended_rather_than_replaced() -> None:
    """Callers below the root can hand in where they are."""
    from pyvider.cty.path import CtyPath

    schema: PvsSchema = s_resource({"name": a_str(required=True)})

    with pytest.raises(CtyAttributeValidationError) as caught:
        check_required_attributes(schema.block, {"name": None}, CtyPath.get_attr("outer"))

    assert _path_of(caught.value) == "outer.name"


# 🐍🏗️🔚
