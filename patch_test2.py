with open("tests/tfprotov6/handlers/test_deferral.py", "r") as f:
    content = f.read()

content = "import attrs\n" + content

replace_with = """
@attrs.define
class MockState:
    pass

@pytest.fixture
def mock_resource_class():
    class MockResource:
        @classmethod
        def get_schema(cls):
            class MockSchema:
                class MockBlock:
                    attributes = {}
                    def to_cty_type(self):
                        class MockValidator:
                            def validate(self, x): return None
                        return MockValidator()
                block = MockBlock()
            return MockSchema()
            
        async def read(self, ctx):
            raise Deferral(reason=DeferralReason.RESOURCE_CONFIG_UNKNOWN)
            
        async def plan(self, ctx):
            raise Deferral(reason=DeferralReason.ABSENT_PREREQ)

        config_class = MockState
        state_class = MockState
        private_state_class = None
    return MockResource
"""

import re
content = re.sub(r'@pytest.fixture\ndef mock_resource_class\(\):.*?return MockResource', replace_with, content, flags=re.DOTALL)

with open("tests/tfprotov6/handlers/test_deferral.py", "w") as f:
    f.write(content)
