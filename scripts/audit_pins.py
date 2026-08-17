#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Report capped or exact dependency pins across the core pyvider suite.

The suite's policy is floor-only constraints: a cap turns a loud, fixable
failure into a silent refusal to upgrade, and outlives whatever it went up for.
Run this to confirm the policy still holds.
"""

from pathlib import Path
import sys
import tomllib

SUITE_ROOT = Path("/Volumes/data/pyv")
CORE = (
    "provide-foundation",
    "provide-testkit",
    "pyvider-cty",
    "pyvider-rpcplugin",
    "pyvider-hcl",
    "pyvider",
    "plating",
    "pyvider-components",
    "tofusoup",
    "terraform-provider-pyvider",
)
CAPPED = ("<", "==", "~=")


def requirements(repo: str) -> list[tuple[str, str]]:
    """Yield (section, requirement) for every dependency the repo declares."""
    data = tomllib.loads((SUITE_ROOT / repo / "pyproject.toml").read_text())
    project = data.get("project", {})
    found = [("dependencies", r) for r in project.get("dependencies", [])]
    for extra, reqs in project.get("optional-dependencies", {}).items():
        found += [(f"optional:{extra}", r) for r in reqs]
    for group, reqs in data.get("dependency-groups", {}).items():
        found += [(f"group:{group}", r) for r in reqs if isinstance(r, str)]
    return found


def main() -> int:
    offenders = []
    for repo in CORE:
        for section, requirement in requirements(repo):
            # Environment markers after ';' may legitimately contain '<'.
            if any(token in requirement.split(";")[0] for token in CAPPED):
                offenders.append(f"{repo} [{section}] {requirement}")

    if offenders:
        print("Capped or exact pins found:")
        for offender in offenders:
            print(f"  {offender}")
        return 1

    print(f"No capped pins across {len(CORE)} core repositories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
