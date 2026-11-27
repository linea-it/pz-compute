#!/usr/bin/env python3
"""Validate custom DP2 DNF cModel griz/riz models against their inputs."""

from __future__ import annotations

import argparse
import importlib.util
import os
import pickle
from pathlib import Path

import h5py
import numpy as np
from rail.core.model import Model

PROJECT_DIR = Path(__file__).resolve().parent.parent


def load_wrapper_module():
    path = PROJECT_DIR / "scripts/wrap-model.py"
    spec = importlib.util.spec_from_file_location("dp2_custom_dnf_wrapper", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load wrapper module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WRAPPER = load_wrapper_module()
VARIANTS = {"griz": tuple("griz"), "riz": tuple("riz")}
MAG_LIMITS = {"g": 27.8, "r": 27.1, "i": 26.7, "z": 25.8}


def model_path(root: Path, variant: str) -> Path:
    basename = f"model_dp2_v3p1_custom_dnf_cmodel_{variant}_gold.pickle"
    return root / variant / "stage1/model" / basename


def training_path(root: Path, variant: str) -> Path:
    return root / "common/training" / f"train_clipped_v3_cmodel_{variant}.hdf5"


def load_wrapped_model(path: Path) -> Model:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as stream:
        model = pickle.load(stream)
    if not isinstance(model, Model):
        raise TypeError(f"{path}: expected rail.core.model.Model, got {type(model)}")
    return model


def expected_training_arrays(path: Path, bands: tuple[str, ...]):
    with h5py.File(path, "r") as handle:
        truez = handle["redshift"][...]
        magnitudes = np.column_stack(
            [handle[f"{band}_cModelMag"][...] for band in bands]
        )
        errors = np.column_stack(
            [handle[f"{band}_cModelMagErr"][...] for band in bands]
        )
    for index, band in enumerate(bands):
        missing = np.isnan(magnitudes[:, index])
        magnitudes[missing, index] = MAG_LIMITS[band]
        errors[missing, index] = 1.0
    return truez, magnitudes, errors


def validate_model(root: Path, variant: str) -> None:
    bands = VARIANTS[variant]
    path = model_path(root, variant)
    training = training_path(root, variant)
    wrapped = load_wrapped_model(path)
    assert wrapped.creation_class_name == WRAPPER.CREATION_CLASS, path
    assert wrapped.catalog_tag == WRAPPER.CATALOG_TAG, path
    assert wrapped.version == 0, path
    assert wrapped.provenance == WRAPPER.provenance(variant), path

    model = wrapped.data
    assert set(model) == {"train_mag", "train_err", "truez", "clf", "train_norm"}
    truez, expected_mag, expected_err = expected_training_arrays(training, bands)
    expected_shape = (554_676, len(bands))
    assert model["train_mag"].shape == expected_shape, path
    assert model["train_err"].shape == expected_shape, path
    assert model["truez"].shape == (554_676,), path
    assert model["train_norm"].shape == (554_676,), path
    np.testing.assert_array_equal(model["truez"], truez)
    np.testing.assert_allclose(model["train_mag"], expected_mag, rtol=0, atol=0)
    np.testing.assert_allclose(
        model["train_err"], expected_err, rtol=0, atol=0, equal_nan=True
    )
    np.testing.assert_allclose(
        model["train_norm"], np.linalg.norm(expected_mag, axis=1), rtol=1e-13, atol=0
    )
    assert np.isfinite(model["train_mag"]).all(), path
    assert np.isfinite(model["truez"]).all(), path
    assert np.isclose(truez.min(), 0.0010000000474974513), path
    assert np.isclose(truez.max(), 9.975), path
    assert int((truez > 6.0).sum()) == 501, path

    clf = model["clf"]
    expected_parameters = {
        "algorithm": "auto",
        "leaf_size": 30,
        "metric": "minkowski",
        "metric_params": None,
        "n_jobs": None,
        "n_neighbors": 5,
        "p": 2,
        "weights": "uniform",
    }
    parameters = clf.get_params()
    for name, value in expected_parameters.items():
        assert parameters[name] == value, (path, name, parameters[name], value)
    assert clf.n_features_in_ == len(bands), path
    assert clf.n_samples_fit_ == 554_676, path
    assert clf.effective_metric_ == "euclidean", path
    assert clf._fit_method == "kd_tree", path
    print(f"{variant}: compatible ({path})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", choices=(*VARIANTS, "all"))
    args = parser.parse_args()
    try:
        root = Path(os.environ["PZ_DP2_CUSTOM_ROOT"])
    except KeyError as error:
        raise SystemExit("PZ_DP2_CUSTOM_ROOT is not set") from error
    variants = VARIANTS if args.selection == "all" else (args.selection,)
    for variant in variants:
        validate_model(root, variant)


if __name__ == "__main__":
    main()
