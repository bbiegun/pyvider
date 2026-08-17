#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""The data_sources package exports what a data source needs to subclass."""


def test_base_data_source_is_exported() -> None:
    """`pyvider.data_sources` exports its base class, as `pyvider.resources` does.

    Without it, every data source has to import from `pyvider.data_sources.base` —
    a private path that the decorator's own package does not advertise.
    """
    from pyvider.data_sources import BaseDataSource, register_data_source

    assert BaseDataSource is not None
    assert callable(register_data_source)


def test_exports_match_all() -> None:
    import pyvider.data_sources as ds

    for name in ds.__all__:
        assert hasattr(ds, name), f"{name} in __all__ but not importable"
