#!/usr/bin/env python3
"""Validate official DP2 models or the standalone BPZ test candidate."""

import argparse
import os
import pickle
from pathlib import Path

import numpy as np
from rail.core.model import Model


OFFICIAL_ALGORITHMS = ("fzboost", "bpz")
ALGORITHMS = (*OFFICIAL_ALGORITHMS, "bpz_test")
OFFICIAL_PROVENANCE = {
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


TEST_PROVENANCE = {
    "project": "dp2_v3p1",
    "flavor": "cosmos31_test",
    "selection": "gold",
}


def validate_wrapper(
    path: Path, expected_class: str, expected_provenance: dict[str, str]
) -> Model:
    model = load_model(path)
    assert model.creation_class_name == expected_class, path
    assert model.catalog_tag == "lsst_gaap_1p0", path
    assert model.provenance == expected_provenance, path
    return model


def validate_fzboost(path: Path) -> None:
    wrapped = validate_wrapper(
        path,
        "rail.estimation.algos.flexzboost.FlexZBoostInformer",
        OFFICIAL_PROVENANCE,
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


def validate_bpz_prior(
    path: Path, nt_array: list[int], provenance: dict[str, str]
) -> None:
    wrapped = validate_wrapper(
        path, "rail.estimation.algos.bpz_lite.BPZliteInformer", provenance
    )
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
    assert prior["nt_array"] == nt_array
    np.testing.assert_array_equal(wrapped.data["zp_offsets"]["offsets"], np.zeros(6))


def validate_bpz(path: Path) -> None:
    validate_bpz_prior(path, [7, 57, 72], OFFICIAL_PROVENANCE)


def validate_bpz_test(path: Path) -> None:
    validate_bpz_prior(path, [7, 12, 12], TEST_PROVENANCE)


def paths_for(root: Path, algorithm: str) -> tuple[Path | None, Path]:
    basenames = {
        "fzboost": "model_dp2_v3p1_fzboost_dp2_6band_gold.pickle",
        "bpz": "model_dp2_v3p1_bpz_dp2_6band_gold.pickle",
        "bpz_test": "model_dp2_v3p1_bpz_test_cosmos31_gold.pickle",
    }
    basename = basenames[algorithm]
    model_dir = root / algorithm / "stage1" / "model"
    reference = None if algorithm == "bpz_test" else model_dir / "reference" / basename
    return reference, model_dir / basename


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate official reference/candidate models or BPZ test."
    )
    parser.add_argument("selection", choices=(*ALGORITHMS, "all"))
    args = parser.parse_args()

    try:
        root = Path(os.environ["PZ_DP2_ROOT"])
    except KeyError as error:
        raise SystemExit("PZ_DP2_ROOT is not set") from error

    algorithms = OFFICIAL_ALGORITHMS if args.selection == "all" else (args.selection,)
    validators = {
        "fzboost": validate_fzboost,
        "bpz": validate_bpz,
        "bpz_test": validate_bpz_test,
    }
    for algorithm in algorithms:
        reference, candidate = paths_for(root, algorithm)
        paths = [("candidate", candidate)]
        if reference is not None:
            paths.insert(0, ("reference", reference))
        for label, path in paths:
            validators[algorithm](path)
            print(f"{algorithm} {label}: compatible ({path})")


if __name__ == "__main__":
    main()
