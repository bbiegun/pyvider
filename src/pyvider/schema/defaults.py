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
from pyvider.schema.types.attribute import PvsAttribute
from pyvider.schema.types.blocks import PvsNestedBlock
from pyvider.schema.types.enums import NestingMode
from pyvider.schema.types.object import PvsObjectType


def resolves_from_configuration(attribute: PvsAttribute) -> bool:
    """True when a null value for `attribute` means "the practitioner omitted it".

    Only then is there an omission for a default to fill -- and declaring a
    default is the only way to say so. The combinations where a default would
    have to be ignored are refused at schema construction rather than silently
    dropped here: `PvsAttribute` rejects a default on a required attribute
    (Rule 9), on a write-only one (Rule 10) and on a computed-only one (Rule 8),
    so an attribute that carries a default is always one the practitioner could
    have written and left out.
    """
    return attribute.default is not None


# SINGLE and GROUP carry one block directly; every other mode carries a
# collection of them. Both walks below branch on this same distinction.
_SINGLE_BLOCK_NESTINGS = (NestingMode.SINGLE, NestingMode.GROUP)


def _known_config(value: Any) -> CtyValue | None:
    """The configuration to read defaults from, or None when there is none.

    A null value was never written and an unknown one is not yet decided.
    """
    if isinstance(value, CtyValue) and not value.is_null and not value.is_unknown:
        return value
    return None


def _block_members(value: Any) -> Mapping[str, Any] | None:
    """The attribute-name-to-value mapping behind a configured block, or None."""
    config = _known_config(value)
    if config is None or not isinstance(config.value, Mapping):
        return None
    return config.value


def _nested_elements(
    target: Any, config: CtyValue, nested: PvsNestedBlock
) -> list[tuple[Any, Any, Any]] | None:
    """Pair every element of a collection-nested block with the configuration it came from.

    Returns `(key, element, config_element)` triples -- `key` being a map key or
    a list position -- or None when the two cannot be paired, which leaves the
    caller's value untouched. The only place that knows which nesting modes are
    keyed and which are ordered.
    """
    if nested.nesting is NestingMode.MAP:
        if not isinstance(target, Mapping) or not isinstance(config.value, Mapping):
            return None
        return [(key, element, config.value.get(key)) for key, element in target.items()]

    # LIST and SET are both carried as an ordered collection of elements.
    if not isinstance(target, list | tuple) or not isinstance(config.value, tuple):
        return None
    if len(target) != len(config.value):
        # Nothing pairs an element up with its configuration once counts differ.
        return None
    return [(index, element, config.value[index]) for index, element in enumerate(target)]


def resolve_schema_defaults(value: CtyValue | None, block: PvsObjectType) -> CtyValue | None:
    """Return `value` with every null attribute replaced by its schema default.

    The walk is recursive: an attribute declared with `a_obj()` carries its own
    `PvsObjectType`, and the attributes inside it take their defaults exactly as
    top-level ones do -- as do the attributes of nested blocks, to any depth.

    Nulls only: an unknown attribute is one whose value is not yet known, not an
    absent one, and replacing it would plan a value Terraform is about to
    compute. Which attributes are eligible at all is `resolves_from_configuration`.

    The value is returned unchanged when nothing needed resolving, so callers
    can pass anything through this without paying for a rebuild.
    """
    if not isinstance(value, CtyValue):
        return value
    members = _block_members(value)
    if members is None:
        return value

    resolved = dict(members)
    changed = False

    for name, attribute in block.attributes.items():
        current = resolved.get(name)
        replacement = _resolve_attribute(current, attribute)
        if replacement is not current:
            resolved[name] = replacement
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


def _resolve_attribute(value: Any, attribute: PvsAttribute) -> Any:
    """Return one attribute's value with its own default and any object members resolved."""
    if attribute.write_only:
        # A write-only value is never stored, so nothing inside it may be filled
        # in either. The attribute cannot carry a default of its own (Rule 10);
        # this stops the defaults its object members declare.
        return value

    resolved = value
    if resolves_from_configuration(attribute) and _is_null(resolved):
        resolved = attribute.type.validate(attribute.default)

    if attribute.object_type is not None:
        # An object-typed attribute is a block's structure written as a value:
        # its members declare defaults of their own, including a default the
        # object attribute itself just supplied but left partly unfilled.
        resolved = resolve_schema_defaults(resolved, attribute.object_type)

    return resolved


def merge_schema_defaults_into_plan(
    plan: dict[str, Any], config: CtyValue | None, block: PvsObjectType
) -> None:
    """Make `plan` agree with the effective configuration for defaulted attributes, in place.

    Defaults are resolved into the decoded configuration, which is what a
    resource reads at apply time -- so the plan has to carry the same value, or
    apply returns a state Terraform did not plan. Terraform itself knows nothing
    about provider-side defaults: an attribute the practitioner omitted comes
    back in the proposed new state carrying the *prior* value, at the top level,
    inside object-typed attributes, and inside nested blocks alike.

    For an attribute that declares a default the effective configuration
    therefore wins outright, prior state included. Prior state losing here is
    deliberate: an omitted attribute means "whatever the provider considers the
    default", and if the plan kept a stale non-default value while `ctx.config`
    reported the default, the two would disagree and apply would fail the
    refinement check.

    Only attributes that declare a default are touched. Everything else in the
    proposed new state is Terraform's own merge of configuration and prior state
    and is left exactly as it arrived.
    """
    merged = _merge_block_into_plan(plan, config, block)
    if merged is not plan:
        plan.update(merged)


def _merge_block_into_plan(plan_value: Any, config_value: Any, block: PvsObjectType) -> Any:
    """Return one planned block value -- root object included -- with its defaults corrected."""
    members = _block_members(config_value)
    if not isinstance(plan_value, dict) or members is None:
        # An absent or not-yet-known block on either side has nothing to merge.
        return plan_value

    merged = dict(plan_value)

    for name, attribute in block.attributes.items():
        _merge_attribute_default(merged, name, attribute, members.get(name))

    for nested in block.block_types:
        if nested.type_name not in merged:
            continue
        merged[nested.type_name] = _merge_nested_into_plan(
            merged[nested.type_name], members.get(nested.type_name), nested
        )

    return merged


def _merge_attribute_default(
    merged: dict[str, Any], name: str, attribute: PvsAttribute, resolved: Any
) -> None:
    """Correct one planned attribute against the value the configuration resolved."""
    if attribute.write_only:
        # A write-only value is never stored, so nothing inside it may be
        # planned either. The attribute cannot carry a default of its own
        # (Rule 10); this stops the defaults its object members declare.
        return
    # An unknown value is not yet known, not absent: Terraform is about to
    # compute it, and planning the default would contradict that.
    if isinstance(resolved, CtyValue) and resolved.is_unknown:
        return

    if attribute.object_type is not None and not _is_null(resolved):
        # An object-typed attribute is a block written as a value: its members
        # take their defaults the same way, and only they are corrected -- the
        # object as a whole is Terraform's proposal.
        current = merged.get(name)
        if isinstance(current, dict):
            merged[name] = _merge_block_into_plan(current, resolved, attribute.object_type)
        return

    if attribute.default is None:
        return
    if _is_null(resolved):
        # No resolved configuration to follow -- fall back to the declared
        # default, but never over a value the plan already holds.
        if merged.get(name) is None:
            merged[name] = attribute.default
        return
    merged[name] = cty_to_native(resolved) if isinstance(resolved, CtyValue) else resolved


def _merge_nested_into_plan(plan_value: Any, config_value: Any, nested: PvsNestedBlock) -> Any:
    """Correct the defaults in a planned nested block, whatever its nesting mode."""
    config = _known_config(config_value)
    if config is None:
        return plan_value

    if nested.nesting in _SINGLE_BLOCK_NESTINGS:
        return _merge_block_into_plan(plan_value, config, nested.block)

    pairs = _nested_elements(plan_value, config, nested)
    if pairs is None:
        return plan_value
    if nested.nesting is NestingMode.SET and len(pairs) > 1:
        # Set elements have no stable order to pair on -- a default that differs
        # from prior state is itself what reorders them -- so only the
        # unambiguous single-element case is merged.
        return plan_value

    merged = [
        _merge_block_into_plan(element, config_element, nested.block) for _, element, config_element in pairs
    ]
    if nested.nesting is NestingMode.MAP:
        return {key: block for (key, _, _), block in zip(pairs, merged, strict=True)}
    return merged if isinstance(plan_value, list) else tuple(merged)


def _is_null(value: Any) -> bool:
    if isinstance(value, CtyValue):
        return bool(value.is_null)
    return value is None


def _resolve_nested(value: Any, nested: PvsNestedBlock) -> Any:
    """Resolve defaults inside a nested block, whatever its nesting mode."""
    config = _known_config(value)
    if config is None:
        return value

    if nested.nesting in _SINGLE_BLOCK_NESTINGS:
        return resolve_schema_defaults(config, nested.block)

    # Every element is its own block, and here the configuration is what is
    # being walked, so each element pairs with itself.
    pairs = _nested_elements(config.value, config, nested)
    if pairs is None:
        return value

    resolved = [resolve_schema_defaults(element, nested.block) for _, element, _ in pairs]
    if all(new is old for new, (_, old, _) in zip(resolved, pairs, strict=True)):
        return value
    if nested.nesting is NestingMode.MAP:
        return attrs.evolve(
            value, value={key: block for (key, _, _), block in zip(pairs, resolved, strict=True)}
        )
    return attrs.evolve(value, value=tuple(resolved))


# 🐍🏗️🔚
