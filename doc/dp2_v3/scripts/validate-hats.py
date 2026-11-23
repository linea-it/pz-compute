#!/usr/bin/env python3
"""Validate Stage 3 products for one DP2 algorithm or the full registry."""

import argparse
import os
from pathlib import Path

import h5py
import lsdb
import numpy as np
import qp
from scipy.integrate import simpson
from scipy.optimize import minimize_scalar


OFFICIAL_ALGORITHMS = ("fzboost", "bpz", "dnf")
ALGORITHMS = (*OFFICIAL_ALGORITHMS, "bpz_test")
IDENTITY_COLUMNS = [
    "objectId",
    "coord_ra",
    "coord_dec",
]
EXTRA_COLUMNS = [
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


def science_columns(algorithm: str) -> list[str]:
    return [
        f"{algorithm}_z_mode",
        f"{algorithm}_z_mean",
        f"{algorithm}_z_median",
        f"{algorithm}_z_best",
        f"{algorithm}_z_err68_low",
        f"{algorithm}_z_err68_high",
        f"{algorithm}_z_err95_low",
        f"{algorithm}_z_err95_high",
    ]


def trapezoid_weights(xvals: np.ndarray) -> np.ndarray:
    delta = np.diff(xvals)
    weights = np.empty_like(xvals)
    weights[0] = delta[0] / 2
    weights[-1] = delta[-1] / 2
    weights[1:-1] = (delta[:-1] + delta[1:]) / 2
    return weights


def interpolated_quantile(
    xvals: np.ndarray, yvals: np.ndarray, quantile: float
) -> np.ndarray:
    widths = np.diff(xvals)
    areas = 0.5 * (yvals[:, :-1] + yvals[:, 1:]) * widths[None, :]
    cdf = np.cumsum(areas, axis=1)
    totals = cdf[:, -1]
    result = np.empty(len(yvals), dtype=np.float64)
    for row, (density, cumulative, total) in enumerate(zip(yvals, cdf, totals)):
        target = quantile * total
        index = min(np.searchsorted(cumulative, target), len(widths) - 1)
        previous = 0.0 if index == 0 else cumulative[index - 1]
        scaled_area = max(target - previous, 0.0) / widths[index]
        y0 = density[index]
        slope = density[index + 1] - y0
        if abs(slope) <= 1e-14 * max(1.0, abs(y0)):
            fraction = scaled_area / y0 if y0 > 0 else 0.0
        else:
            discriminant = max(y0 * y0 + 2 * slope * scaled_area, 0.0)
            fraction = (-y0 + np.sqrt(discriminant)) / slope
        result[row] = xvals[index] + np.clip(fraction, 0.0, 1.0) * widths[index]
    return result


def validate_nested_sample(catalog, algorithm: str) -> int:
    pdf_column = f"{algorithm}_ens_interp"
    expected_columns = [
        *IDENTITY_COLUMNS,
        *science_columns(algorithm),
        *EXTRA_COLUMNS,
        pdf_column,
    ]
    assert list(catalog.columns) == expected_columns, algorithm
    assert pdf_column in catalog.nested_columns, (algorithm, catalog.nested_columns)

    columns = ["objectId", *science_columns(algorithm), pdf_column]
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

    weights = trapezoid_weights(grid)
    integral = matrix @ weights
    prefix = f"{algorithm}_z_"
    reconstructed = {
        f"{prefix}mode": grid[np.argmax(matrix, axis=1)],
        f"{prefix}mean": ((matrix * grid) @ weights) / integral,
        f"{prefix}median": interpolated_quantile(grid, matrix, 0.50),
        f"{prefix}err68_low": interpolated_quantile(grid, matrix, 0.16),
        f"{prefix}err68_high": interpolated_quantile(grid, matrix, 0.84),
        f"{prefix}err95_low": interpolated_quantile(grid, matrix, 0.025),
        f"{prefix}err95_high": interpolated_quantile(grid, matrix, 0.975),
    }
    for name, values in reconstructed.items():
        stored = sample[name].to_numpy(dtype=float)
        assert np.allclose(stored, values, rtol=0, atol=1e-5), (algorithm, name)

    best = sample[f"{prefix}best"].to_numpy(dtype=float)
    assert np.isfinite(best).all() and np.all((grid[0] <= best) & (best <= grid[-1]))
    expected_best = []
    for density in matrix:

        def risk(candidate):
            residual = (candidate - grid) / (0.15 * (1 + grid))
            loss = 1 - 1 / (1 + residual * residual)
            return simpson(density * loss, x=grid)

        expected_best.append(
            minimize_scalar(
                risk, bounds=(grid[0], grid[-1]), method="bounded"
            ).x
        )
    assert np.allclose(best, expected_best, rtol=0, atol=2e-5), algorithm
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
