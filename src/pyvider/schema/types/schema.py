#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from typing import Any

from attrs import define, field
from provide.foundation import logger

from pyvider.cty import CtyValidationError

# CORRECTED IMPORT: Replace the obsolete PvsBlock with the new PvsObjectType.
from pyvider.schema.exceptions import PvsSchemaDefinitionError
from pyvider.schema.required import check_required_attributes
from pyvider.schema.types.object import PvsObjectType


def _validate_version(instance: object, attribute: object, value: int) -> None:
    """Reject negative schema versions.

    Zero is valid, and deliberately so. Terraform stores a resource's schema
    version in state as ``SchemaVersion uint64``
    (``internal/states/instance_object_src.go:29``), with no floor reserving 0
    as a sentinel, and ``"schema_version": 0`` is a genuine persisted value
    throughout ``internal/states/statefile/testdata/roundtrip/`` (e.g.
    ``v4-modules``, ``v4-simple``), alongside ``schema_version: 1`` in others
    (``v3-bigint.out.tfstate``, ``v3-grabbag.out.tfstate``). The identity
    version has the same floor: the protocol says identity "versioning
    implicitly starts at 0" (``docs/plugin-protocol/tfplugin6.proto``). Only
    negative versions are unrepresentable.

    Replaces a lambda that returned a bool. attrs signals validation failure by
    raising and discards return values, so the original enforced nothing.
    """
    if value < 0:
        raise PvsSchemaDefinitionError(f"Schema version must be 0 or greater, got {value}.")


@define(frozen=True, kw_only=True)
class PvsSchema:
    """
    Represents a complete schema definition for a provider, resource, or data source.
    This class is the root of a schema tree.

    Attributes:
        version: An integer representing the schema version, used for state upgrades.
        block: The root block of the schema, defining its attributes and nested blocks.
    """

    version: int = field(validator=_validate_version)
    block: PvsObjectType = field()

    def validate_config(self, config: Any) -> None:
        """
        Validates a configuration against this schema by converting the schema
        to its CtyType representation and invoking its validation logic.

        This method raises CtyValidationError on failure, which is the
        expected contract for direct validation. Higher-level handlers are
        responsible for catching this exception and creating diagnostics.
        """
        logger.debug("Validating configuration against schema", schema_version=self.version)
        if not isinstance(config, dict):
            raise CtyValidationError(f"Configuration must be a dictionary, but got {type(config).__name__}.")

        # Required-ness is checked here, and only here. cty deliberately allows
        # a null for any attribute -- go-cty does the same, and Terraform sends
        # nulls constantly -- so the schema is the only thing that knows which
        # attributes a practitioner must actually supply.
        check_required_attributes(self.block, config)

        # Convert the schema's block to its CtyType representation to get the validator.
        validator = self.block.to_cty_type()

        # The CtyType's validate method will raise CtyValidationError on failure.
        validator.validate(config)

    def to_cty_type(self) -> PvsObjectType:
        """
        Returns the CtyType representation of the schema's root block.
        Since the block is now a PvsObjectType, this is a direct return.
        """
        return self.block


# 🐍🏗️🔚
