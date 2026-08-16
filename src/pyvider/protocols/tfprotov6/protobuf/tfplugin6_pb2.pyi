import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StringKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PLAIN: _ClassVar[StringKind]
    MARKDOWN: _ClassVar[StringKind]
PLAIN: StringKind
MARKDOWN: StringKind

class DynamicValue(_message.Message):
    __slots__ = ("msgpack", "json")
    MSGPACK_FIELD_NUMBER: _ClassVar[int]
    JSON_FIELD_NUMBER: _ClassVar[int]
    msgpack: bytes
    json: bytes
    def __init__(self, msgpack: _Optional[bytes] = ..., json: _Optional[bytes] = ...) -> None: ...

class Diagnostic(_message.Message):
    __slots__ = ("severity", "summary", "detail", "attribute")
    class Severity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INVALID: _ClassVar[Diagnostic.Severity]
        ERROR: _ClassVar[Diagnostic.Severity]
        WARNING: _ClassVar[Diagnostic.Severity]
    INVALID: Diagnostic.Severity
    ERROR: Diagnostic.Severity
    WARNING: Diagnostic.Severity
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTE_FIELD_NUMBER: _ClassVar[int]
    severity: Diagnostic.Severity
    summary: str
    detail: str
    attribute: AttributePath
    def __init__(self, severity: _Optional[_Union[Diagnostic.Severity, str]] = ..., summary: _Optional[str] = ..., detail: _Optional[str] = ..., attribute: _Optional[_Union[AttributePath, _Mapping]] = ...) -> None: ...

class FunctionError(_message.Message):
    __slots__ = ("text", "function_argument")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    FUNCTION_ARGUMENT_FIELD_NUMBER: _ClassVar[int]
    text: str
    function_argument: int
    def __init__(self, text: _Optional[str] = ..., function_argument: _Optional[int] = ...) -> None: ...

class AttributePath(_message.Message):
    __slots__ = ("steps",)
    class Step(_message.Message):
        __slots__ = ("attribute_name", "element_key_string", "element_key_int")
        ATTRIBUTE_NAME_FIELD_NUMBER: _ClassVar[int]
        ELEMENT_KEY_STRING_FIELD_NUMBER: _ClassVar[int]
        ELEMENT_KEY_INT_FIELD_NUMBER: _ClassVar[int]
        attribute_name: str
        element_key_string: str
        element_key_int: int
        def __init__(self, attribute_name: _Optional[str] = ..., element_key_string: _Optional[str] = ..., element_key_int: _Optional[int] = ...) -> None: ...
    STEPS_FIELD_NUMBER: _ClassVar[int]
    steps: _containers.RepeatedCompositeFieldContainer[AttributePath.Step]
    def __init__(self, steps: _Optional[_Iterable[_Union[AttributePath.Step, _Mapping]]] = ...) -> None: ...

class StopProvider(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class Response(_message.Message):
        __slots__ = ("Error",)
        ERROR_FIELD_NUMBER: _ClassVar[int]
        Error: str
        def __init__(self, Error: _Optional[str] = ...) -> None: ...
    def __init__(self) -> None: ...

class RawState(_message.Message):
    __slots__ = ("json", "flatmap")
    class FlatmapEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    JSON_FIELD_NUMBER: _ClassVar[int]
    FLATMAP_FIELD_NUMBER: _ClassVar[int]
    json: bytes
    flatmap: _containers.ScalarMap[str, str]
    def __init__(self, json: _Optional[bytes] = ..., flatmap: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ResourceIdentitySchema(_message.Message):
    __slots__ = ("version", "identity_attributes")
    class IdentityAttribute(_message.Message):
        __slots__ = ("name", "type", "required_for_import", "optional_for_import", "description")
        NAME_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        REQUIRED_FOR_IMPORT_FIELD_NUMBER: _ClassVar[int]
        OPTIONAL_FOR_IMPORT_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        name: str
        type: bytes
        required_for_import: bool
        optional_for_import: bool
        description: str
        def __init__(self, name: _Optional[str] = ..., type: _Optional[bytes] = ..., required_for_import: _Optional[bool] = ..., optional_for_import: _Optional[bool] = ..., description: _Optional[str] = ...) -> None: ...
    VERSION_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    version: int
    identity_attributes: _containers.RepeatedCompositeFieldContainer[ResourceIdentitySchema.IdentityAttribute]
    def __init__(self, version: _Optional[int] = ..., identity_attributes: _Optional[_Iterable[_Union[ResourceIdentitySchema.IdentityAttribute, _Mapping]]] = ...) -> None: ...

class ResourceIdentityData(_message.Message):
    __slots__ = ("identity_data",)
    IDENTITY_DATA_FIELD_NUMBER: _ClassVar[int]
    identity_data: DynamicValue
    def __init__(self, identity_data: _Optional[_Union[DynamicValue, _Mapping]] = ...) -> None: ...

class ActionSchema(_message.Message):
    __slots__ = ("schema",)
    SCHEMA_FIELD_NUMBER: _ClassVar[int]
    schema: Schema
    def __init__(self, schema: _Optional[_Union[Schema, _Mapping]] = ...) -> None: ...

class Schema(_message.Message):
    __slots__ = ("version", "block")
    class Block(_message.Message):
        __slots__ = ("version", "attributes", "block_types", "description", "description_kind", "deprecated", "deprecation_message", "computed")
        VERSION_FIELD_NUMBER: _ClassVar[int]
        ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
        BLOCK_TYPES_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_KIND_FIELD_NUMBER: _ClassVar[int]
        DEPRECATED_FIELD_NUMBER: _ClassVar[int]
        DEPRECATION_MESSAGE_FIELD_NUMBER: _ClassVar[int]
        COMPUTED_FIELD_NUMBER: _ClassVar[int]
        version: int
        attributes: _containers.RepeatedCompositeFieldContainer[Schema.Attribute]
        block_types: _containers.RepeatedCompositeFieldContainer[Schema.NestedBlock]
        description: str
        description_kind: StringKind
        deprecated: bool
        deprecation_message: str
        computed: bool
        def __init__(self, version: _Optional[int] = ..., attributes: _Optional[_Iterable[_Union[Schema.Attribute, _Mapping]]] = ..., block_types: _Optional[_Iterable[_Union[Schema.NestedBlock, _Mapping]]] = ..., description: _Optional[str] = ..., description_kind: _Optional[_Union[StringKind, str]] = ..., deprecated: _Optional[bool] = ..., deprecation_message: _Optional[str] = ..., computed: _Optional[bool] = ...) -> None: ...
    class Attribute(_message.Message):
        __slots__ = ("name", "type", "nested_type", "description", "required", "optional", "computed", "sensitive", "description_kind", "deprecated", "write_only", "deprecation_message")
        NAME_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        NESTED_TYPE_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        REQUIRED_FIELD_NUMBER: _ClassVar[int]
        OPTIONAL_FIELD_NUMBER: _ClassVar[int]
        COMPUTED_FIELD_NUMBER: _ClassVar[int]
        SENSITIVE_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_KIND_FIELD_NUMBER: _ClassVar[int]
        DEPRECATED_FIELD_NUMBER: _ClassVar[int]
        WRITE_ONLY_FIELD_NUMBER: _ClassVar[int]
        DEPRECATION_MESSAGE_FIELD_NUMBER: _ClassVar[int]
        name: str
        type: bytes
        nested_type: Schema.Object
        description: str
        required: bool
        optional: bool
        computed: bool
        sensitive: bool
        description_kind: StringKind
        deprecated: bool
        write_only: bool
        deprecation_message: str
        def __init__(self, name: _Optional[str] = ..., type: _Optional[bytes] = ..., nested_type: _Optional[_Union[Schema.Object, _Mapping]] = ..., description: _Optional[str] = ..., required: _Optional[bool] = ..., optional: _Optional[bool] = ..., computed: _Optional[bool] = ..., sensitive: _Optional[bool] = ..., description_kind: _Optional[_Union[StringKind, str]] = ..., deprecated: _Optional[bool] = ..., write_only: _Optional[bool] = ..., deprecation_message: _Optional[str] = ...) -> None: ...
    class NestedBlock(_message.Message):
        __slots__ = ("type_name", "block", "nesting", "min_items", "max_items")
        class NestingMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            INVALID: _ClassVar[Schema.NestedBlock.NestingMode]
            SINGLE: _ClassVar[Schema.NestedBlock.NestingMode]
            LIST: _ClassVar[Schema.NestedBlock.NestingMode]
            SET: _ClassVar[Schema.NestedBlock.NestingMode]
            MAP: _ClassVar[Schema.NestedBlock.NestingMode]
            GROUP: _ClassVar[Schema.NestedBlock.NestingMode]
        INVALID: Schema.NestedBlock.NestingMode
        SINGLE: Schema.NestedBlock.NestingMode
        LIST: Schema.NestedBlock.NestingMode
        SET: Schema.NestedBlock.NestingMode
        MAP: Schema.NestedBlock.NestingMode
        GROUP: Schema.NestedBlock.NestingMode
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        BLOCK_FIELD_NUMBER: _ClassVar[int]
        NESTING_FIELD_NUMBER: _ClassVar[int]
        MIN_ITEMS_FIELD_NUMBER: _ClassVar[int]
        MAX_ITEMS_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        block: Schema.Block
        nesting: Schema.NestedBlock.NestingMode
        min_items: int
        max_items: int
        def __init__(self, type_name: _Optional[str] = ..., block: _Optional[_Union[Schema.Block, _Mapping]] = ..., nesting: _Optional[_Union[Schema.NestedBlock.NestingMode, str]] = ..., min_items: _Optional[int] = ..., max_items: _Optional[int] = ...) -> None: ...
    class Object(_message.Message):
        __slots__ = ("attributes", "nesting", "min_items", "max_items")
        class NestingMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            INVALID: _ClassVar[Schema.Object.NestingMode]
            SINGLE: _ClassVar[Schema.Object.NestingMode]
            LIST: _ClassVar[Schema.Object.NestingMode]
            SET: _ClassVar[Schema.Object.NestingMode]
            MAP: _ClassVar[Schema.Object.NestingMode]
        INVALID: Schema.Object.NestingMode
        SINGLE: Schema.Object.NestingMode
        LIST: Schema.Object.NestingMode
        SET: Schema.Object.NestingMode
        MAP: Schema.Object.NestingMode
        ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
        NESTING_FIELD_NUMBER: _ClassVar[int]
        MIN_ITEMS_FIELD_NUMBER: _ClassVar[int]
        MAX_ITEMS_FIELD_NUMBER: _ClassVar[int]
        attributes: _containers.RepeatedCompositeFieldContainer[Schema.Attribute]
        nesting: Schema.Object.NestingMode
        min_items: int
        max_items: int
        def __init__(self, attributes: _Optional[_Iterable[_Union[Schema.Attribute, _Mapping]]] = ..., nesting: _Optional[_Union[Schema.Object.NestingMode, str]] = ..., min_items: _Optional[int] = ..., max_items: _Optional[int] = ...) -> None: ...
    VERSION_FIELD_NUMBER: _ClassVar[int]
    BLOCK_FIELD_NUMBER: _ClassVar[int]
    version: int
    block: Schema.Block
    def __init__(self, version: _Optional[int] = ..., block: _Optional[_Union[Schema.Block, _Mapping]] = ...) -> None: ...

class Function(_message.Message):
    __slots__ = ("parameters", "variadic_parameter", "summary", "description", "description_kind", "deprecation_message")
    class Parameter(_message.Message):
        __slots__ = ("name", "type", "allow_null_value", "allow_unknown_values", "description", "description_kind")
        NAME_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        ALLOW_NULL_VALUE_FIELD_NUMBER: _ClassVar[int]
        ALLOW_UNKNOWN_VALUES_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_KIND_FIELD_NUMBER: _ClassVar[int]
        name: str
        type: bytes
        allow_null_value: bool
        allow_unknown_values: bool
        description: str
        description_kind: StringKind
        def __init__(self, name: _Optional[str] = ..., type: _Optional[bytes] = ..., allow_null_value: _Optional[bool] = ..., allow_unknown_values: _Optional[bool] = ..., description: _Optional[str] = ..., description_kind: _Optional[_Union[StringKind, str]] = ...) -> None: ...
    class Return(_message.Message):
        __slots__ = ("type",)
        TYPE_FIELD_NUMBER: _ClassVar[int]
        type: bytes
        def __init__(self, type: _Optional[bytes] = ...) -> None: ...
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    VARIADIC_PARAMETER_FIELD_NUMBER: _ClassVar[int]
    RETURN_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_KIND_FIELD_NUMBER: _ClassVar[int]
    DEPRECATION_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    parameters: _containers.RepeatedCompositeFieldContainer[Function.Parameter]
    variadic_parameter: Function.Parameter
    summary: str
    description: str
    description_kind: StringKind
    deprecation_message: str
    def __init__(self, parameters: _Optional[_Iterable[_Union[Function.Parameter, _Mapping]]] = ..., variadic_parameter: _Optional[_Union[Function.Parameter, _Mapping]] = ..., summary: _Optional[str] = ..., description: _Optional[str] = ..., description_kind: _Optional[_Union[StringKind, str]] = ..., deprecation_message: _Optional[str] = ..., **kwargs) -> None: ...

class ServerCapabilities(_message.Message):
    __slots__ = ("plan_destroy", "get_provider_schema_optional", "move_resource_state", "generate_resource_config")
    PLAN_DESTROY_FIELD_NUMBER: _ClassVar[int]
    GET_PROVIDER_SCHEMA_OPTIONAL_FIELD_NUMBER: _ClassVar[int]
    MOVE_RESOURCE_STATE_FIELD_NUMBER: _ClassVar[int]
    GENERATE_RESOURCE_CONFIG_FIELD_NUMBER: _ClassVar[int]
    plan_destroy: bool
    get_provider_schema_optional: bool
    move_resource_state: bool
    generate_resource_config: bool
    def __init__(self, plan_destroy: _Optional[bool] = ..., get_provider_schema_optional: _Optional[bool] = ..., move_resource_state: _Optional[bool] = ..., generate_resource_config: _Optional[bool] = ...) -> None: ...

class ClientCapabilities(_message.Message):
    __slots__ = ("deferral_allowed", "write_only_attributes_allowed", "store_planned_private", "computed_blocks_allowed")
    DEFERRAL_ALLOWED_FIELD_NUMBER: _ClassVar[int]
    WRITE_ONLY_ATTRIBUTES_ALLOWED_FIELD_NUMBER: _ClassVar[int]
    STORE_PLANNED_PRIVATE_FIELD_NUMBER: _ClassVar[int]
    COMPUTED_BLOCKS_ALLOWED_FIELD_NUMBER: _ClassVar[int]
    deferral_allowed: bool
    write_only_attributes_allowed: bool
    store_planned_private: bool
    computed_blocks_allowed: bool
    def __init__(self, deferral_allowed: _Optional[bool] = ..., write_only_attributes_allowed: _Optional[bool] = ..., store_planned_private: _Optional[bool] = ..., computed_blocks_allowed: _Optional[bool] = ...) -> None: ...

class Deferred(_message.Message):
    __slots__ = ("reason",)
    class Reason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNKNOWN: _ClassVar[Deferred.Reason]
        RESOURCE_CONFIG_UNKNOWN: _ClassVar[Deferred.Reason]
        PROVIDER_CONFIG_UNKNOWN: _ClassVar[Deferred.Reason]
        ABSENT_PREREQ: _ClassVar[Deferred.Reason]
    UNKNOWN: Deferred.Reason
    RESOURCE_CONFIG_UNKNOWN: Deferred.Reason
    PROVIDER_CONFIG_UNKNOWN: Deferred.Reason
    ABSENT_PREREQ: Deferred.Reason
    REASON_FIELD_NUMBER: _ClassVar[int]
    reason: Deferred.Reason
    def __init__(self, reason: _Optional[_Union[Deferred.Reason, str]] = ...) -> None: ...

class GetMetadata(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class Response(_message.Message):
        __slots__ = ("server_capabilities", "diagnostics", "data_sources", "resources", "functions", "ephemeral_resources", "list_resources", "state_stores", "actions")
        SERVER_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        DATA_SOURCES_FIELD_NUMBER: _ClassVar[int]
        RESOURCES_FIELD_NUMBER: _ClassVar[int]
        FUNCTIONS_FIELD_NUMBER: _ClassVar[int]
        EPHEMERAL_RESOURCES_FIELD_NUMBER: _ClassVar[int]
        LIST_RESOURCES_FIELD_NUMBER: _ClassVar[int]
        STATE_STORES_FIELD_NUMBER: _ClassVar[int]
        ACTIONS_FIELD_NUMBER: _ClassVar[int]
        server_capabilities: ServerCapabilities
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        data_sources: _containers.RepeatedCompositeFieldContainer[GetMetadata.DataSourceMetadata]
        resources: _containers.RepeatedCompositeFieldContainer[GetMetadata.ResourceMetadata]
        functions: _containers.RepeatedCompositeFieldContainer[GetMetadata.FunctionMetadata]
        ephemeral_resources: _containers.RepeatedCompositeFieldContainer[GetMetadata.EphemeralMetadata]
        list_resources: _containers.RepeatedCompositeFieldContainer[GetMetadata.ListResourceMetadata]
        state_stores: _containers.RepeatedCompositeFieldContainer[GetMetadata.StateStoreMetadata]
        actions: _containers.RepeatedCompositeFieldContainer[GetMetadata.ActionMetadata]
        def __init__(self, server_capabilities: _Optional[_Union[ServerCapabilities, _Mapping]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., data_sources: _Optional[_Iterable[_Union[GetMetadata.DataSourceMetadata, _Mapping]]] = ..., resources: _Optional[_Iterable[_Union[GetMetadata.ResourceMetadata, _Mapping]]] = ..., functions: _Optional[_Iterable[_Union[GetMetadata.FunctionMetadata, _Mapping]]] = ..., ephemeral_resources: _Optional[_Iterable[_Union[GetMetadata.EphemeralMetadata, _Mapping]]] = ..., list_resources: _Optional[_Iterable[_Union[GetMetadata.ListResourceMetadata, _Mapping]]] = ..., state_stores: _Optional[_Iterable[_Union[GetMetadata.StateStoreMetadata, _Mapping]]] = ..., actions: _Optional[_Iterable[_Union[GetMetadata.ActionMetadata, _Mapping]]] = ...) -> None: ...
    class EphemeralMetadata(_message.Message):
        __slots__ = ("type_name",)
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        def __init__(self, type_name: _Optional[str] = ...) -> None: ...
    class FunctionMetadata(_message.Message):
        __slots__ = ("name",)
        NAME_FIELD_NUMBER: _ClassVar[int]
        name: str
        def __init__(self, name: _Optional[str] = ...) -> None: ...
    class DataSourceMetadata(_message.Message):
        __slots__ = ("type_name",)
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        def __init__(self, type_name: _Optional[str] = ...) -> None: ...
    class ResourceMetadata(_message.Message):
        __slots__ = ("type_name",)
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        def __init__(self, type_name: _Optional[str] = ...) -> None: ...
    class ListResourceMetadata(_message.Message):
        __slots__ = ("type_name",)
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        def __init__(self, type_name: _Optional[str] = ...) -> None: ...
    class StateStoreMetadata(_message.Message):
        __slots__ = ("type_name",)
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        def __init__(self, type_name: _Optional[str] = ...) -> None: ...
    class ActionMetadata(_message.Message):
        __slots__ = ("type_name",)
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        def __init__(self, type_name: _Optional[str] = ...) -> None: ...
    def __init__(self) -> None: ...

class GetProviderSchema(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class Response(_message.Message):
        __slots__ = ("provider", "resource_schemas", "data_source_schemas", "functions", "ephemeral_resource_schemas", "list_resource_schemas", "state_store_schemas", "action_schemas", "diagnostics", "provider_meta", "server_capabilities")
        class ResourceSchemasEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: Schema
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Schema, _Mapping]] = ...) -> None: ...
        class DataSourceSchemasEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: Schema
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Schema, _Mapping]] = ...) -> None: ...
        class FunctionsEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: Function
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Function, _Mapping]] = ...) -> None: ...
        class EphemeralResourceSchemasEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: Schema
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Schema, _Mapping]] = ...) -> None: ...
        class ListResourceSchemasEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: Schema
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Schema, _Mapping]] = ...) -> None: ...
        class StateStoreSchemasEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: Schema
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Schema, _Mapping]] = ...) -> None: ...
        class ActionSchemasEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: ActionSchema
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ActionSchema, _Mapping]] = ...) -> None: ...
        PROVIDER_FIELD_NUMBER: _ClassVar[int]
        RESOURCE_SCHEMAS_FIELD_NUMBER: _ClassVar[int]
        DATA_SOURCE_SCHEMAS_FIELD_NUMBER: _ClassVar[int]
        FUNCTIONS_FIELD_NUMBER: _ClassVar[int]
        EPHEMERAL_RESOURCE_SCHEMAS_FIELD_NUMBER: _ClassVar[int]
        LIST_RESOURCE_SCHEMAS_FIELD_NUMBER: _ClassVar[int]
        STATE_STORE_SCHEMAS_FIELD_NUMBER: _ClassVar[int]
        ACTION_SCHEMAS_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        PROVIDER_META_FIELD_NUMBER: _ClassVar[int]
        SERVER_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        provider: Schema
        resource_schemas: _containers.MessageMap[str, Schema]
        data_source_schemas: _containers.MessageMap[str, Schema]
        functions: _containers.MessageMap[str, Function]
        ephemeral_resource_schemas: _containers.MessageMap[str, Schema]
        list_resource_schemas: _containers.MessageMap[str, Schema]
        state_store_schemas: _containers.MessageMap[str, Schema]
        action_schemas: _containers.MessageMap[str, ActionSchema]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        provider_meta: Schema
        server_capabilities: ServerCapabilities
        def __init__(self, provider: _Optional[_Union[Schema, _Mapping]] = ..., resource_schemas: _Optional[_Mapping[str, Schema]] = ..., data_source_schemas: _Optional[_Mapping[str, Schema]] = ..., functions: _Optional[_Mapping[str, Function]] = ..., ephemeral_resource_schemas: _Optional[_Mapping[str, Schema]] = ..., list_resource_schemas: _Optional[_Mapping[str, Schema]] = ..., state_store_schemas: _Optional[_Mapping[str, Schema]] = ..., action_schemas: _Optional[_Mapping[str, ActionSchema]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., provider_meta: _Optional[_Union[Schema, _Mapping]] = ..., server_capabilities: _Optional[_Union[ServerCapabilities, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ValidateProviderConfig(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("config",)
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        config: DynamicValue
        def __init__(self, config: _Optional[_Union[DynamicValue, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class UpgradeResourceState(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "version", "raw_state")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        VERSION_FIELD_NUMBER: _ClassVar[int]
        RAW_STATE_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        version: int
        raw_state: RawState
        def __init__(self, type_name: _Optional[str] = ..., version: _Optional[int] = ..., raw_state: _Optional[_Union[RawState, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("upgraded_state", "diagnostics")
        UPGRADED_STATE_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        upgraded_state: DynamicValue
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, upgraded_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class GetResourceIdentitySchemas(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class Response(_message.Message):
        __slots__ = ("identity_schemas", "diagnostics")
        class IdentitySchemasEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: ResourceIdentitySchema
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ResourceIdentitySchema, _Mapping]] = ...) -> None: ...
        IDENTITY_SCHEMAS_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        identity_schemas: _containers.MessageMap[str, ResourceIdentitySchema]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, identity_schemas: _Optional[_Mapping[str, ResourceIdentitySchema]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class UpgradeResourceIdentity(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "version", "raw_identity")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        VERSION_FIELD_NUMBER: _ClassVar[int]
        RAW_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        version: int
        raw_identity: RawState
        def __init__(self, type_name: _Optional[str] = ..., version: _Optional[int] = ..., raw_identity: _Optional[_Union[RawState, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("upgraded_identity", "diagnostics")
        UPGRADED_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        upgraded_identity: ResourceIdentityData
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, upgraded_identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ValidateResourceConfig(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config", "client_capabilities")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        client_capabilities: ClientCapabilities
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ValidateDataResourceConfig(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ValidateEphemeralResourceConfig(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ConfigureProvider(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("terraform_version", "config", "client_capabilities")
        TERRAFORM_VERSION_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        terraform_version: str
        config: DynamicValue
        client_capabilities: ClientCapabilities
        def __init__(self, terraform_version: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ReadResource(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "current_state", "private", "provider_meta", "client_capabilities", "current_identity")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CURRENT_STATE_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        PROVIDER_META_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        CURRENT_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        current_state: DynamicValue
        private: bytes
        provider_meta: DynamicValue
        client_capabilities: ClientCapabilities
        current_identity: ResourceIdentityData
        def __init__(self, type_name: _Optional[str] = ..., current_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., private: _Optional[bytes] = ..., provider_meta: _Optional[_Union[DynamicValue, _Mapping]] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ..., current_identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("new_state", "diagnostics", "private", "deferred", "new_identity")
        NEW_STATE_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        DEFERRED_FIELD_NUMBER: _ClassVar[int]
        NEW_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        new_state: DynamicValue
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        private: bytes
        deferred: Deferred
        new_identity: ResourceIdentityData
        def __init__(self, new_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., private: _Optional[bytes] = ..., deferred: _Optional[_Union[Deferred, _Mapping]] = ..., new_identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class PlanResourceChange(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "prior_state", "proposed_new_state", "config", "prior_private", "provider_meta", "client_capabilities", "prior_identity", "planned_private")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        PRIOR_STATE_FIELD_NUMBER: _ClassVar[int]
        PROPOSED_NEW_STATE_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        PRIOR_PRIVATE_FIELD_NUMBER: _ClassVar[int]
        PROVIDER_META_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        PRIOR_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        PLANNED_PRIVATE_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        prior_state: DynamicValue
        proposed_new_state: DynamicValue
        config: DynamicValue
        prior_private: bytes
        provider_meta: DynamicValue
        client_capabilities: ClientCapabilities
        prior_identity: ResourceIdentityData
        planned_private: bytes
        def __init__(self, type_name: _Optional[str] = ..., prior_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., proposed_new_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., prior_private: _Optional[bytes] = ..., provider_meta: _Optional[_Union[DynamicValue, _Mapping]] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ..., prior_identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ..., planned_private: _Optional[bytes] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("planned_state", "requires_replace", "planned_private", "diagnostics", "legacy_type_system", "deferred", "planned_identity")
        PLANNED_STATE_FIELD_NUMBER: _ClassVar[int]
        REQUIRES_REPLACE_FIELD_NUMBER: _ClassVar[int]
        PLANNED_PRIVATE_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        LEGACY_TYPE_SYSTEM_FIELD_NUMBER: _ClassVar[int]
        DEFERRED_FIELD_NUMBER: _ClassVar[int]
        PLANNED_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        planned_state: DynamicValue
        requires_replace: _containers.RepeatedCompositeFieldContainer[AttributePath]
        planned_private: bytes
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        legacy_type_system: bool
        deferred: Deferred
        planned_identity: ResourceIdentityData
        def __init__(self, planned_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., requires_replace: _Optional[_Iterable[_Union[AttributePath, _Mapping]]] = ..., planned_private: _Optional[bytes] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., legacy_type_system: _Optional[bool] = ..., deferred: _Optional[_Union[Deferred, _Mapping]] = ..., planned_identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ApplyResourceChange(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "prior_state", "planned_state", "config", "planned_private", "provider_meta", "planned_identity")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        PRIOR_STATE_FIELD_NUMBER: _ClassVar[int]
        PLANNED_STATE_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        PLANNED_PRIVATE_FIELD_NUMBER: _ClassVar[int]
        PROVIDER_META_FIELD_NUMBER: _ClassVar[int]
        PLANNED_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        prior_state: DynamicValue
        planned_state: DynamicValue
        config: DynamicValue
        planned_private: bytes
        provider_meta: DynamicValue
        planned_identity: ResourceIdentityData
        def __init__(self, type_name: _Optional[str] = ..., prior_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., planned_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., planned_private: _Optional[bytes] = ..., provider_meta: _Optional[_Union[DynamicValue, _Mapping]] = ..., planned_identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("new_state", "private", "diagnostics", "legacy_type_system", "new_identity")
        NEW_STATE_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        LEGACY_TYPE_SYSTEM_FIELD_NUMBER: _ClassVar[int]
        NEW_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        new_state: DynamicValue
        private: bytes
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        legacy_type_system: bool
        new_identity: ResourceIdentityData
        def __init__(self, new_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., private: _Optional[bytes] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., legacy_type_system: _Optional[bool] = ..., new_identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ImportResourceState(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "id", "client_capabilities", "identity")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        ID_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        IDENTITY_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        id: str
        client_capabilities: ClientCapabilities
        identity: ResourceIdentityData
        def __init__(self, type_name: _Optional[str] = ..., id: _Optional[str] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ..., identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ...) -> None: ...
    class ImportedResource(_message.Message):
        __slots__ = ("type_name", "state", "private", "identity")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        STATE_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        IDENTITY_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        state: DynamicValue
        private: bytes
        identity: ResourceIdentityData
        def __init__(self, type_name: _Optional[str] = ..., state: _Optional[_Union[DynamicValue, _Mapping]] = ..., private: _Optional[bytes] = ..., identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("imported_resources", "diagnostics", "deferred")
        IMPORTED_RESOURCES_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        DEFERRED_FIELD_NUMBER: _ClassVar[int]
        imported_resources: _containers.RepeatedCompositeFieldContainer[ImportResourceState.ImportedResource]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        deferred: Deferred
        def __init__(self, imported_resources: _Optional[_Iterable[_Union[ImportResourceState.ImportedResource, _Mapping]]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., deferred: _Optional[_Union[Deferred, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class GenerateResourceConfig(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "state")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        STATE_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        state: DynamicValue
        def __init__(self, type_name: _Optional[str] = ..., state: _Optional[_Union[DynamicValue, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("config", "diagnostics")
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        config: DynamicValue
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, config: _Optional[_Union[DynamicValue, _Mapping]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class MoveResourceState(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("source_provider_address", "source_type_name", "source_schema_version", "source_state", "target_type_name", "source_private", "source_identity", "source_identity_schema_version")
        SOURCE_PROVIDER_ADDRESS_FIELD_NUMBER: _ClassVar[int]
        SOURCE_TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        SOURCE_SCHEMA_VERSION_FIELD_NUMBER: _ClassVar[int]
        SOURCE_STATE_FIELD_NUMBER: _ClassVar[int]
        TARGET_TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        SOURCE_PRIVATE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        SOURCE_IDENTITY_SCHEMA_VERSION_FIELD_NUMBER: _ClassVar[int]
        source_provider_address: str
        source_type_name: str
        source_schema_version: int
        source_state: RawState
        target_type_name: str
        source_private: bytes
        source_identity: RawState
        source_identity_schema_version: int
        def __init__(self, source_provider_address: _Optional[str] = ..., source_type_name: _Optional[str] = ..., source_schema_version: _Optional[int] = ..., source_state: _Optional[_Union[RawState, _Mapping]] = ..., target_type_name: _Optional[str] = ..., source_private: _Optional[bytes] = ..., source_identity: _Optional[_Union[RawState, _Mapping]] = ..., source_identity_schema_version: _Optional[int] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("target_state", "diagnostics", "target_private", "target_identity")
        TARGET_STATE_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        TARGET_PRIVATE_FIELD_NUMBER: _ClassVar[int]
        TARGET_IDENTITY_FIELD_NUMBER: _ClassVar[int]
        target_state: DynamicValue
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        target_private: bytes
        target_identity: ResourceIdentityData
        def __init__(self, target_state: _Optional[_Union[DynamicValue, _Mapping]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., target_private: _Optional[bytes] = ..., target_identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ReadDataSource(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config", "provider_meta", "client_capabilities")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        PROVIDER_META_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        provider_meta: DynamicValue
        client_capabilities: ClientCapabilities
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., provider_meta: _Optional[_Union[DynamicValue, _Mapping]] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("state", "diagnostics", "deferred")
        STATE_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        DEFERRED_FIELD_NUMBER: _ClassVar[int]
        state: DynamicValue
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        deferred: Deferred
        def __init__(self, state: _Optional[_Union[DynamicValue, _Mapping]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., deferred: _Optional[_Union[Deferred, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class OpenEphemeralResource(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config", "client_capabilities")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        client_capabilities: ClientCapabilities
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics", "renew_at", "result", "private", "deferred")
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        RENEW_AT_FIELD_NUMBER: _ClassVar[int]
        RESULT_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        DEFERRED_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        renew_at: _timestamp_pb2.Timestamp
        result: DynamicValue
        private: bytes
        deferred: Deferred
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., renew_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., result: _Optional[_Union[DynamicValue, _Mapping]] = ..., private: _Optional[bytes] = ..., deferred: _Optional[_Union[Deferred, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class RenewEphemeralResource(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "private")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        private: bytes
        def __init__(self, type_name: _Optional[str] = ..., private: _Optional[bytes] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics", "renew_at", "private")
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        RENEW_AT_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        renew_at: _timestamp_pb2.Timestamp
        private: bytes
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., renew_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., private: _Optional[bytes] = ...) -> None: ...
    def __init__(self) -> None: ...

class CloseEphemeralResource(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "private")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        private: bytes
        def __init__(self, type_name: _Optional[str] = ..., private: _Optional[bytes] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class GetFunctions(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class Response(_message.Message):
        __slots__ = ("functions", "diagnostics")
        class FunctionsEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: Function
            def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Function, _Mapping]] = ...) -> None: ...
        FUNCTIONS_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        functions: _containers.MessageMap[str, Function]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, functions: _Optional[_Mapping[str, Function]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class CallFunction(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("name", "arguments")
        NAME_FIELD_NUMBER: _ClassVar[int]
        ARGUMENTS_FIELD_NUMBER: _ClassVar[int]
        name: str
        arguments: _containers.RepeatedCompositeFieldContainer[DynamicValue]
        def __init__(self, name: _Optional[str] = ..., arguments: _Optional[_Iterable[_Union[DynamicValue, _Mapping]]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("result", "error")
        RESULT_FIELD_NUMBER: _ClassVar[int]
        ERROR_FIELD_NUMBER: _ClassVar[int]
        result: DynamicValue
        error: FunctionError
        def __init__(self, result: _Optional[_Union[DynamicValue, _Mapping]] = ..., error: _Optional[_Union[FunctionError, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ListResource(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config", "include_resource_object", "limit")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        INCLUDE_RESOURCE_OBJECT_FIELD_NUMBER: _ClassVar[int]
        LIMIT_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        include_resource_object: bool
        limit: int
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., include_resource_object: _Optional[bool] = ..., limit: _Optional[int] = ...) -> None: ...
    class Event(_message.Message):
        __slots__ = ("identity", "display_name", "resource_object", "diagnostic")
        IDENTITY_FIELD_NUMBER: _ClassVar[int]
        DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
        RESOURCE_OBJECT_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTIC_FIELD_NUMBER: _ClassVar[int]
        identity: ResourceIdentityData
        display_name: str
        resource_object: DynamicValue
        diagnostic: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, identity: _Optional[_Union[ResourceIdentityData, _Mapping]] = ..., display_name: _Optional[str] = ..., resource_object: _Optional[_Union[DynamicValue, _Mapping]] = ..., diagnostic: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ValidateListResourceConfig(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config", "include_resource_object", "limit")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        INCLUDE_RESOURCE_OBJECT_FIELD_NUMBER: _ClassVar[int]
        LIMIT_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        include_resource_object: DynamicValue
        limit: DynamicValue
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., include_resource_object: _Optional[_Union[DynamicValue, _Mapping]] = ..., limit: _Optional[_Union[DynamicValue, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ValidateStateStore(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ConfigureStateStore(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config", "capabilities")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        capabilities: StateStoreClientCapabilities
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., capabilities: _Optional[_Union[StateStoreClientCapabilities, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics", "capabilities")
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        capabilities: StateStoreServerCapabilities
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., capabilities: _Optional[_Union[StateStoreServerCapabilities, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class StateStoreClientCapabilities(_message.Message):
    __slots__ = ("chunk_size",)
    CHUNK_SIZE_FIELD_NUMBER: _ClassVar[int]
    chunk_size: int
    def __init__(self, chunk_size: _Optional[int] = ...) -> None: ...

class StateStoreServerCapabilities(_message.Message):
    __slots__ = ("chunk_size",)
    CHUNK_SIZE_FIELD_NUMBER: _ClassVar[int]
    chunk_size: int
    def __init__(self, chunk_size: _Optional[int] = ...) -> None: ...

class ReadStateBytes(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "state_id")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        STATE_ID_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        state_id: str
        def __init__(self, type_name: _Optional[str] = ..., state_id: _Optional[str] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("bytes", "total_length", "range", "diagnostics")
        BYTES_FIELD_NUMBER: _ClassVar[int]
        TOTAL_LENGTH_FIELD_NUMBER: _ClassVar[int]
        RANGE_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        bytes: bytes
        total_length: int
        range: StateRange
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, bytes: _Optional[bytes] = ..., total_length: _Optional[int] = ..., range: _Optional[_Union[StateRange, _Mapping]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class WriteStateBytes(_message.Message):
    __slots__ = ()
    class RequestChunk(_message.Message):
        __slots__ = ("meta", "bytes", "total_length", "range")
        META_FIELD_NUMBER: _ClassVar[int]
        BYTES_FIELD_NUMBER: _ClassVar[int]
        TOTAL_LENGTH_FIELD_NUMBER: _ClassVar[int]
        RANGE_FIELD_NUMBER: _ClassVar[int]
        meta: RequestChunkMeta
        bytes: bytes
        total_length: int
        range: StateRange
        def __init__(self, meta: _Optional[_Union[RequestChunkMeta, _Mapping]] = ..., bytes: _Optional[bytes] = ..., total_length: _Optional[int] = ..., range: _Optional[_Union[StateRange, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class RequestChunkMeta(_message.Message):
    __slots__ = ("type_name", "state_id")
    TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
    STATE_ID_FIELD_NUMBER: _ClassVar[int]
    type_name: str
    state_id: str
    def __init__(self, type_name: _Optional[str] = ..., state_id: _Optional[str] = ...) -> None: ...

class StateRange(_message.Message):
    __slots__ = ("start", "end")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    start: int
    end: int
    def __init__(self, start: _Optional[int] = ..., end: _Optional[int] = ...) -> None: ...

class LockState(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "state_id", "operation")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        STATE_ID_FIELD_NUMBER: _ClassVar[int]
        OPERATION_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        state_id: str
        operation: str
        def __init__(self, type_name: _Optional[str] = ..., state_id: _Optional[str] = ..., operation: _Optional[str] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("lock_id", "diagnostics")
        LOCK_ID_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        lock_id: str
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, lock_id: _Optional[str] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class UnlockState(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "state_id", "lock_id")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        STATE_ID_FIELD_NUMBER: _ClassVar[int]
        LOCK_ID_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        state_id: str
        lock_id: str
        def __init__(self, type_name: _Optional[str] = ..., state_id: _Optional[str] = ..., lock_id: _Optional[str] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class GetStates(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name",)
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        def __init__(self, type_name: _Optional[str] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("state_id", "diagnostics")
        STATE_ID_FIELD_NUMBER: _ClassVar[int]
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        state_id: _containers.RepeatedScalarFieldContainer[str]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, state_id: _Optional[_Iterable[str]] = ..., diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class DeleteState(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "state_id")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        STATE_ID_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        state_id: str
        def __init__(self, type_name: _Optional[str] = ..., state_id: _Optional[str] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class PlanAction(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("action_type", "config", "client_capabilities")
        ACTION_TYPE_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        action_type: str
        config: DynamicValue
        client_capabilities: ClientCapabilities
        def __init__(self, action_type: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics", "deferred")
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        DEFERRED_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        deferred: Deferred
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ..., deferred: _Optional[_Union[Deferred, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class InvokeAction(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("action_type", "config", "client_capabilities")
        ACTION_TYPE_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        CLIENT_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        action_type: str
        config: DynamicValue
        client_capabilities: ClientCapabilities
        def __init__(self, action_type: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ..., client_capabilities: _Optional[_Union[ClientCapabilities, _Mapping]] = ...) -> None: ...
    class Event(_message.Message):
        __slots__ = ("progress", "completed")
        class Progress(_message.Message):
            __slots__ = ("message",)
            MESSAGE_FIELD_NUMBER: _ClassVar[int]
            message: str
            def __init__(self, message: _Optional[str] = ...) -> None: ...
        class Completed(_message.Message):
            __slots__ = ("diagnostics",)
            DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
            diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
            def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
        PROGRESS_FIELD_NUMBER: _ClassVar[int]
        COMPLETED_FIELD_NUMBER: _ClassVar[int]
        progress: InvokeAction.Event.Progress
        completed: InvokeAction.Event.Completed
        def __init__(self, progress: _Optional[_Union[InvokeAction.Event.Progress, _Mapping]] = ..., completed: _Optional[_Union[InvokeAction.Event.Completed, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class ValidateActionConfig(_message.Message):
    __slots__ = ()
    class Request(_message.Message):
        __slots__ = ("type_name", "config")
        TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
        CONFIG_FIELD_NUMBER: _ClassVar[int]
        type_name: str
        config: DynamicValue
        def __init__(self, type_name: _Optional[str] = ..., config: _Optional[_Union[DynamicValue, _Mapping]] = ...) -> None: ...
    class Response(_message.Message):
        __slots__ = ("diagnostics",)
        DIAGNOSTICS_FIELD_NUMBER: _ClassVar[int]
        diagnostics: _containers.RepeatedCompositeFieldContainer[Diagnostic]
        def __init__(self, diagnostics: _Optional[_Iterable[_Union[Diagnostic, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...
