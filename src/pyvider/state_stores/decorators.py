#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Registration decorator for provider-supplied state-store backends."""

from __future__ import annotations

from collections.abc import Callable

from provide.foundation import logger

from pyvider.state_stores.base import BaseStateStore


def register_state_store(
    name: str, test_only: bool = False
) -> Callable[[type[BaseStateStore]], type[BaseStateStore]]:
    """Register a state-store backend under a Terraform store type name.

    Registration is eager rather than marker-based (the pattern used by
    ephemeral resources) because a state store must be resolvable the moment
    ``ValidateStateStoreConfig`` arrives, which can precede a full discovery
    sweep.
    """

    def decorator(cls: type[BaseStateStore]) -> type[BaseStateStore]:
        from pyvider.hub import hub

        if not issubclass(cls, BaseStateStore):
            raise TypeError(f"@register_state_store('{name}') requires a BaseStateStore subclass, got {cls!r}")

        cls._is_registered_state_store = True  # type: ignore[attr-defined]
        cls._registered_name = name  # type: ignore[attr-defined]
        cls._is_test_only = test_only  # type: ignore[attr-defined]
        hub.register("state_store", name, cls)
        logger.debug(
            "Registered state store",
            name=name,
            backend=cls.__name__,
            durable=cls.durable,
            test_only=test_only,
        )
        return cls

    return decorator


# 🐍🏗️🔚
