import attrs
import pytest
from unittest.mock import AsyncMock, patch

from pyvider.actions.types import DeferralReason
from pyvider.exceptions.deferral import Deferral
from pyvider.protocols.tfprotov6.handlers.read_resource import ReadResourceHandler
from pyvider.protocols.tfprotov6.handlers.plan_resource_change import PlanResourceChangeHandler
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.hub import hub


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


@pytest.fixture
def setup_hub(mock_resource_class):
    hub.register("resource", "test_resource", mock_resource_class)
    
    class MockProvider:
        class Metadata:
            capabilities = []
        metadata = Metadata()
    hub.register("singleton", "provider", MockProvider())
    hub.register("singleton", "provider_context", object())
    
    yield
    
    # hub is managed by other fixtures or doesn't need clear

@pytest.mark.asyncio
async def test_read_resource_deferral_allowed(setup_hub):
    req = pb.ReadResource.Request(
        type_name="test_resource",
    )
    req.client_capabilities.deferral_allowed = True
    
    resp = await ReadResourceHandler(req, None)
    
    assert resp.deferred.reason == pb.Deferred.Reason.RESOURCE_CONFIG_UNKNOWN
    assert len(resp.diagnostics) == 0

@pytest.mark.asyncio
async def test_read_resource_deferral_not_allowed(setup_hub):
    req = pb.ReadResource.Request(
        type_name="test_resource",
    )
    req.client_capabilities.deferral_allowed = False
    
    resp = await ReadResourceHandler(req, None)
    
    assert len(resp.diagnostics) == 1
    assert resp.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert "Invalid Deferral" in resp.diagnostics[0].summary

@pytest.mark.asyncio
async def test_plan_resource_deferral_allowed(setup_hub):
    req = pb.PlanResourceChange.Request(
        type_name="test_resource",
    )
    req.client_capabilities.deferral_allowed = True
    
    resp = await PlanResourceChangeHandler(req, None)
    
    assert resp.deferred.reason == pb.Deferred.Reason.ABSENT_PREREQ
    assert len(resp.diagnostics) == 0

@pytest.mark.asyncio
async def test_plan_resource_deferral_not_allowed(setup_hub):
    req = pb.PlanResourceChange.Request(
        type_name="test_resource",
    )
    req.client_capabilities.deferral_allowed = False
    
    resp = await PlanResourceChangeHandler(req, None)
    
    assert len(resp.diagnostics) == 1
    assert resp.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert "Invalid Deferral" in resp.diagnostics[0].summary
