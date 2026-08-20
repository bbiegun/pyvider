#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Codec for resource identity values.

Identity data travels over the same msgpack path as state and config, against
the object type implied by the identity schema's attributes.
"""

from typing import Any, cast

from pyvider.conversion.adapter import cty_to_native
from pyvider.conversion.marshaler import marshal, unmarshal
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import PvsSchema


def marshal_identity(values: dict[str, Any], schema: PvsSchema) -> pb.ResourceIdentityData:
    """Encode identity values against the identity schema."""
    return pb.ResourceIdentityData(identity_data=marshal(values, schema=schema.block))


def unmarshal_identity(data: pb.ResourceIdentityData | None, schema: PvsSchema) -> dict[str, Any] | None:
    """Decode inbound identity values.

    Returns None for absent, empty, or null identity so callers do not have to
    distinguish "no identity sent" from "empty identity".
    """
    if data is None or not data.identity_data.msgpack:
        return None

    cty_value = unmarshal(data.identity_data, schema=schema.block)
    if cty_value.is_null:
        return None

    return cast(dict[str, Any], cty_to_native(cty_value))


# 🐍🏗️🔚
