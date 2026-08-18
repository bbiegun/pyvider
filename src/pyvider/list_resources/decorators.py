#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Registration decorator for list resources."""

from __future__ import annotations

from collections.abc import Callable

from provide.foundation import logger

from pyvider.list_resources.base import BaseListResource


def register_list_resource(
    name: str, resource_type: str | None = None, test_only: bool = False
) -> Callable[[type[BaseListResource]], type[BaseListResource]]:
    """Register a list resource under a Terraform list resource type name.

    ``resource_type`` names the managed resource whose identity and state
    schemas describe the results. It can also be set as a class attribute; the
    decorator argument wins when both are given.
    """

    def decorator(cls: type[BaseListResource]) -> type[BaseListResource]:
        from pyvider.hub import hub

        if not issubclass(cls, BaseListResource):
            raise TypeError(
                f"@register_list_resource('{name}') requires a BaseListResource subclass, got {cls!r}"
            )

        cls._is_registered_list_resource = True  # type: ignore[attr-defined]
        cls._registered_name = name  # type: ignore[attr-defined]
        cls._is_test_only = test_only  # type: ignore[attr-defined]
        if resource_type is not None:
            cls.resource_type = resource_type

        hub.register("list_resource", name, cls)
        logger.debug(
            "Registered list resource",
            name=name,
            resource_type=cls.resource_type,
            test_only=test_only,
        )
        return cls

    return decorator


# 🐍🏗️🔚
