from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import types

import numpy as np
import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "rail_scripts" / "pz-build-hats"
RUNNER = ROOT / "doc" / "dp2_v3" / "scripts" / "run-one-hats.sbatch"


def load_builder():
    pytest.importorskip("h5py")
    pytest.importorskip("pyarrow")
    pytest.importorskip("docopt")
    module_name = "testable_pz_build_hats"
    module = types.ModuleType(module_name)
    module.__file__ = str(SCRIPT)
    sys.modules[module_name] = module
    SourceFileLoader(module_name, str(SCRIPT)).exec_module(module)
    return module


def test_nested_pdf_array_matches_dp1_struct_of_lists_schema():
    builder = load_builder()
    xvals = np.linspace(0, 1, 4, dtype=np.float64)
    yvals = np.asarray([[0, 1, 2, 3], [3, 2, 1, 0]], dtype=np.float64)

    nested = builder.nested_pdf_array(xvals, yvals, "float32")

    assert nested.type.names == ["xvals", "yvals"]
    assert str(nested.type.field("xvals").type) == "list<item: float>"
    assert str(nested.type.field("yvals").type) == "list<item: float>"
    assert nested[0].as_py() == {
        "xvals": xvals.astype(np.float32).tolist(),
        "yvals": yvals[0].astype(np.float32).tolist(),
    }
    assert nested[1].as_py()["xvals"] == nested[0].as_py()["xvals"]


def test_dp2_stage3_runner_builds_nested_only_algorithm_column():
    source = RUNNER.read_text(encoding="utf-8")
    assert "--pdf-layout=nested" in source
    assert '--pdf-column="${PZ_ALGORITHM}_ens_interp"' in source
    assert "--delete-hdf5-outputs" not in source
    assert '--slurm-job-name="$worker_job_name"' in source
    assert '--margin-threshold="$PZ_HATS_MARGIN_ARCSEC"' in source


def test_builder_configures_default_margin_for_both_hats_paths():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--margin-threshold=<arcsec>" in source
    assert "margin_threshold=cfg.margin_threshold" in source
    assert ").add_margin(" in source
    assert "is_default=True" in source

