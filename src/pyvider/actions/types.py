#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Values exchanged with an action during planning and invocation."""

from __future__ import annotations

from enum import IntEnum
from typing import Generic, TypeVar

from attrs import define, field

ConfigType = TypeVar("ConfigType")


class DeferralReason(IntEnum):
    """Why Terraform should retry an action later.

    The values mirror ``Deferred.Reason`` in tfplugin6.proto so that a provider
    can express a deferral without importing protobuf types.
    """

    UNKNOWN = 0
    RESOURCE_CONFIG_UNKNOWN = 1
    PROVIDER_CONFIG_UNKNOWN = 2
    ABSENT_PREREQ = 3


@define(frozen=True, slots=True)
class ActionContext(Generic[ConfigType]):
    """What an action is given for one PlanAction or InvokeAction call."""

    action_type: str
    config: ConfigType | None = None
    #: True when Terraform indicated it can handle a deferred response.
    deferral_allowed: bool = False


@define(frozen=True, slots=True)
class ActionPlan:
    """The outcome of planning an action.

    An action that simply intends to run returns the default: no warnings and
    no deferral. Setting ``defer`` tells Terraform the action cannot be planned
    yet, which it can only honor when ``ActionContext.deferral_allowed`` is
    true.
    """

    warnings: tuple[str, ...] = field(factory=tuple)
    defer: DeferralReason | None = None


@define(frozen=True, slots=True)
class ActionProgress:
    """A human-readable progress line emitted while an action runs."""

    message: str


# 🐍🏗️🔚
