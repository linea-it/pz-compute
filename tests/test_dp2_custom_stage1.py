import importlib.util
import pickle
from pathlib import Path
import subprocess

import numpy as np
from rail.core.model import Model


ROOT = Path(__file__).parents[1]
PROJECT = ROOT / "doc/dp2_v3/custom/dnf_cmodel_griz_riz"
SCRIPTS = PROJECT / "scripts"


def load_script(name: str, module_name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def variant_environment(variant: str, root: Path) -> dict[str, str]:
    command = f"""
set -euo pipefail
export PZ_DP2_CUSTOM_ROOT={root!s}
source {SCRIPTS / 'variant-config.sh'}
custom_dnf_variant_config {variant}
printf '%s\\n' "$PZ_CUSTOM_BANDS" "$PZ_CUSTOM_TRAIN_CONFIG" \
  "$PZ_CUSTOM_TRAINING_DATA" "$PZ_CUSTOM_MODEL_BASENAME" "$PZ_CUSTOM_STAGE1"
"""
    result = subprocess.run(
        ["bash", "-c", command], check=True, capture_output=True, text=True
    )
    keys = ("bands", "config", "training", "model", "stage1")
    return dict(zip(keys, result.stdout.splitlines(), strict=True))


def test_variant_config_is_explicit_and_isolated(tmp_path):
    griz = variant_environment("griz", tmp_path)
    riz = variant_environment("riz", tmp_path)

    assert griz["bands"] == "griz"
    assert riz["bands"] == "riz"
    assert griz["config"].endswith("/config/dnf-griz-train.yaml")
    assert riz["training"] == str(
        tmp_path / "common/training/train_clipped_v3_cmodel_riz.hdf5"
    )
    assert griz["model"] == (
        "model_dp2_v3p1_custom_dnf_cmodel_griz_gold.pickle"
    )
    assert griz["stage1"] == str(tmp_path / "griz/stage1")
    assert riz["stage1"] == str(tmp_path / "riz/stage1")


def test_variant_config_rejects_unknown_variant(tmp_path):
    command = f"""
export PZ_DP2_CUSTOM_ROOT={tmp_path!s}
source {SCRIPTS / 'variant-config.sh'}
custom_dnf_variant_config ugrizy
"""
    result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
    assert result.returncode == 2
    assert "expected griz or riz" in result.stderr


def test_wrapper_sets_custom_metadata_without_mutating_raw(tmp_path):
    wrapper = load_script("wrap-model.py", "test_dp2_custom_wrapper")
    raw_data = {"train_mag": np.array([[20.0, 21.0, 22.0]])}
    raw = tmp_path / "raw.pickle"
    output = tmp_path / "wrapped.pickle"
    with raw.open("wb") as stream:
        pickle.dump(raw_data, stream)

    wrapper.wrap_model("riz", raw, output)

    with raw.open("rb") as stream:
        assert pickle.load(stream).keys() == raw_data.keys()
    with output.open("rb") as stream:
        wrapped = pickle.load(stream)
    assert isinstance(wrapped, Model)
    assert wrapped.data.keys() == raw_data.keys()
    assert wrapped.creation_class_name == wrapper.CREATION_CLASS
    assert wrapped.catalog_tag == "lsst_cmodel"
    assert wrapped.version == 0
    assert wrapped.provenance == {
        "project": "dp2_v3p1_custom",
        "flavor": "dnf_cmodel_riz",
        "selection": "gold",
    }


def test_stage1_runner_opts_into_custom_bands_and_columns():
    runner = (SCRIPTS / "run-one-train.sbatch").read_text()
    assert '--bands="$PZ_CUSTOM_BANDS"' in runner
    assert "--column-template='{band}_cModelMag'" in runner
    assert "--column-template-error='{band}_cModelMagErr'" in runner
    assert "$PZ_CUSTOM_PROJECT_DIR/scripts/wrap-model.py" in runner
    assert "PZ_DP2_ROOT" not in runner
