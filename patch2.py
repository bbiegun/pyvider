import sys

file_path = "/Users/tim/.gemini/antigravity-cli/brain/c9a016f4-f05b-48f1-aebd-264ae994bcbb/.system_generated/worktrees/subagent-A1-Capability-Engineer-self-5a489aa6/tests/tfprotov6/handlers/test_get_provider_schema_computation.py"

with open(file_path, "r") as f:
    content = f.read()

target = """            assert isinstance(response, pb.GetProviderSchema.Response)
            assert isinstance(response.provider, pb.Schema)"""

replacement = """            assert isinstance(response, pb.GetProviderSchema.Response)
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
