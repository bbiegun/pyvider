import sys

file_path = "/Users/tim/.gemini/antigravity-cli/brain/c9a016f4-f05b-48f1-aebd-264ae994bcbb/.system_generated/worktrees/subagent-A1-Capability-Engineer-self-5a489aa6/tests/tfprotov6/handlers/test_get_provider_schema.py"

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
            mock_to_proto.return_value = pb.Schema()
            mock_resources.return_value = {}
            mock_data_sources.return_value = {}
            mock_functions.return_value = {}

            response = await _compute_schema_once()

            assert isinstance(response, pb.GetProviderSchema.Response)
            assert isinstance(response.provider, pb.Schema)"""

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
            mock_to_proto.return_value = pb.Schema()
            mock_resources.return_value = {}
            mock_data_sources.return_value = {}
            mock_functions.return_value = {}

            response = await _compute_schema_once()

            assert isinstance(response, pb.GetProviderSchema.Response)
            assert isinstance(response.provider, pb.Schema)
            assert response.server_capabilities.plan_destroy is True
            assert response.server_capabilities.get_provider_schema_optional is True
            assert response.server_capabilities.move_resource_state is True
            assert response.server_capabilities.generate_resource_config is True"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w") as f:
        f.write(content)
    print("Success")
else:
    print("Target not found")
