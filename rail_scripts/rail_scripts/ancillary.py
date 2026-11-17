"""Validation helpers for estimator-specific qp ancillary arrays."""

from __future__ import annotations

import h5py
import numpy as np


def load_estimator_ancillary(handle, names, expected_rows: int) -> dict[str, np.ndarray]:
    """Load an allow-list of one-dimensional datasets from the qp ``ancil`` group."""
    if not names:
        return {}
    source = handle.get("ancil")
    if source is None:
        raise ValueError("estimator output is missing the ancil group")

    result = {}
    for name in names:
        if name not in source:
            raise ValueError(f"estimator output is missing ancil/{name}")
        dataset = source[name]
        if not isinstance(dataset, h5py.Dataset) or dataset.ndim != 1:
            raise ValueError(f"ancil/{name} must be a one-dimensional dataset")
        if dataset.shape[0] != expected_rows:
            raise ValueError(
                f"ancil/{name} has {dataset.shape[0]} rows; expected {expected_rows}"
            )
        result[name] = np.asarray(dataset)
    return result
