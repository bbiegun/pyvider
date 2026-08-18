#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""The required-attribute rule, which belongs to the schema rather than to cty.

`pyvider.cty` used to refuse a null for any object attribute that was not
declared optional. go-cty has no such rule -- nullability is not part of an
object type there -- and Terraform depends on that: everything crossing the
provider protocol is marshalled with `ImpliedType()`, which strips optional
attributes recursively (`configschema/implied_type.go:129`), so the object type
a provider is handed has no optional attributes at all and Terraform sends
nulls for unset ones constantly.

The check has to live here because this is the only layer that knows which
attributes are `required`. A `CtyObject` records *optionality*, which is a
wire-format concern; it does not record intent, and cannot be made to without
adding a third meaning to a flag that already carries two.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pyvider.cty import CtyValue
from pyvider.cty.exceptions import CtyAttributeValidationError
from pyvider.cty.path import CtyPath
from pyvider.schema.types.enums import NestingMode

if TYPE_CHECKING:
    from pyvider.schema.types.attribute import PvsAttribute
    from pyvider.schema.types.blocks import PvsNestedBlock
    from pyvider.schema.types.object import PvsObjectType

ERR_ATTRIBUTE_CANNOT_BE_NULL = "Attribute cannot be null"


def _is_null(value: Any) -> bool:
    """True for a raw `None` and for a cty null alike.

    Both shapes reach this walk. Direct callers pass plain Python, while the
    ephemeral-config handler passes the payload of an unmarshalled `CtyValue`,
    whose attributes are themselves `CtyValue`s.
    """
    if isinstance(value, CtyValue):
        return bool(value.is_null)
    return value is None


def _payload(value: Any) -> Any:
    return value.value if isinstance(value, CtyValue) else value


def check_required_attributes(
    block: PvsObjectType, config: Any, path: CtyPath | None = None, is_state: bool = False
) -> None:
    """Raise if any `required` attribute in the schema tree is present and null.

    Absent is not the same as null and is left alone: cty maps an absent
    attribute onto a null of its type, which is go-cty's documented behaviour,
    and raises for a non-optional one it cannot supply.
    """
    here = path if path is not None else CtyPath.empty()
    mapping = _payload(config)
    if not isinstance(mapping, Mapping):
        return

    for name, attribute in block.attributes.items():
        _check_attribute(name, attribute, mapping, here, is_state)
    for nested in block.block_types:
        _check_block(nested, mapping, here, is_state)


def _check_attribute(
    name: str, attribute: PvsAttribute, mapping: Mapping[str, Any], path: CtyPath, is_state: bool
) -> None:
    if name not in mapping:
        return

    value = mapping[name]
    attribute_path = path.child(name)
    if attribute.required and _is_null(value) and not (is_state and getattr(attribute, "write_only", False)):
        raise CtyAttributeValidationError(ERR_ATTRIBUTE_CANNOT_BE_NULL, value=None, path=attribute_path)

    # `a_obj` keeps the nested schema on the attribute, so required-ness inside
    # an object attribute is still known here. `a_list(a_obj(...))` and friends
    # do not -- the element factories take a CtyType and discard the wrapper --
    # so nesting below a collection attribute is out of reach by construction.
    if attribute.object_type is not None and not _is_null(value):
        check_required_attributes(attribute.object_type, value, attribute_path, is_state)


def _check_block(nested: PvsNestedBlock, mapping: Mapping[str, Any], path: CtyPath, is_state: bool) -> None:
    if nested.type_name not in mapping:
        return

    value = mapping[nested.type_name]
    if _is_null(value):
        return

    block_path = path.child(nested.type_name)
    payload = _payload(value)
    match nested.nesting:
        case NestingMode.LIST:
            _check_indexed(nested, payload, block_path, is_state)
        case NestingMode.MAP:
            _check_keyed(nested, payload, block_path, is_state)
        case NestingMode.SET:
            # Terraform identifies a set element by its value, and there is no
            # proto step for that (`cty_path_to_proto_path` has none either), so
            # an index here would be an invented position. Report the block.
            for element in payload if isinstance(payload, list | tuple | frozenset | set) else ():
                check_required_attributes(nested.block, element, block_path, is_state)
        case _:  # SINGLE, GROUP
            check_required_attributes(nested.block, value, block_path, is_state)


def _check_indexed(nested: PvsNestedBlock, payload: Any, block_path: CtyPath, is_state: bool) -> None:
    if not isinstance(payload, list | tuple):
        return
    for index, element in enumerate(payload):
        check_required_attributes(nested.block, element, block_path.index_step(index), is_state)


def _check_keyed(nested: PvsNestedBlock, payload: Any, block_path: CtyPath, is_state: bool) -> None:
    if not isinstance(payload, Mapping):
        return
    for key, element in payload.items():
        check_required_attributes(nested.block, element, block_path.key_step(key), is_state)


# 🐍🏗️🔚
