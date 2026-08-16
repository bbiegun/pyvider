#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the identity value codec."""

from pyvider.conversion import marshal_identity, unmarshal_identity
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import a_num, a_str, s_identity

SCHEMA = s_identity(attributes={"region": a_str(required=True), "port": a_num(required=True)})


def test_round_trips_identity_values() -> None:
    data = marshal_identity({"region": "us-east-1", "port": 443}, SCHEMA)

    assert isinstance(data, pb.ResourceIdentityData)
    assert data.identity_data.msgpack

    assert unmarshal_identity(data, SCHEMA) == {"region": "us-east-1", "port": 443}


def test_unmarshal_returns_none_for_none_input() -> None:
    assert unmarshal_identity(None, SCHEMA) is None


def test_unmarshal_returns_none_for_empty_message() -> None:
    """Terraform sends no identity when it has none to send."""
    assert unmarshal_identity(pb.ResourceIdentityData(), SCHEMA) is None


def test_unmarshal_returns_none_for_null_identity() -> None:
    null_data = pb.ResourceIdentityData(identity_data=pb.DynamicValue(msgpack=b"\xc0"))

    assert unmarshal_identity(null_data, SCHEMA) is None


# 🐍🏗️🔚
