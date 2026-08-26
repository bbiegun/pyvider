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
