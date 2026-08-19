from typing import Any, ClassVar

import attrs
import pytest

from pyvider.actions.types import DeferralReason
from pyvider.exceptions.deferral import Deferral
from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers.plan_resource_change import PlanResourceChangeHandler
from pyvider.protocols.tfprotov6.handlers.read_resource import ReadResourceHandler
import pyvider.protocols.tfprotov6.protobuf as pb


@attrs.define
class MockState:
    pass


@pytest.fixture
def mock_resource_class():
    class MockResource:
        @classmethod
        def get_schema(cls) -> Any:
            class MockSchema:
                class MockBlock:
                    attributes: ClassVar[dict[str, Any]] = {}

                    def to_cty_type(self):
                        class MockValidator:
                            def validate(self, x):
                                return None

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
    """Register the doubles this module needs, and put the hub back afterwards.

    The hub is process-global. Leaving `test_resource` registered makes every
    later test that expects it to be absent take the found-it path instead --
    which is how this module used to break `test_structured_logging`'s
    unregistered-resource assertions, depending only on file ordering.
    """

    class MockProvider:
        class Metadata:
            capabilities: ClassVar[list[Any]] = []

        metadata = Metadata()

    registrations = {
        ("resource", "test_resource"): mock_resource_class,
        ("singleton", "provider"): MockProvider(),
        ("singleton", "provider_context"): object(),
    }
    previous = {key: hub.get_component(*key) for key in registrations}

    for (dimension, name), component in registrations.items():
        hub.register(dimension, name, component)

    yield

    for dimension, name in registrations:
        restored = previous[(dimension, name)]
        if restored is None:
            if hub.get_component(dimension, name) is not None:
                hub.unregister(dimension, name)
        else:
            hub.register(dimension, name, restored)


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
