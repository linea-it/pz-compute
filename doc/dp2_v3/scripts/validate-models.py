#!/usr/bin/env python3
"""Validate trusted DP2 model artifacts for one algorithm or the full registry."""

import argparse
import os
import pickle
from pathlib import Path

import numpy as np
from rail.core.model import Model


ALGORITHMS = ("fzboost", "bpz")
PROVENANCE = {
    "project": "dp2_v3p1",
    "flavor": "dp2_6band",
    "selection": "gold",
}


def load_model(path: Path) -> Model:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as stream:
        model = pickle.load(stream)
    if not isinstance(model, Model):
        raise TypeError(f"{path}: expected rail.core.model.Model, got {type(model)}")
    return model


def validate_wrapper(path: Path, expected_class: str) -> Model:
    model = load_model(path)
    assert model.creation_class_name == expected_class, path
    assert model.catalog_tag == "lsst_gaap_1p0", path
    assert model.provenance == PROVENANCE, path
    return model


def validate_fzboost(path: Path) -> None:
    wrapped = validate_wrapper(
        path, "rail.estimation.algos.flexzboost.FlexZBoostInformer"
    )
    model = wrapped.data
    assert model.max_basis == 50
    assert model.basis_system == "cosine"
    assert model.z_min == 0.0
    assert model.z_max == 6.0
    np.testing.assert_array_equal(model.best_basis, np.arange(50))
    assert np.isclose(model.bump_threshold, 0.02)
    assert np.isclose(model.sharpen_alpha, 1.2)
    assert model.model.models.n_features_in_ == 6
    assert len(model.model.models.estimators_) == 50

    expected = {
        "max_depth": 8,
        "learning_rate": 0.3,
        "verbosity": 1,
        "objective": "reg:squarederror",
    }
    for key, value in expected.items():
        assert model.model.params[key] == value, (path, key)
    for regressor in model.model.models.estimators_:
        params = regressor.get_params()
        for key, value in expected.items():
            assert params[key] == value, (path, key)


def validate_bpz(path: Path) -> None:
    wrapped = validate_wrapper(path, "rail.estimation.algos.bpz_lite.BPZliteInformer")
    prior = wrapped.data["priormodel"]
    expected = {
        "fo_arr": [0.35, 0.5],
        "kt_arr": [0.45, 0.147],
        "zo_arr": [0.431, 0.39, 0.0626],
        "km_arr": [0.0913, 0.0636, 0.123],
        "a_arr": [2.465, 1.806, 0.906],
    }
    for name, values in expected.items():
        np.testing.assert_allclose(prior[name], values, rtol=0, atol=0)
    assert prior["mo"] == 20.0
    assert prior["nt_array"] == [7, 57, 72]
    np.testing.assert_array_equal(wrapped.data["zp_offsets"]["offsets"], np.zeros(6))


def paths_for(root: Path, algorithm: str) -> tuple[Path, Path]:
    basename = f"model_dp2_v3p1_{algorithm}_dp2_6band_gold.pickle"
    model_dir = root / algorithm / "stage1" / "model"
    return model_dir / "reference" / basename, model_dir / basename


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate trusted reference and candidate DP2 model pickles."
    )
    parser.add_argument("selection", choices=(*ALGORITHMS, "all"))
    args = parser.parse_args()

    try:
        root = Path(os.environ["PZ_DP2_ROOT"])
    except KeyError as error:
        raise SystemExit("PZ_DP2_ROOT is not set") from error

    algorithms = ALGORITHMS if args.selection == "all" else (args.selection,)
    validators = {"fzboost": validate_fzboost, "bpz": validate_bpz}
    for algorithm in algorithms:
        reference, candidate = paths_for(root, algorithm)
        for label, path in (("reference", reference), ("candidate", candidate)):
            validators[algorithm](path)
            print(f"{algorithm} {label}: compatible ({path})")


if __name__ == "__main__":
    main()
