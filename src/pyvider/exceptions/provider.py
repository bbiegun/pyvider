#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from provide.foundation.errors import (
    ConfigurationError as FoundationConfigurationError,
    RuntimeError as FoundationRuntimeError,
)

from pyvider.exceptions.base import ComponentConfigurationError


class ProviderError(FoundationConfigurationError):
    """Base class for provider-specific errors."""

    def _default_code(self) -> str:
        return "PROVIDER_ERROR"


class ProviderConfigurationError(ProviderError, ComponentConfigurationError):
    """Raised when provider configuration is invalid."""


class ProviderAlreadyConfiguredError(ProviderError):
    """Raised when a provider that is already configured is configured again.

    This exists as its own type so that a repeated ConfigureProvider RPC -- which
    is normal and must succeed -- can be told apart from a provider's own
    configure() hook failing. Distinguishing them by inspecting the provider's
    `_configured` flag cannot work: BaseProvider.configure() sets that flag before
    a subclass's body (the part that builds a client) has run, so a hook that
    fails afterwards is indistinguishable from a repeat and gets reported to
    Terraform as success.
    """

    def _default_code(self) -> str:
        return "PROVIDER_ALREADY_CONFIGURED"


class ProviderInitializationError(FoundationRuntimeError):
    """Raised when provider initialization fails."""

    def _default_code(self) -> str:
        return "PROVIDER_INITIALIZATION_ERROR"


# 🐍🏗️🔚
