#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from collections.abc import Callable

from provide.foundation import logger


def register_ephemeral_resource(name: str, test_only: bool = False) -> Callable[[type], type]:
    """
    Decorator to register an ephemeral resource under the 'ephemeral_resources' component type.

    Args:
        name (str): The unique name of the ephemeral resource to register.
        test_only (bool): Hide the resource unless test mode is on. Matches every
            other registrar; without it, a demo or fixture ephemeral resource can
            only be shipped by exposing it to real users.

    Returns:
        class: The decorated ephemeral resource class.
    """

    def decorator(cls: type) -> type:
        from pyvider.hub import hub

        cls._is_registered_ephemeral_resource = True  # type: ignore[attr-defined]
        cls._registered_name = name  # type: ignore[attr-defined]
        cls._is_test_only = test_only  # type: ignore[attr-defined]
        hub.register("ephemeral_resource", name, cls)
        logger.debug("Registered ephemeral resource", name=name, test_only=test_only)
        return cls

    return decorator


# 🐍🏗️🔚
