import sys

file_path = "/Users/tim/.gemini/antigravity-cli/brain/c9a016f4-f05b-48f1-aebd-264ae994bcbb/.system_generated/worktrees/subagent-A1-Capability-Engineer-self-5a489aa6/src/pyvider/protocols/tfprotov6/handlers/get_provider_schema.py"

with open(file_path, "r") as f:
    content = f.read()

target = """        response = pb.GetProviderSchema.Response(
            provider=provider_proto_schema,
            resource_schemas=resource_schemas,
            data_source_schemas=data_source_schemas,
            functions=functions,
            ephemeral_resource_schemas=ephemeral_resource_schemas,
            list_resource_schemas=list_resource_schemas,
            state_store_schemas=state_store_schemas,
            action_schemas=action_schemas,
            diagnostics=diagnostics,
        )"""

replacement = """        response = pb.GetProviderSchema.Response(
            provider=provider_proto_schema,
            resource_schemas=resource_schemas,
            data_source_schemas=data_source_schemas,
            functions=functions,
            ephemeral_resource_schemas=ephemeral_resource_schemas,
            list_resource_schemas=list_resource_schemas,
            state_store_schemas=state_store_schemas,
            action_schemas=action_schemas,
            diagnostics=diagnostics,
            server_capabilities=pb.ServerCapabilities(
                plan_destroy=True,
                get_provider_schema_optional=True,
                move_resource_state=True,
                generate_resource_config=True,
            ),
        )"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w") as f:
        f.write(content)
    print("Success")
else:
    print("Target not found")
