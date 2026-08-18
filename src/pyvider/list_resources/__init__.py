#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""List resources: provider-defined discovery for Terraform's ListResource RPC."""

from pyvider.list_resources.base import BaseListResource
from pyvider.list_resources.decorators import register_list_resource
from pyvider.list_resources.types import ListResourceContext, ListResult

__all__ = [
    "BaseListResource",
    "ListResourceContext",
    "ListResult",
    "register_list_resource",
]

# 🐍🏗️🔚
