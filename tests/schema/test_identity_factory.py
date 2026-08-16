#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the s_identity schema factory."""

import pytest

from pyvider.cty import CtyString
from pyvider.schema import PvsSchema, a_str, s_identity
from pyvider.schema.exceptions import PvsSchemaDefinitionError
from pyvider.schema.types import PvsObjectType


def test_s_identity_builds_a_pvs_schema() -> None:
    schema = s_identity(attributes={"path": a_str(required=True)})

    assert isinstance(schema, PvsSchema)
    assert schema.version == 1
    assert set(schema.block.attributes) == {"path"}
    assert isinstance(schema.block.attributes["path"].type, CtyString)


def test_s_identity_names_attributes_from_the_dict_key() -> None:
    schema = s_identity(attributes={"path": a_str(required=True)})

    assert schema.block.attributes["path"].name == "path"


def test_s_identity_carries_an_explicit_version() -> None:
    schema = s_identity(attributes={"path": a_str(required=True)}, version=3)

    assert schema.version == 3


def test_s_identity_has_no_nested_blocks() -> None:
    schema = s_identity(attributes={"path": a_str(required=True)})

    assert schema.block.block_types == ()


def test_s_identity_rejects_version_below_one() -> None:
    """Identity versions start at 1."""
    with pytest.raises(PvsSchemaDefinitionError, match="version"):
        s_identity(attributes={"path": a_str(required=True)}, version=0)


def test_s_identity_rejects_negative_version() -> None:
    with pytest.raises(PvsSchemaDefinitionError, match="version"):
        s_identity(attributes={"path": a_str(required=True)}, version=-1)


def test_pvs_schema_version_validator_actually_raises() -> None:
    """Regression: the validator used to return a bool, which attrs discards.

    s_identity is the first factory to accept a version argument, so it is the
    first code that can reach a bad value.
    """
    with pytest.raises(PvsSchemaDefinitionError, match="version"):
        PvsSchema(version=0, block=PvsObjectType(attributes={}))


def test_pvs_schema_accepts_version_one() -> None:
    assert PvsSchema(version=1, block=PvsObjectType(attributes={})).version == 1


def test_unflagged_identity_attribute_defaults_to_optional() -> None:
    """Inherited from PvsAttribute.__attrs_post_init__ -- optional_for_import."""
    schema = s_identity(attributes={"region": a_str()})

    assert schema.block.attributes["region"].optional is True
    assert schema.block.attributes["region"].required is False


def test_required_wins_when_both_flags_set() -> None:
    """Also inherited: required and optional together resolves to required."""
    schema = s_identity(attributes={"path": a_str(required=True, optional=True)})

    assert schema.block.attributes["path"].required is True
    assert schema.block.attributes["path"].optional is False


# 🐍🏗️🔚
