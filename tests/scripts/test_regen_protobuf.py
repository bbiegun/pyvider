#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Unit tests for the protobuf regeneration script's drift checks."""

from scripts.regen_protobuf import mask_toolchain_versions

PB2_SAMPLE = """# Protobuf Python Version: 7.35.1
\"\"\"Generated protocol buffer code.\"\"\"
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    7,
    35,
    1,
    '',
    'tfplugin6.proto'
)
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\\n\\x0ftfplugin6.proto')
"""

GRPC_SAMPLE = """GRPC_GENERATED_VERSION = '1.83.0'
GRPC_VERSION = grpc.__version__
"""


def test_masking_makes_differing_toolchain_versions_compare_equal():
    """A pure toolchain bump must not read as proto drift."""
    newer = PB2_SAMPLE.replace("7.35.1", "7.36.0").replace(
        "    7,\n    35,\n    1,", "    7,\n    36,\n    0,"
    )
    assert newer != PB2_SAMPLE
    assert mask_toolchain_versions(newer) == mask_toolchain_versions(PB2_SAMPLE)


def test_masking_makes_differing_grpc_versions_compare_equal():
    """The grpc stub's generated-version constant is toolchain noise too."""
    newer = GRPC_SAMPLE.replace("1.83.0", "1.84.0")
    assert newer != GRPC_SAMPLE
    assert mask_toolchain_versions(newer) == mask_toolchain_versions(GRPC_SAMPLE)


def test_masking_preserves_real_proto_drift():
    """Masking must not blind the check to an actual change in the descriptor."""
    changed = PB2_SAMPLE.replace("tfplugin6.proto')", "tfplugin7.proto')")
    assert mask_toolchain_versions(changed) != mask_toolchain_versions(PB2_SAMPLE)


def test_masking_preserves_drift_in_unrelated_numbers():
    """Only the known version tokens are masked, not every integer."""
    changed = PB2_SAMPLE.replace("_descriptor_pool.Default()", "_descriptor_pool.Other()")
    assert mask_toolchain_versions(changed) != mask_toolchain_versions(PB2_SAMPLE)


import pytest

from scripts.regen_protobuf import (
    declared_floor,
    extract_generated_versions,
)


def _write_stub_pair(tmp_path, protobuf_version: str, grpc_version: str):
    """Write a minimal generated-stub pair carrying the given versions."""
    pb2 = PB2_SAMPLE.replace("7.35.1", protobuf_version)
    grpc = GRPC_SAMPLE.replace("1.83.0", grpc_version)
    (tmp_path / "tfplugin6_pb2.py").write_text(pb2)
    (tmp_path / "tfplugin6_pb2_grpc.py").write_text(grpc)
    return tmp_path


def test_extract_generated_versions_reads_both_stamps(tmp_path):
    out = _write_stub_pair(tmp_path, "7.36.0", "1.84.0")
    assert extract_generated_versions(out) == ("7.36.0", "1.84.0")


def test_extract_generated_versions_rejects_missing_stamp(tmp_path):
    (tmp_path / "tfplugin6_pb2.py").write_text("no banner here\n")
    (tmp_path / "tfplugin6_pb2_grpc.py").write_text(GRPC_SAMPLE)
    with pytest.raises(SystemExit):
        extract_generated_versions(tmp_path)


def test_declared_floor_reads_pyproject():
    """The real pyproject must declare floors for both packages."""
    assert declared_floor("protobuf") is not None
    assert declared_floor("grpcio") is not None


def test_declared_floor_returns_none_for_absent_package():
    assert declared_floor("definitely-not-a-dependency") is None
