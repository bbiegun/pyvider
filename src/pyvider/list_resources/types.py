#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Values a list resource yields and the context it is given."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from attrs import define, field

ConfigType = TypeVar("ConfigType")


@define(frozen=True, slots=True)
class ListResult:
    """One resource discovered by a list resource.

    ``identity`` is the only required part: Terraform matches a listed instance
    to a managed resource by identity, so a result without one cannot be
    imported or referenced. ``resource_object`` is populated only when the
    caller asked for it, since building a full state object is usually the
    expensive half of listing.
    """

    identity: dict[str, Any]
    display_name: str = ""
    resource_object: Any = None
    warnings: tuple[str, ...] = field(factory=tuple)


@define(frozen=True, slots=True)
class ListResourceContext(Generic[ConfigType]):
    """Everything a list resource needs to answer one ListResource call."""

    type_name: str
    config: ConfigType | None = None
    include_resource_object: bool = False
    #: Terraform's cap on returned results. Zero means "no limit"; the
    #: framework stops the stream at the cap regardless, so an implementation
    #: that ignores it stays correct and merely does extra work.
    limit: int = 0


# 🐍🏗️🔚
