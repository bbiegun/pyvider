#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from pyvider.actions.types import DeferralReason
from pyvider.exceptions.base import PyviderError


class Deferral(PyviderError):
    """Raised to indicate that a response should be deferred.

    This exception allows handlers to abort processing and signal Terraform
    that the operation cannot complete yet, avoiding the need to change every
    return type in the provider interface.
    """

    def __init__(self, reason: DeferralReason, message: str = "Response deferred.") -> None:
        self.reason = reason
        super().__init__(message, context={"deferral.reason": reason.name})

    def _default_code(self) -> str:
        return "DEFERRED"


# 🐍🏗️🔚
