#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Resolution of `PvsAttribute.default` into a decoded configuration value.

The plugin protocol schema has no default-value field. Terraform sends an
attribute the practitioner omitted as null and never learns what the provider
considers the default, so the provider is the only party that can resolve one --
and it has to do so *before* anything reads the configuration, not only while
planning. A default resolved on the plan alone would leave ``ctx.config``
reporting None, so apply would return a state that does not match the state
Terraform planned.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import attrs

from pyvider.cty import CtyValue
from pyvider.cty.conversion import cty_to_native
from pyvider.schema.types.blocks import PvsNestedBlock
from pyvider.schema.types.enums import NestingMode
from pyvider.schema.types.object import PvsObjectType


def resolve_schema_defaults(value: CtyValue | None, block: PvsObjectType) -> CtyValue | None:
    """Return `value` with every null attribute replaced by its schema default.

    Nulls only: an unknown attribute is one whose value is not yet known, not an
    absent one, and replacing it would plan a value Terraform is about to
    compute. Required attributes are skipped so a default cannot mask a missing
    one, and write-only attributes because they are never stored.

    The value is returned unchanged when nothing needed resolving, so callers
    can pass anything through this without paying for a rebuild.
    """
    if not isinstance(value, CtyValue) or value.is_null or value.is_unknown:
        return value
    if not isinstance(value.value, Mapping):
        return value

    resolved = dict(value.value)
    changed = False

    for name, attribute in block.attributes.items():
        if attribute.default is None or attribute.required or attribute.write_only:
            continue
        if not _is_null(resolved.get(name)):
            continue
        resolved[name] = attribute.type.validate(attribute.default)
        changed = True

    for nested in block.block_types:
        current = resolved.get(nested.type_name)
        replacement = _resolve_nested(current, nested)
        if replacement is not current:
            resolved[nested.type_name] = replacement
            changed = True

    if not changed:
        return value
    return attrs.evolve(value, value=resolved)


def merge_nested_block_defaults(plan: dict[str, Any], config: CtyValue | None, block: PvsObjectType) -> None:
    """Push defaults resolved inside nested blocks into `plan`, in place.

    Defaults are resolved recursively into the decoded configuration, but
    Terraform knows nothing about them: an attribute the practitioner omitted
    inside a block that already exists in prior state comes back in the proposed
    new state carrying the *prior* value. A top-level attribute is corrected by
    `BaseResource._apply_schema_defaults`, but a nested one is not -- the plan
    would keep the stale value while `ctx.config` reports the default, and apply
    would return a state Terraform did not plan.

    Only attributes that declare a default are overridden. Everything else in
    the proposed new state is Terraform's own merge of configuration and prior
    state and is left exactly as it arrived.
    """
    if not isinstance(config, CtyValue) or config.is_null or config.is_unknown:
        return
    if not isinstance(config.value, Mapping):
        return

    for nested in block.block_types:
        if nested.type_name not in plan:
            continue
        plan[nested.type_name] = _merge_nested_into_plan(
            plan[nested.type_name], config.value.get(nested.type_name), nested
        )


def _merge_block_into_plan(plan_value: Any, config_value: Any, block: PvsObjectType) -> Any:
    """Return one planned block value with its defaulted attributes corrected."""
    if not isinstance(plan_value, dict):
        # An absent or not-yet-known block has nothing to merge into.
        return plan_value
    if not isinstance(config_value, CtyValue) or config_value.is_null or config_value.is_unknown:
        return plan_value
    if not isinstance(config_value.value, Mapping):
        return plan_value

    config_values = config_value.value
    merged = dict(plan_value)

    for name, attribute in block.attributes.items():
        if attribute.default is None or attribute.required or attribute.write_only:
            continue
        resolved = config_values.get(name)
        # An unknown value is not yet known, not absent; a null one means the
        # default was never resolved, and inventing it here would go behind
        # `ctx.config`'s back.
        if not isinstance(resolved, CtyValue) or resolved.is_unknown or resolved.is_null:
            continue
        merged[name] = cty_to_native(resolved)

    for deeper in block.block_types:
        if deeper.type_name not in merged:
            continue
        merged[deeper.type_name] = _merge_nested_into_plan(
            merged[deeper.type_name], config_values.get(deeper.type_name), deeper
        )

    return merged


def _merge_nested_into_plan(plan_value: Any, config_value: Any, nested: PvsNestedBlock) -> Any:
    """Correct the defaults in a planned nested block, whatever its nesting mode."""
    if not isinstance(config_value, CtyValue) or config_value.is_null or config_value.is_unknown:
        return plan_value

    if nested.nesting in (NestingMode.SINGLE, NestingMode.GROUP):
        return _merge_block_into_plan(plan_value, config_value, nested.block)

    if nested.nesting is NestingMode.MAP:
        if not isinstance(plan_value, Mapping) or not isinstance(config_value.value, Mapping):
            return plan_value
        return {
            key: _merge_block_into_plan(element, config_value.value.get(key), nested.block)
            for key, element in plan_value.items()
        }

    # LIST and SET are both carried as an ordered collection of elements.
    if not isinstance(plan_value, list | tuple) or not isinstance(config_value.value, tuple):
        return plan_value
    if len(plan_value) != len(config_value.value):
        # Nothing pairs an element up with the configuration it came from once
        # the counts differ, so Terraform's proposal is left alone.
        return plan_value
    if nested.nesting is NestingMode.SET and len(plan_value) > 1:
        # Set elements have no stable order to pair on -- a default that differs
        # from prior state is itself what reorders them -- so only the
        # unambiguous single-element case is merged.
        return plan_value

    merged = [
        _merge_block_into_plan(element, config_element, nested.block)
        for element, config_element in zip(plan_value, config_value.value, strict=True)
    ]
    return merged if isinstance(plan_value, list) else tuple(merged)


def _is_null(value: Any) -> bool:
    if isinstance(value, CtyValue):
        return bool(value.is_null)
    return value is None


def _resolve_nested(value: Any, nested: PvsNestedBlock) -> Any:
    """Resolve defaults inside a nested block, whatever its nesting mode."""
    if not isinstance(value, CtyValue) or value.is_null or value.is_unknown:
        return value

    if nested.nesting in (NestingMode.SINGLE, NestingMode.GROUP):
        return resolve_schema_defaults(value, nested.block)

    if nested.nesting is NestingMode.MAP:
        if not isinstance(value.value, Mapping):
            return value
        mapped = {k: resolve_schema_defaults(v, nested.block) for k, v in value.value.items()}
        if all(mapped[k] is v for k, v in value.value.items()):
            return value
        return attrs.evolve(value, value=mapped)

    # LIST and SET are both carried as a tuple of element values.
    if not isinstance(value.value, tuple):
        return value
    elements = tuple(resolve_schema_defaults(element, nested.block) for element in value.value)
    if all(new is old for new, old in zip(elements, value.value, strict=True)):
        return value
    return attrs.evolve(value, value=elements)


# 🐍🏗️🔚
