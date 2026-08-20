#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Actions: provider-defined operations Terraform invokes outside a resource lifecycle."""

from pyvider.actions.base import BaseAction
from pyvider.actions.decorators import register_action
from pyvider.actions.types import (
    ActionContext,
    ActionPlan,
    ActionProgress,
    DeferralReason,
)

__all__ = [
    "ActionContext",
    "ActionPlan",
    "ActionProgress",
    "BaseAction",
    "DeferralReason",
    "register_action",
]

# 🐍🏗️🔚
