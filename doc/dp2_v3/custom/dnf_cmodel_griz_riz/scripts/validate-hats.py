#!/usr/bin/env python3
"""Validate scalar-only HATS products for the custom DNF cModel run."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path

import dask
from dask import delayed
import h5py
import lsdb
import numpy as np
import pyarrow.parquet as pq


PROJECT_DIR = Path(__file__).resolve().parent.parent
DP2_DOC_DIR = PROJECT_DIR.parents[1]
REPOSITORY_ROOT = DP2_DOC_DIR.parents[1]
VARIANTS = ("griz", "riz")
SUMMARY_COLUMNS = (
    "objectId",
    "coord_ra",
    "coord_dec",
    "dnf_z_mean",
    "dnf_z_median",
    "dnf_z_mode",
    "dnf_z_err68_low",
    "dnf_z_err68_high",
    "dnf_z_err95_low",
    "dnf_z_err95_high",
    "DNF_ZN",
)
SCIENCE_COLUMNS = SUMMARY_COLUMNS[3:]
GRID_COLUMNS = SCIENCE_COLUMNS[:-1]
DEFAULT_INPUT = Path(
    "/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset"
)
DEFAULT_MARGIN_ARCSEC = 5.0


def hats_dir(root: Path, variant: str) -> Path:
    name = f"pz-dnf-cmodel-{variant}-scalar-hats"
    return root / variant / "stage3/output" / name


def manifest_inputs(path: Path) -> list[Path]:
    result = [
        Path(line.strip())
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not result:
        raise ValueError(f"empty manifest: {path}")
    if len(result) != len(set(result)):
        raise ValueError(f"duplicate paths in manifest: {path}")
    return result


def _empty_stats() -> dict:
    return {
        "rows": 0,
        "coord_invalid": 0,
        "interval_invalid": 0,
        "grid_outside": 0,
        "no_estimate_rows": 0,
        "partial_nonfinite_rows": 0,
        "nonfinite": {name: 0 for name in SCIENCE_COLUMNS},
        "zn_sum": 0.0,
        "zn_sumsq": 0.0,
        "zn_min": math.inf,
        "zn_max": -math.inf,
        "sample": [],
    }


def partition_stats(frame, sample_ids=()) -> dict:
    result = _empty_stats()
    result["rows"] = len(frame)
    if not len(frame):
        return result

    ra = frame["coord_ra"].to_numpy(dtype=np.float64)
    dec = frame["coord_dec"].to_numpy(dtype=np.float64)
    result["coord_invalid"] = int(
        np.count_nonzero(
            ~np.isfinite(ra)
            | ~np.isfinite(dec)
            | (ra < 0.0)
            | (ra >= 360.0)
            | (dec < -90.0)
            | (dec > 90.0)
        )
    )

    values = {
        name: frame[name].to_numpy(dtype=np.float64) for name in SCIENCE_COLUMNS
    }
    science = np.column_stack([values[name] for name in SCIENCE_COLUMNS])
    no_estimate = np.isnan(science).all(axis=1)
    any_nonfinite = (~np.isfinite(science)).any(axis=1)
    result["no_estimate_rows"] = int(np.count_nonzero(no_estimate))
    result["partial_nonfinite_rows"] = int(
        np.count_nonzero(any_nonfinite & ~no_estimate)
    )
    for name, array in values.items():
        result["nonfinite"][name] = int(np.count_nonzero(~np.isfinite(array)))

    low95 = values["dnf_z_err95_low"]
    low68 = values["dnf_z_err68_low"]
    median = values["dnf_z_median"]
    high68 = values["dnf_z_err68_high"]
    high95 = values["dnf_z_err95_high"]
    ordered = (
        (low95 <= low68)
        & (low68 <= median)
        & (median <= high68)
        & (high68 <= high95)
    )
    result["interval_invalid"] = int(np.count_nonzero(~ordered & ~no_estimate))

    grid_values = np.column_stack([values[name] for name in GRID_COLUMNS])
    result["grid_outside"] = int(
        np.count_nonzero((grid_values < 0.0) | (grid_values > 6.0))
    )
    zn = values["DNF_ZN"]
    finite = zn[np.isfinite(zn)]
    if len(finite):
        result["zn_sum"] = float(np.sum(finite, dtype=np.float64))
        result["zn_sumsq"] = float(np.sum(np.square(finite), dtype=np.float64))
        result["zn_min"] = float(finite.min())
        result["zn_max"] = float(finite.max())
    if sample_ids:
        ids = frame["objectId"].to_numpy()
        selected = np.isin(ids, np.asarray(sample_ids))
        if np.any(selected):
            result["sample"] = frame.loc[selected, list(SUMMARY_COLUMNS)].to_dict(
                orient="records"
            )
    return result


def reduce_stats(parts: list[dict]) -> dict:
    result = _empty_stats()
    result["rows"] = sum(part["rows"] for part in parts)
    result["coord_invalid"] = sum(part["coord_invalid"] for part in parts)
    result["interval_invalid"] = sum(
        part["interval_invalid"] for part in parts
    )
    result["grid_outside"] = sum(part["grid_outside"] for part in parts)
    result["no_estimate_rows"] = sum(
        part["no_estimate_rows"] for part in parts
    )
    result["partial_nonfinite_rows"] = sum(
        part["partial_nonfinite_rows"] for part in parts
    )
    for name in SCIENCE_COLUMNS:
        result["nonfinite"][name] = sum(
            part["nonfinite"][name] for part in parts
        )
    result["zn_sum"] = math.fsum(part["zn_sum"] for part in parts)
    result["zn_sumsq"] = math.fsum(part["zn_sumsq"] for part in parts)
    populated = [part for part in parts if part["rows"]]
    if populated:
        result["zn_min"] = min(part["zn_min"] for part in populated)
        result["zn_max"] = max(part["zn_max"] for part in populated)
    result["sample"] = [row for part in parts for row in part["sample"]]
    return result


def hats_stats(catalog, sample_ids=()) -> dict:
    frame = catalog[list(SUMMARY_COLUMNS)].to_dask_dataframe()
    tasks = [
        delayed(partition_stats)(part, sample_ids) for part in frame.to_delayed()
    ]
    with dask.config.set(scheduler="threads", num_workers=2):
        return reduce_stats(list(dask.compute(*tasks)))


def stage2_stats(
    input_root: Path, output_root: Path, inputs: list[Path]
) -> dict:
    result = _empty_stats()
    sums = []
    sumsqs = []
    minima = []
    maxima = []
    for input_path in inputs:
        relative = input_path.relative_to(input_root)
        output_path = output_root / relative.with_suffix(".hdf5")
        if not output_path.is_file():
            raise FileNotFoundError(output_path)
        with h5py.File(output_path, "r") as handle:
            rows = handle["data/yvals"].shape[0]
            marker = handle["pz_compute"].attrs
            if not bool(marker.get("complete", False)):
                raise ValueError(f"incomplete Stage 2 output: {output_path}")
            if int(marker.get("row_count", -1)) != rows:
                raise ValueError(f"row marker differs in {output_path}")
            ancillary = handle["ancillary"]
            if set(ancillary) != {"DNF_ZN"}:
                raise ValueError(f"unexpected Stage 2 ancillary schema: {output_path}")
            dataset = ancillary["DNF_ZN"]
            if dataset.shape != (rows,):
                raise ValueError(f"DNF_ZN row count differs in {output_path}")
            result["rows"] += rows
            quality = handle["pz_compute/dnf_input_quality"].attrs
            if quality.get("no_photometry_policy", "") != "nan":
                raise ValueError(f"unexpected no-photometry policy: {output_path}")
            expected_nan = int(quality["no_usable_selected_band_rows"])
            pdf_quality = handle["pz_compute/dnf_pdf_quality"].attrs
            if int(pdf_quality["no_estimate_rows"]) != expected_nan:
                raise ValueError(f"Stage 2 no-estimate counters differ: {output_path}")
            result["no_estimate_rows"] += expected_nan
            actual_nan = 0
            for start in range(0, rows, 1_000_000):
                values = np.asarray(dataset[start : start + 1_000_000], dtype=np.float64)
                finite = values[np.isfinite(values)]
                actual_nan += int(np.count_nonzero(np.isnan(values)))
                if np.isinf(values).any():
                    raise ValueError(f"infinite Stage 2 DNF_ZN: {output_path}")
                sums.append(float(np.sum(finite, dtype=np.float64)))
                sumsqs.append(float(np.sum(np.square(finite), dtype=np.float64)))
                if len(finite):
                    minima.append(float(finite.min()))
                    maxima.append(float(finite.max()))
            if actual_nan != expected_nan:
                raise ValueError(f"Stage 2 DNF_ZN NaN count differs: {output_path}")
    result["zn_sum"] = math.fsum(sums)
    result["zn_sumsq"] = math.fsum(sumsqs)
    if minima:
        result["zn_min"] = min(minima)
        result["zn_max"] = max(maxima)
    return result


def weighted_quantile(xvals: np.ndarray, yvals: np.ndarray, q: float) -> np.ndarray:
    totals = yvals.sum(axis=1)
    cumulative = np.cumsum(yvals, axis=1)
    result = np.full(len(yvals), np.nan, dtype=np.float64)
    for index in np.flatnonzero(np.isfinite(totals) & (totals > 0)):
        position = np.searchsorted(
            cumulative[index], q * totals[index], side="left"
        )
        result[index] = xvals[min(position, len(xvals) - 1)]
    return result


def stage2_scalar_sample(
    input_root: Path, output_root: Path, inputs: list[Path], size: int = 8
) -> dict[int, dict[str, float]]:
    for input_path in inputs:
        relative = input_path.relative_to(input_root)
        output_path = output_root / relative.with_suffix(".hdf5")
        with h5py.File(output_path, "r") as handle:
            rows = handle["data/yvals"].shape[0]
            if rows == 0:
                continue
            indices = np.unique(
                np.linspace(0, rows - 1, min(size, rows), dtype=np.int64)
            )
            xvals = np.asarray(handle["meta/xvals"][0], dtype=np.float64)
            yvals = np.asarray(handle["data/yvals"][indices, :], dtype=np.float64)
            zn = np.asarray(handle["ancillary/DNF_ZN"][indices], dtype=np.float64)
        identifiers = (
            pq.ParquetFile(input_path)
            .read(columns=["objectId"])["objectId"]
            .combine_chunks()
            .to_numpy(zero_copy_only=False)[indices]
        )
        totals = yvals.sum(axis=1)
        valid = np.isfinite(totals) & (totals > 0)
        modes = np.full(len(yvals), np.nan, dtype=np.float64)
        modes[valid] = xvals[np.argmax(yvals[valid], axis=1)]
        means = np.full(len(yvals), np.nan, dtype=np.float64)
        means[valid] = (
            (yvals[valid] * xvals).sum(axis=1) / totals[valid]
        )
        values = {
            "dnf_z_mean": means,
            "dnf_z_median": weighted_quantile(xvals, yvals, 0.50),
            "dnf_z_mode": modes,
            "dnf_z_err68_low": weighted_quantile(xvals, yvals, 0.16),
            "dnf_z_err68_high": weighted_quantile(xvals, yvals, 0.84),
            "dnf_z_err95_low": weighted_quantile(xvals, yvals, 0.025),
            "dnf_z_err95_high": weighted_quantile(xvals, yvals, 0.975),
            "DNF_ZN": zn,
        }
        return {
            int(identifier): {
                name: float(array[index]) for name, array in values.items()
            }
            for index, identifier in enumerate(identifiers)
        }
    raise ValueError("cannot cross-check scalars because every Stage 2 shard is empty")


def validate_scalar_sample(
    variant: str,
    expected: dict[int, dict[str, float]],
    actual_rows: list[dict],
) -> None:
    actual = {int(row["objectId"]): row for row in actual_rows}
    if set(actual) != set(expected):
        raise ValueError(
            f"{variant}: scalar cross-check IDs differ: "
            f"expected={sorted(expected)}, actual={sorted(actual)}"
        )
    for identifier, expected_values in expected.items():
        for name, expected_value in expected_values.items():
            actual_value = float(actual[identifier][name])
            if not np.isclose(
                actual_value, expected_value, rtol=0, atol=1e-12, equal_nan=True
            ):
                raise ValueError(
                    f"{variant}: {name} differs for objectId={identifier}: "
                    f"{actual_value} != {expected_value}"
                )


def verify_checksum_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            expected, source = line.split("  ", 1)
        except ValueError as error:
            raise ValueError(f"invalid checksum record in {path}: {line}") from error
        source_path = Path(source)
        if digest(source_path) != expected:
            raise ValueError(f"checksum differs for {source_path}")


def validate_dtypes(catalog, variant: str) -> None:
    dtypes = catalog[list(SCIENCE_COLUMNS)].dtypes
    for name in SCIENCE_COLUMNS:
        dtype = dtypes[name]
        numpy_dtype = getattr(dtype, "numpy_dtype", dtype)
        if np.dtype(numpy_dtype) != np.dtype(np.float64):
            raise TypeError(f"{variant}: {name} has dtype {dtype}; expected float64")


def reject_pdf_products(path: Path) -> None:
    if list(path.parent.glob("*.pdf")):
        raise ValueError(f"unexpected companion PDF product beside {path}")
    for sibling in path.parent.iterdir():
        if sibling != path and "pdf" in sibling.name.lower():
            raise ValueError(f"unexpected PDF-named product: {sibling}")
    staging = Path(f"{path}.parquet_staging")
    if staging.exists():
        raise ValueError(f"temporary staging still exists: {staging}")


def validate_variant(
    root: Path,
    official_root: Path,
    input_root: Path,
    variant: str,
) -> dict:
    verify_checksum_file(root / variant / "stage2/production/READY")
    path = hats_dir(root, variant)
    reject_pdf_products(path)
    catalog = lsdb.open_catalog(path)
    if list(catalog.columns) != list(SUMMARY_COLUMNS):
        raise ValueError(
            f"{variant}: columns are {list(catalog.columns)}; "
            f"expected {list(SUMMARY_COLUMNS)}"
        )
    if catalog.nested_columns:
        raise ValueError(f"{variant}: unexpected nested columns {catalog.nested_columns}")
    validate_dtypes(catalog, variant)

    expected_margin = float(
        os.environ.get("PZ_HATS_MARGIN_ARCSEC", DEFAULT_MARGIN_ARCSEC)
    )
    if catalog.margin is None:
        raise ValueError(f"{variant}: default margin catalog is absent")
    actual_margin = catalog.margin.hc_structure.catalog_info.margin_threshold
    if not np.isclose(actual_margin, expected_margin):
        raise ValueError(
            f"{variant}: margin is {actual_margin}; expected {expected_margin}"
        )

    manifest = official_root / "common/manifests/input-parquet-files.txt"
    inputs = manifest_inputs(manifest)
    stage2_output = root / variant / "stage2/output"
    source = stage2_stats(input_root, stage2_output, inputs)
    expected_sample = stage2_scalar_sample(input_root, stage2_output, inputs)
    final = hats_stats(catalog, tuple(expected_sample))
    catalog_rows = len(catalog)
    if source["rows"] != catalog_rows or final["rows"] != catalog_rows:
        raise ValueError(
            f"{variant}: row counts differ: stage2={source['rows']}, "
            f"metadata={catalog_rows}, scanned={final['rows']}"
        )
    if final["coord_invalid"]:
        raise ValueError(f"{variant}: {final['coord_invalid']} invalid coordinates")
    if final["partial_nonfinite_rows"]:
        raise ValueError(
            f"{variant}: {final['partial_nonfinite_rows']} rows have partial or "
            "non-NaN non-finite science values"
        )
    if final["no_estimate_rows"] != source["no_estimate_rows"]:
        raise ValueError(
            f"{variant}: no-estimate rows differ: "
            f"stage2={source['no_estimate_rows']}, "
            f"HATS={final['no_estimate_rows']}"
        )
    bad_nonfinite = {
        name: count
        for name, count in final["nonfinite"].items()
        if count != final["no_estimate_rows"]
    }
    if bad_nonfinite:
        raise ValueError(
            f"{variant}: science NaN counts differ from the no-estimate policy: "
            f"{bad_nonfinite}"
        )
    if final["interval_invalid"]:
        raise ValueError(
            f"{variant}: {final['interval_invalid']} rows have unordered intervals"
        )
    if final["grid_outside"]:
        raise ValueError(
            f"{variant}: {final['grid_outside']} scalar values lie outside [0, 6]"
        )
    for name in ("zn_sum", "zn_sumsq", "zn_min", "zn_max"):
        if not np.isclose(source[name], final[name], rtol=1e-12, atol=1e-10):
            raise ValueError(
                f"{variant}: Stage 2/HATS {name} differs: "
                f"{source[name]} != {final[name]}"
            )
    validate_scalar_sample(variant, expected_sample, final["sample"])
    print(
        f"{variant}: valid scalar-only HATS "
        f"(rows={catalog_rows}, columns={len(SUMMARY_COLUMNS)}, "
        f"no_estimate_rows={final['no_estimate_rows']}, "
        f"margin_arcsec={actual_margin:g})"
    )
    return {
        "rows": catalog_rows,
        "columns": len(SUMMARY_COLUMNS),
        "no_estimate_rows": final["no_estimate_rows"],
        "margin_arcsec": float(actual_margin),
    }


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def ready_sources(root: Path, variant: str) -> list[Path]:
    return [
        root / variant / "stage2/production/READY",
        root / variant / "stage3/production/VALIDATION.json",
        REPOSITORY_ROOT / "rail_scripts/pz-build-hats",
        PROJECT_DIR / "scripts/run-one-hats.sbatch",
        Path(__file__).resolve(),
    ]


def write_validation_record(root: Path, variant: str, result: dict) -> Path:
    destination = root / variant / "stage3/production/VALIDATION.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name("VALIDATION.json.inprogress")
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite validation record: {destination}")
    document = {
        "schema_version": 2,
        "project": "dp2_v3p1_custom",
        "variant": variant,
        "collection": hats_dir(root, variant).name,
        "catalog_name": "pz_summary",
        "rows": result["rows"],
        "columns": list(SUMMARY_COLUMNS),
        "science_dtype": "float64",
        "pdf_layout": "none",
        "no_photometry_policy": "nan",
        "no_estimate_rows": result["no_estimate_rows"],
        "default_margin_arcsec": result["margin_arcsec"],
        "stage2_ready": str(
            (root / variant / "stage2/production/READY").resolve()
        ),
    }
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(destination)
    return destination


def write_ready(root: Path, variant: str) -> Path:
    destination = root / variant / "stage3/production/READY"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name("READY.inprogress")
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite validation marker: {destination}")
    lines = [f"{digest(path)}  {path.resolve()}\n" for path in ready_sources(root, variant)]
    temporary.write_text("".join(lines), encoding="utf-8")
    temporary.replace(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", choices=(*VARIANTS, "all"))
    parser.add_argument("--write-ready", action="store_true")
    args = parser.parse_args()
    try:
        root = Path(os.environ["PZ_DP2_CUSTOM_ROOT"])
        official_root = Path(os.environ["PZ_DP2_ROOT"])
    except KeyError as error:
        raise SystemExit(f"{error.args[0]} is not set") from error
    input_root = Path(os.environ.get("PZ_DP2_INPUT_DATASET", DEFAULT_INPUT))
    variants = VARIANTS if args.selection == "all" else (args.selection,)
    if args.write_ready:
        targets = [
            root / variant / "stage3/production" / name
            for variant in variants
            for name in ("READY", "VALIDATION.json")
        ]
        existing = [path for path in targets if path.exists()]
        if existing:
            raise FileExistsError(f"refusing to overwrite validation records: {existing}")
    results = {
        variant: validate_variant(root, official_root, input_root, variant)
        for variant in variants
    }
    if args.write_ready:
        for variant in variants:
            print(f"wrote: {write_validation_record(root, variant, results[variant])}")
        for variant in variants:
            print(f"wrote: {write_ready(root, variant)}")


if __name__ == "__main__":
    main()
