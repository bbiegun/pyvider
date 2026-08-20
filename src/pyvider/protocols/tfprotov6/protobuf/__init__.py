#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Re-exports of the generated tfplugin6 bindings.

Mirrors every top-level message and enum in ``tfplugin6.proto`` so callers import
from this package rather than reaching into the generated modules. Kept in sync
with the proto -- see ``scripts/regen_protobuf.py``.
"""

from google.protobuf.empty_pb2 import Empty

from pyvider.protocols.tfprotov6.protobuf.tfplugin6_pb2 import (
    ActionSchema,
    ApplyResourceChange,
    AttributePath,
    CallFunction,
    ClientCapabilities,
    CloseEphemeralResource,
    ConfigureProvider,
    ConfigureStateStore,
    Deferred,
    DeleteState,
    Diagnostic,
    DynamicValue,
    Function,
    FunctionError,
    GenerateResourceConfig,
    GetFunctions,
    GetMetadata,
    GetProviderSchema,
    GetResourceIdentitySchemas,
    GetStates,
    ImportResourceState,
    InvokeAction,
    ListResource,
    LockState,
    MoveResourceState,
    OpenEphemeralResource,
    PlanAction,
    PlanResourceChange,
    RawState,
    ReadDataSource,
    ReadResource,
    ReadStateBytes,
    RenewEphemeralResource,
    RequestChunkMeta,
    ResourceIdentityData,
    ResourceIdentitySchema,
    Schema,
    ServerCapabilities,
    StateRange,
    StateStoreClientCapabilities,
    StateStoreServerCapabilities,
    StopProvider,
    StringKind,
    UnlockState,
    UpgradeResourceIdentity,
    UpgradeResourceState,
    ValidateActionConfig,
    ValidateDataResourceConfig,
    ValidateEphemeralResourceConfig,
    ValidateListResourceConfig,
    ValidateProviderConfig,
    ValidateResourceConfig,
    ValidateStateStore,
    WriteStateBytes,
)
from pyvider.protocols.tfprotov6.protobuf.tfplugin6_pb2_grpc import (
    ProviderServicer,
    ProviderStub,
    add_ProviderServicer_to_server,
)

__all__ = [
    # Actions (protocol 6.10+)
    "ActionSchema",
    # Planning and state operations
    "ApplyResourceChange",
    # Core protobuf messages
    "AttributePath",
    # Functions
    "CallFunction",
    # Capabilities
    "ClientCapabilities",
    # Ephemeral resource operations
    "CloseEphemeralResource",
    # Provider configuration
    "ConfigureProvider",
    # Pluggable state stores (protocol 6.10+)
    "ConfigureStateStore",
    "Deferred",
    "DeleteState",
    "Diagnostic",
    "DynamicValue",
    "Empty",
    "Function",
    "FunctionError",
    "GenerateResourceConfig",
    "GetFunctions",
    "GetMetadata",
    "GetProviderSchema",
    "GetResourceIdentitySchemas",
    "GetStates",
    "ImportResourceState",
    "InvokeAction",
    # List resources (protocol 6.10+)
    "ListResource",
    "LockState",
    "MoveResourceState",
    "OpenEphemeralResource",
    "PlanAction",
    "PlanResourceChange",
    # gRPC service definitions
    "ProviderServicer",
    "ProviderStub",
    "RawState",
    # Read operations
    "ReadDataSource",
    "ReadResource",
    "ReadStateBytes",
    "RenewEphemeralResource",
    "RequestChunkMeta",
    # Resource identity
    "ResourceIdentityData",
    "ResourceIdentitySchema",
    # Schema and attribute definitions
    "Schema",
    "ServerCapabilities",
    "StateRange",
    "StateStoreClientCapabilities",
    "StateStoreServerCapabilities",
    "StopProvider",
    "StringKind",
    "UnlockState",
    "UpgradeResourceIdentity",
    "UpgradeResourceState",
    "ValidateActionConfig",
    # Validation operations
    "ValidateDataResourceConfig",
    "ValidateEphemeralResourceConfig",
    "ValidateListResourceConfig",
    "ValidateProviderConfig",
    "ValidateResourceConfig",
    "ValidateStateStore",
    "WriteStateBytes",
    "add_ProviderServicer_to_server",
]

# 🐍🏗️🔚
