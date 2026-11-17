from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import types

import numpy as np
import pandas as pd


ROOT = Path(__file__).parents[1]
SCRIPT = (
    ROOT
    / "doc"
    / "dp2_v3"
    / "custom"
    / "dnf_cmodel_griz_riz"
    / "scripts"
    / "prepare-training-catalog.py"
)


def load_preparer():
    module_name = "testable_dp2_custom_training_preparer"
    module = types.ModuleType(module_name)
    module.__file__ = str(SCRIPT)
    sys.modules[module_name] = module
    SourceFileLoader(module_name, str(SCRIPT)).exec_module(module)
    return module


def test_variant_frame_preserves_rows_and_expected_column_order():
    preparer = load_preparer()
    data = pd.DataFrame({"redshift": [0.1, 0.2]})
    for band in "griz":
        data[f"{band}_cModelMag"] = [20.0, 21.0]
        data[f"{band}_cModelMagErr"] = [0.1, 0.2]

    griz = preparer.variant_frame(data, preparer.VARIANTS["griz"])
    riz = preparer.variant_frame(data, preparer.VARIANTS["riz"])

    assert len(griz) == len(riz) == len(data)
    assert griz.columns.tolist() == [
        "redshift",
        "g_cModelMag",
        "r_cModelMag",
        "i_cModelMag",
        "z_cModelMag",
        "g_cModelMagErr",
        "r_cModelMagErr",
        "i_cModelMagErr",
        "z_cModelMagErr",
    ]
    assert riz.columns.tolist() == [
        "redshift",
        "r_cModelMag",
        "i_cModelMag",
        "z_cModelMag",
        "r_cModelMagErr",
        "i_cModelMagErr",
        "z_cModelMagErr",
    ]
    np.testing.assert_array_equal(griz["redshift"], data["redshift"])
    np.testing.assert_array_equal(riz["redshift"], data["redshift"])


def test_required_columns_include_dereddening_evidence():
    preparer = load_preparer()
    columns = preparer.required_source_columns()

    assert columns[:2] == ["redshift", "ebv"]
    for band in "griz":
        assert f"{band}_cModelFlux" in columns
        assert f"{band}_cModelFluxErr" in columns
        assert f"{band}_cModelMag" in columns
        assert f"{band}_cModelMagErr" in columns
