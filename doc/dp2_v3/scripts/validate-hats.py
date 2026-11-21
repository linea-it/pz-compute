#!/usr/bin/env python3
"""Validate Stage 3 products for one DP2 algorithm or the full registry."""

import argparse
import os
from pathlib import Path

import h5py
import lsdb
import numpy as np
import qp


OFFICIAL_ALGORITHMS = ("fzboost", "bpz", "dnf")
ALGORITHMS = (*OFFICIAL_ALGORITHMS, "bpz_test")
SUMMARY_COLUMNS = [
    "objectId",
    "coord_ra",
    "coord_dec",
    "zmode",
    "zmean",
    "zmedian",
    "z_p16",
    "z_p84",
    "i_gaap1p0Mag_sfd",
    "refExtendedness",
]
SAMPLE_ROWS = 8
DEFAULT_MARGIN_ARCSEC = 5.0


def stage2_rows(input_root: Path, output_root: Path) -> int:
    total = 0
    for input_path in input_root.glob("**/*.parquet"):
        relative = input_path.relative_to(input_root)
        output_path = output_root / relative.with_suffix(".hdf5")
        if not output_path.is_file():
            raise FileNotFoundError(output_path)
        with h5py.File(output_path, "r") as handle:
            total += handle["data/yvals"].shape[0]
    return total


def weighted_quantile(xvals: np.ndarray, yvals: np.ndarray, q: float) -> np.ndarray:
    totals = yvals.sum(axis=1)
    cdf = np.cumsum(yvals, axis=1)
    return np.asarray(
        [xvals[min(np.searchsorted(row, q * total), len(xvals) - 1)]
         for row, total in zip(cdf, totals)]
    )


def validate_nested_sample(catalog, algorithm: str) -> int:
    pdf_column = f"{algorithm}_ens_interp"
    expected_columns = [*SUMMARY_COLUMNS, pdf_column]
    assert list(catalog.columns) == expected_columns, algorithm
    assert pdf_column in catalog.nested_columns, (algorithm, catalog.nested_columns)

    columns = ["objectId", "zmode", "zmean", "zmedian", "z_p16", "z_p84", pdf_column]
    sample = catalog[columns].head(SAMPLE_ROWS)
    assert len(sample) > 0, f"{algorithm}: empty HATS sample"
    nested = sample[pdf_column]
    xvals = [np.asarray(nested.iloc[index]["xvals"]) for index in range(len(sample))]
    yvals = [np.asarray(nested.iloc[index]["yvals"]) for index in range(len(sample))]
    assert all(values.shape == (601,) for values in xvals), algorithm
    assert all(values.shape == (601,) for values in yvals), algorithm
    assert all(values.dtype == np.float32 for values in xvals), algorithm
    assert all(values.dtype == np.float32 for values in yvals), algorithm
    assert all(np.array_equal(xvals[0], values) for values in xvals[1:]), algorithm

    grid = xvals[0].astype(np.float64)
    matrix = np.stack(yvals).astype(np.float64)
    assert np.isfinite(grid).all() and np.all(np.diff(grid) > 0), algorithm
    assert np.isfinite(matrix).all(), algorithm
    assert np.all(matrix >= 0), algorithm
    totals = matrix.sum(axis=1)
    assert np.all(totals > 0), algorithm

    ensemble = qp.Ensemble(
        qp.interp_gen,
        data={"xvals": grid, "yvals": matrix},
    )
    assert ensemble.shape == matrix.shape, algorithm

    reconstructed = {
        "zmode": grid[np.argmax(matrix, axis=1)],
        "zmean": (matrix * grid).sum(axis=1) / totals,
        "zmedian": weighted_quantile(grid, matrix, 0.50),
        "z_p16": weighted_quantile(grid, matrix, 0.16),
        "z_p84": weighted_quantile(grid, matrix, 0.84),
    }
    for name, values in reconstructed.items():
        stored = sample[name].to_numpy(dtype=float)
        assert np.allclose(stored, values, rtol=0, atol=1e-5), (algorithm, name)
    return len(sample)


def validate(root: Path, input_root: Path, algorithm: str) -> None:
    stage2_output = root / algorithm / "stage2" / "output"
    hats_dir = (
        root
        / algorithm
        / "stage3"
        / "output"
        / f"pz-{algorithm}-gaap1p0-clipped-hats"
    )
    pdf_dir = Path(f"{hats_dir}.pdf")
    staging = Path(f"{hats_dir}.parquet_staging")

    catalog = lsdb.open_catalog(hats_dir)
    expected_margin = float(
        os.environ.get("PZ_HATS_MARGIN_ARCSEC", DEFAULT_MARGIN_ARCSEC)
    )
    assert catalog.margin is not None, f"{algorithm}: missing default margin catalog"
    actual_margin = catalog.margin.hc_structure.catalog_info.margin_threshold
    assert np.isclose(actual_margin, expected_margin), (
        algorithm,
        actual_margin,
        expected_margin,
    )
    summary_rows = len(catalog)
    sample_rows = validate_nested_sample(catalog, algorithm)

    hdf5_rows = stage2_rows(input_root, stage2_output)
    assert hdf5_rows == summary_rows, (
        algorithm,
        hdf5_rows,
        summary_rows,
    )
    assert not staging.exists(), f"temporary staging still exists: {staging}"
    assert not pdf_dir.exists(), f"unexpected companion PDF product: {pdf_dir}"
    print(
        f"{algorithm}: compatible nested HATS "
        f"(stage2={hdf5_rows}, hats={summary_rows}, sampled_pdfs={sample_rows}, "
        f"default_margin_arcsec={actual_margin:g})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", choices=(*ALGORITHMS, "all"))
    args = parser.parse_args()

    try:
        root = Path(os.environ["PZ_DP2_ROOT"])
    except KeyError as error:
        raise SystemExit("PZ_DP2_ROOT is not set") from error
    input_root = Path(
        os.environ.get(
            "PZ_DP2_INPUT_DATASET",
            "/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset",
        )
    )
    algorithms = OFFICIAL_ALGORITHMS if args.selection == "all" else (args.selection,)
    for algorithm in algorithms:
        validate(root, input_root, algorithm)


if __name__ == "__main__":
    main()
