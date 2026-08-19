import sys

file_path = "/Users/tim/.gemini/antigravity-cli/brain/c9a016f4-f05b-48f1-aebd-264ae994bcbb/.system_generated/worktrees/subagent-A1-Capability-Engineer-self-5a489aa6/tests/tfprotov6/handlers/test_get_provider_schema_computation.py"

with open(file_path, "r") as f:
    content = f.read()

target = """        with (
            patch("pyvider.hub.hub.get_component") as mock_get_component,
            patch(
                "pyvider.protocols.tfprotov6.handlers.get_provider_schema.pvs_schema_to_proto"
            ) as mock_to_proto,
            patch(
                "pyvider.protocols.tfprotov6.handlers.get_provider_schema._collect_resource_schemas"
            ) as mock_resources,
            patch(
                "pyvider.protocols.tfprotov6.handlers.get_provider_schema._collect_data_source_schemas"
            ) as mock_data_sources,
            patch(
                "pyvider.protocols.tfprotov6.handlers.get_provider_schema._collect_function_schemas"
            ) as mock_functions,
        ):
            mock_get_component.return_value = mock_provider_instance
            mock_to_proto.return_value = pb.Schema()"""

replacement = """        with (
            patch("pyvider.hub.hub.get_component") as mock_get_component,
            patch(
                "pyvider.protocols.tfprotov6.handlers.get_provider_schema.pvs_schema_to_proto"
            ) as mock_to_proto,
            patch(
                "pyvider.protocols.tfprotov6.handlers.get_provider_schema._collect_resource_schemas"
            ) as mock_resources,
            patch(
                "pyvider.protocols.tfprotov6.handlers.get_provider_schema._collect_data_source_schemas"
            ) as mock_data_sources,
            patch(
                "pyvider.protocols.tfprotov6.handlers.get_provider_schema._collect_function_schemas"
            ) as mock_functions,
        ):
            def side_effect(*args, **kwargs):
                if args[1] == "provider":
                    return mock_provider_instance
                return None
            mock_get_component.side_effect = side_effect
            mock_to_proto.return_value = pb.Schema()"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w") as f:
        f.write(content)
    print("Success")
else:
    print("Target not found")
