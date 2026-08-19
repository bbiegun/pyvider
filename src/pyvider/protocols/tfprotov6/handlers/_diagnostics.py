#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Diagnostics shared by the component-dispatching handlers.

Every handler that resolves a Terraform type name to a registered component
needs the same two things: a plain error diagnostic, and one that reports an
unregistered type. Those were written three times over -- once per component
kind -- which is how the wording drifted apart. Building them here keeps a
provider's error messages consistent whichever RPC surfaced the problem.
"""

from __future__ import annotations

from collections.abc import Iterable

import pyvider.protocols.tfprotov6.protobuf as pb


def error_diagnostic(summary: str, detail: str = "") -> pb.Diagnostic:
    """An error-severity diagnostic."""
    return pb.Diagnostic(severity=pb.Diagnostic.ERROR, summary=summary, detail=detail)


def warning_diagnostic(summary: str, detail: str = "") -> pb.Diagnostic:
    """A warning-severity diagnostic."""
    return pb.Diagnostic(severity=pb.Diagnostic.WARNING, summary=summary, detail=detail)


def unknown_type_diagnostic(
    kind: str, type_name: str, registered: Iterable[str], decorator: str
) -> pb.Diagnostic:
    """Report a type name no component is registered under.

    Listing what *is* registered turns "unknown type" into something the
    practitioner can act on: nearly always a typo or a component that was never
    imported, and the answer is visible in the message either way.
    """
    known = sorted(registered)
    return error_diagnostic(
        f"Unknown {kind} type '{type_name}'",
        f"Register it with {decorator}. Registered {kind} types: " + (", ".join(known) if known else "(none)"),
    )


# 🐍🏗️🔚
