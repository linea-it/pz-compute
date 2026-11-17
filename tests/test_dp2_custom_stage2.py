import importlib.util
from pathlib import Path

import h5py
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from rail_scripts.integrity import FINGERPRINT_ALGORITHM, row_id_fingerprint


ROOT = Path(__file__).parents[1]
PROJECT = ROOT / "doc/dp2_v3/custom/dnf_cmodel_griz_riz"
SCRIPT = PROJECT / "scripts/validate-stage2.py"
SFD = {"u": 4.78, "g": 3.65, "r": 2.70, "i": 2.06, "z": 1.58, "y": 1.31}


def load_validator():
    spec = importlib.util.spec_from_file_location("test_custom_stage2_validator", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_pair(tmp_path: Path, variant: str = "riz"):
    input_path = tmp_path / "input.parquet"
    output_path = tmp_path / "output.hdf5"
    object_ids = np.array([10, 20, 30], dtype=np.int64)
    i_mag = np.array([20.0, 21.0, 22.0])
    ebv = np.array([0.1, 0.2, 0.3])
    pq.write_table(
        pa.table(
            {
                "objectId": object_ids,
                "ebv": ebv,
                "r_cModelMag": i_mag + 0.5,
                "r_cModelMagErr": np.full(3, 0.1),
                "i_cModelMag": i_mag,
                "i_cModelMagErr": np.full(3, 0.1),
                "z_cModelMag": i_mag - 0.5,
                "z_cModelMagErr": np.full(3, 0.1),
            }
        ),
        input_path,
    )
    xvals = np.linspace(0.0, 6.0, 601)
    yvals = np.repeat(np.full((1, 601), 1.0 / 6.0), 3, axis=0)
    zn = np.array([0.2, 0.4, 0.6])
    with h5py.File(output_path, "w") as handle:
        data = handle.create_group("data")
        data.create_dataset("yvals", data=yvals)
        meta = handle.create_group("meta")
        meta.create_dataset("xvals", data=xvals[np.newaxis, :])
        internal = handle.create_group("ancil")
        internal.create_dataset("DNF_ZN", data=zn)
        ancillary = handle.create_group("ancillary")
        ancillary.create_dataset("DNF_ZN", data=zn)
        marker = handle.create_group("pz_compute").attrs
        marker["complete"] = True
        marker["row_count"] = 3
        marker["row_id_column"] = "objectId"
        marker["row_id_fingerprint_algorithm"] = FINGERPRINT_ALGORITHM
        marker["row_id_fingerprint"] = row_id_fingerprint(object_ids)
        marker["sfd_bands"] = variant
        marker["sfd_a_ebv"] = [SFD[band] for band in variant]
    return input_path, output_path


def test_pair_validator_checks_source_values_pdf_and_dnf_zn(tmp_path):
    validator = load_validator()
    input_path, output_path = write_pair(tmp_path)
    assert validator.validate_pair(input_path, output_path, "riz") == 3


def test_pair_validator_rejects_divergent_promoted_dnf_zn(tmp_path):
    validator = load_validator()
    input_path, output_path = write_pair(tmp_path)
    with h5py.File(output_path, "a") as handle:
        handle["ancillary/DNF_ZN"][1] = 9.0
    with pytest.raises(AssertionError):
        validator.validate_pair(input_path, output_path, "riz")


def test_stage2_runner_uses_custom_columns_and_ancillary_allow_list():
    runner = (PROJECT / "scripts/run-one-estimate.sbatch").read_text()
    assert '--bands="$PZ_CUSTOM_BANDS"' in runner
    assert "--column-template='{band}_cModelMag_sfd'" in runner
    assert "--column-template-error='{band}_cModelMagErr_sfd'" in runner
    assert "--output-ancil-columns=DNF_ZN" in runner
    assert "--output-columns" not in runner
    assert "PZ_DP2_ROOT" not in runner
