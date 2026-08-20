#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Registration decorator for provider-defined actions."""

from __future__ import annotations

from collections.abc import Callable

from provide.foundation import logger

from pyvider.actions.base import BaseAction


def register_action(name: str, test_only: bool = False) -> Callable[[type[BaseAction]], type[BaseAction]]:
    """Register an action under a Terraform action type name."""

    def decorator(cls: type[BaseAction]) -> type[BaseAction]:
        from pyvider.hub import hub

        if not issubclass(cls, BaseAction):
            raise TypeError(f"@register_action('{name}') requires a BaseAction subclass, got {cls!r}")

        cls._is_registered_action = True  # type: ignore[attr-defined]
        cls._registered_name = name  # type: ignore[attr-defined]
        cls._is_test_only = test_only  # type: ignore[attr-defined]
        hub.register("action", name, cls)
        logger.debug("Registered action", name=name, test_only=test_only)
        return cls

    return decorator


# 🐍🏗️🔚
