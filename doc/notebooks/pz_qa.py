"""Scalable, configuration-driven QA helpers for final photo-z products.

The public entry points are intentionally small so the companion notebook stays
readable: load_config, start_cluster, run_qa, plot_nz,
plot_zmean_selections, and write_report.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os

import dask
import dask.dataframe as dd
from dask import delayed
from dask.distributed import Client, LocalCluster
import lsdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml


POINT_COLUMNS = ("zmode", "zmean", "zmedian")
SUMMARY_COLUMNS = (
    "objectId", "coord_ra", "coord_dec", "zmode", "zmean", "zmedian",
    "z_p16", "z_p84",
)
UINT64_MASK = (1 << 64) - 1


@dataclass
class QAResult:
    config: dict
    paths: pd.Series
    grid: pd.Series
    grid_values: np.ndarray
    checks: pd.DataFrame
    global_metrics: pd.DataFrame
    pdf_metrics: pd.DataFrame
    pdf_health: pd.DataFrame
    distribution_distances: pd.DataFrame
    crosscheck: pd.DataFrame
    nz: dict[str, dict[str, np.ndarray]]


def load_config(path: str | Path) -> dict:
    """Load YAML, expand environment variables, and resolve relative paths."""
    path = Path(path).expanduser().resolve()
    with path.open() as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a YAML mapping: {path}")

    config["_config_path"] = str(path)
    for key in ("summary_hats", "pdf_dir", "report_dir"):
        value = config.get("paths", {}).get(key)
        if value:
            expanded = Path(os.path.expandvars(os.path.expanduser(str(value))))
            if not expanded.is_absolute():
                expanded = path.parent / expanded
            config["paths"][key] = str(expanded.resolve())

    selections = config.setdefault("selections", [{"name": "all", "label": "All objects"}])
    enabled = [item for item in selections if item.get("enabled", True)]
    if not enabled:
        raise ValueError("At least one selection must be enabled")
    names = [item["name"] for item in enabled]
    if len(names) != len(set(names)):
        raise ValueError("Selection names must be unique")
    config["selections"] = enabled
    return config


def start_cluster(config: dict):
    """Start the local/SLURM client described by the YAML configuration."""
    settings = config.get("cluster", {})
    cluster_type = settings.get("type", "local")
    cluster = None
    if cluster_type == "local":
        cluster = LocalCluster(
            n_workers=settings.get("n_workers", 2),
            threads_per_worker=settings.get("threads_per_worker", 1),
            memory_limit=settings.get("memory_limit", "2GiB"),
            processes=settings.get("processes", True),
            dashboard_address=settings.get("dashboard_address"),
        )
        client = Client(cluster)
    elif cluster_type == "slurm":
        from dask_jobqueue import SLURMCluster

        cluster = SLURMCluster(
            n_workers=settings.get("minimum_jobs", 5) * settings.get("processes", 1),
            queue=settings.get("queue", "cpu"),
            account=settings.get("account", "hpc-public"),
            cores=settings.get("cores", 8),
            memory=settings.get("memory", "16GB"),
            processes=settings.get("processes", 1),
            interface=settings.get("interface", "ib0"),
            walltime=settings.get("walltime", "01:00:00"),
            job_extra_directives=settings.get("job_extra_directives", ["--propagate"]),
        )
        cluster.adapt(
            minimum_jobs=settings.get("minimum_jobs", 5),
            maximum_jobs=settings.get("maximum_jobs", 10),
        )
        client = Client(cluster)
        client.wait_for_workers(
            settings.get("minimum_jobs", 5),
            timeout=settings.get("wait_timeout", 300),
        )
    elif cluster_type == "existing":
        address = settings.get("scheduler_address") or os.environ.get("DASK_SCHEDULER_ADDRESS")
        if not address:
            raise ValueError("Set cluster.scheduler_address or DASK_SCHEDULER_ADDRESS")
        client = Client(address)
    else:
        raise ValueError(f"Unsupported cluster.type: {cluster_type!r}")
    return client, cluster


def _read_hats_nrows(catalog) -> int:
    """Return the main catalog row count, never the collection plus margins."""
    total_rows = catalog.hc_structure.catalog_info.total_rows
    if total_rows is None:
        raise ValueError("The HATS main catalog metadata does not define total_rows")
    return int(total_rows)


def _selection_columns(selections: list[dict]) -> list[str]:
    return sorted({flt["column"] for item in selections for flt in item.get("filters", [])})


def _selection_mask(frame: pd.DataFrame, selection: dict) -> np.ndarray:
    mask = np.ones(len(frame), dtype=bool)
    for flt in selection.get("filters", []):
        values = pd.to_numeric(frame[flt["column"]], errors="coerce").to_numpy(
            dtype=np.float64, na_value=np.nan
        )
        if flt.get("finite", True):
            mask &= np.isfinite(values)
        if flt.get("minimum") is not None:
            mask &= values >= float(flt["minimum"])
        if flt.get("maximum") is not None:
            mask &= values < float(flt["maximum"])
    return mask


def _selection_masks(frame: pd.DataFrame, selections: list[dict]) -> dict[str, np.ndarray]:
    """Evaluate every configured sample once for a partition."""
    return {
        item["name"]: _selection_mask(frame, item)
        for item in selections
    }


def _id_digest(values: pd.Series) -> dict:
    missing = int(values.isna().sum())
    hashed = pd.util.hash_pandas_object(values.dropna(), index=False).to_numpy(dtype=np.uint64)
    if not len(hashed):
        return {"count": 0, "missing": missing, "sum": 0, "xor": 0, "sumsq": 0}
    squared = hashed * hashed
    return {
        "count": int(len(hashed)),
        "missing": missing,
        "sum": int(hashed.sum(dtype=np.uint64)),
        "xor": int(np.bitwise_xor.reduce(hashed)),
        "sumsq": int(squared.sum(dtype=np.uint64)),
    }


def _sample_mask(ids: pd.Series, probability: float) -> np.ndarray:
    if probability >= 1:
        return ids.notna().to_numpy()
    hashed = pd.util.hash_pandas_object(ids, index=False).to_numpy(dtype=np.uint64)
    threshold = np.uint64(max(1, int(probability * UINT64_MASK)))
    return ids.notna().to_numpy() & (hashed <= threshold)


def _empty_point_stats(n_bins: int) -> dict:
    return {
        "id": {"count": 0, "missing": 0, "sum": 0, "xor": 0, "sumsq": 0},
        "rows": 0,
        "coord_invalid": 0,
        "interval_invalid": 0,
        "interval_nonfinite": 0,
        "interval_outside": 0,
        "width_count": 0,
        "width_sum": 0.0,
        "width_sumsq": 0.0,
        "width_values": [],
        "points": {
            name: {
                "finite": 0, "inside": 0, "outside": 0, "lower_edge": 0,
                "upper_edge": 0, "low_z": 0, "sum": 0.0, "sumsq": 0.0,
                "hist": np.zeros(n_bins, dtype=np.int64),
            }
            for name in POINT_COLUMNS
        },
    }


def _summary_partition(
    frame,
    selections,
    edges,
    grid,
    low_z_threshold,
    sample_probability,
    selection_masks=None,
):
    if selection_masks is None:
        selection_masks = _selection_masks(frame, selections)
    result = {
        "id": _id_digest(frame["objectId"]),
        "selections": {},
        "sample": frame.loc[
            _sample_mask(frame["objectId"], sample_probability),
            ["objectId", *POINT_COLUMNS, "z_p16", "z_p84"],
        ].copy(),
    }
    for selection in selections:
        selected = frame.loc[selection_masks[selection["name"]]]
        stats = _empty_point_stats(len(grid))
        stats["id"] = _id_digest(selected["objectId"])
        stats["rows"] = len(selected)
        ra = pd.to_numeric(selected["coord_ra"], errors="coerce").to_numpy(dtype=np.float64, na_value=np.nan)
        dec = pd.to_numeric(selected["coord_dec"], errors="coerce").to_numpy(dtype=np.float64, na_value=np.nan)
        stats["coord_invalid"] = int(
            (~np.isfinite(ra) | ~np.isfinite(dec) | (ra < 0) | (ra >= 360) | (dec < -90) | (dec > 90)).sum()
        )
        p16 = pd.to_numeric(selected["z_p16"], errors="coerce").to_numpy(dtype=np.float64, na_value=np.nan)
        median = pd.to_numeric(selected["zmedian"], errors="coerce").to_numpy(dtype=np.float64, na_value=np.nan)
        p84 = pd.to_numeric(selected["z_p84"], errors="coerce").to_numpy(dtype=np.float64, na_value=np.nan)
        ordered_finite = np.isfinite(p16) & np.isfinite(median) & np.isfinite(p84)
        stats["interval_nonfinite"] = int((~ordered_finite).sum())
        stats["interval_invalid"] = int((ordered_finite & ((p16 > median) | (median > p84))).sum())
        stats["interval_outside"] = int((ordered_finite & ((p16 < grid[0]) | (p84 > grid[-1]))).sum())
        widths = (p84 - p16)[ordered_finite & (p84 >= p16)]
        stats["width_count"] = len(widths)
        stats["width_sum"] = float(widths.sum())
        stats["width_sumsq"] = float(np.square(widths).sum())
        # A deterministic bounded sample is enough for robust width quantiles.
        if len(widths):
            width_ids = selected.loc[ordered_finite & (p84 >= p16), "objectId"]
            stats["width_values"] = widths[_sample_mask(width_ids, sample_probability)].tolist()

        for name in POINT_COLUMNS:
            values = pd.to_numeric(selected[name], errors="coerce").to_numpy(dtype=np.float64, na_value=np.nan)
            finite_values = values[np.isfinite(values)]
            in_grid = (finite_values >= grid[0]) & (finite_values <= grid[-1])
            hist = np.histogram(finite_values[in_grid], bins=edges)[0]
            item = stats["points"][name]
            item.update(
                finite=len(finite_values),
                inside=int(hist.sum()),
                outside=int((~in_grid).sum()),
                lower_edge=int(hist[0]),
                upper_edge=int(hist[-1]),
                low_z=int((finite_values <= low_z_threshold).sum()),
                sum=float(finite_values.sum()),
                sumsq=float(np.square(finite_values).sum()),
                hist=hist,
            )
        result["selections"][selection["name"]] = stats
    return result


def _add_digest(target: dict, source: dict) -> None:
    for key in ("count", "missing", "sum", "sumsq"):
        target[key] = (target[key] + source[key]) & UINT64_MASK if key in ("sum", "sumsq") else target[key] + source[key]
    target["xor"] ^= source["xor"]


def _reduce_summary(parts, selections, n_bins):
    result = {
        "id": {"count": 0, "missing": 0, "sum": 0, "xor": 0, "sumsq": 0},
        "selections": {item["name"]: _empty_point_stats(n_bins) for item in selections},
        "sample": [],
    }
    for part in parts:
        _add_digest(result["id"], part["id"])
        result["sample"].append(part["sample"])
        for selection in selections:
            name = selection["name"]
            dst, src = result["selections"][name], part["selections"][name]
            _add_digest(dst["id"], src["id"])
            for key in ("rows", "coord_invalid", "interval_invalid", "interval_nonfinite", "interval_outside", "width_count"):
                dst[key] += src[key]
            for key in ("width_sum", "width_sumsq"):
                dst[key] += src[key]
            dst["width_values"].extend(src["width_values"])
            for column in POINT_COLUMNS:
                for key in (
                    "finite", "inside", "outside", "lower_edge", "upper_edge",
                    "low_z",
                ):
                    dst["points"][column][key] += src["points"][column][key]
                for key in ("sum", "sumsq"):
                    dst["points"][column][key] += src["points"][column][key]
                dst["points"][column]["hist"] += src["points"][column]["hist"]
    result["sample"] = pd.concat(result["sample"], ignore_index=True) if result["sample"] else pd.DataFrame()
    return result


def _empty_pdf_stats(n_bins: int) -> dict:
    return {
        "id": {"count": 0, "missing": 0, "sum": 0, "xor": 0, "sumsq": 0},
        "rows": 0, "valid": 0, "invalid": 0, "wrong_length": 0,
        "nonfinite": 0, "negative": 0, "nonpositive_sum": 0,
        "invalid_xvals": 0, "invalid_yvals_dtype": 0,
        "sum_count": 0, "sum_total": 0.0, "sum_sumsq": 0.0,
        "sum_min": np.inf, "sum_max": -np.inf, "sum_samples": [],
        "edge_mass_total": 0.0,
        "stack": np.zeros(n_bins, dtype=np.float64),
    }


def _pdf_summaries(matrix: np.ndarray, grid: np.ndarray) -> dict[str, np.ndarray]:
    totals = matrix.sum(axis=1)
    cdf = np.cumsum(matrix, axis=1)
    quantiles = {}
    for name, q in (("z_p16_pdf", 0.16), ("zmedian_pdf", 0.50), ("z_p84_pdf", 0.84)):
        indices = np.array([np.searchsorted(row, q * total, side="left") for row, total in zip(cdf, totals)])
        quantiles[name] = grid[np.minimum(indices, len(grid) - 1)]
    return {
        "zmode_pdf": grid[np.argmax(matrix, axis=1)],
        "zmean_pdf": (matrix * grid).sum(axis=1) / totals,
        **quantiles,
    }


def _pdf_partition(
    frame,
    selections,
    grid,
    batch_rows,
    sample_probability,
    edge_bins,
    selection_masks=None,
):
    result = {
        "id": _id_digest(frame["objectId"]),
        "selections": {item["name"]: _empty_pdf_stats(len(grid)) for item in selections},
        "sample": [],
    }
    if selection_masks is None:
        selection_masks = _selection_masks(frame, selections)
    for selection in selections:
        mask = selection_masks[selection["name"]]
        result["selections"][selection["name"]]["id"] = _id_digest(frame.loc[mask, "objectId"])
    ids = frame["objectId"].reset_index(drop=True)
    sample_rows = _sample_mask(ids, sample_probability)
    xvals_valid = frame.get(
        "_nested_xvals_valid", pd.Series(True, index=frame.index)
    ).to_numpy(dtype=bool)
    yvals_dtype_valid = frame.get(
        "_nested_yvals_dtype_valid", pd.Series(True, index=frame.index)
    ).to_numpy(dtype=bool)

    for start in range(0, len(frame), batch_rows):
        stop = min(start + batch_rows, len(frame))
        raw = frame["pdf"].iloc[start:stop].to_numpy()
        right_length = np.fromiter(
            (hasattr(value, "__len__") and len(value) == len(grid) for value in raw),
            dtype=bool, count=len(raw),
        )
        matrix = np.zeros((len(raw), len(grid)), dtype=np.float64)
        if right_length.any():
            try:
                matrix[right_length] = np.stack(raw[right_length]).astype(
                    np.float64, copy=False
                )
            except (TypeError, ValueError):
                # Preserve a diagnostic result even if an individual vector is
                # malformed instead of aborting the complete distributed QA.
                for index in np.flatnonzero(right_length):
                    try:
                        matrix[index] = np.asarray(raw[index], dtype=np.float64)
                    except (TypeError, ValueError):
                        right_length[index] = False
        finite = right_length & np.isfinite(matrix).all(axis=1)
        nonnegative = finite & (matrix >= 0).all(axis=1)
        sums = matrix.sum(axis=1)
        valid_structure = (
            xvals_valid[start:stop] & yvals_dtype_valid[start:stop]
        )
        positive = nonnegative & (sums > 0) & valid_structure

        for selection in selections:
            stats = result["selections"][selection["name"]]
            selected = selection_masks[selection["name"]][start:stop]
            valid = selected & positive
            stats["rows"] += int(selected.sum())
            stats["valid"] += int(valid.sum())
            stats["invalid"] += int((selected & ~positive).sum())
            stats["wrong_length"] += int((selected & ~right_length).sum())
            stats["nonfinite"] += int((selected & right_length & ~finite).sum())
            stats["negative"] += int((selected & finite & ~(matrix >= 0).all(axis=1)).sum())
            stats["nonpositive_sum"] += int((selected & nonnegative & ~(sums > 0)).sum())
            stats["invalid_xvals"] += int(
                (selected & ~xvals_valid[start:stop]).sum()
            )
            stats["invalid_yvals_dtype"] += int(
                (selected & ~yvals_dtype_valid[start:stop]).sum()
            )
            if valid.any():
                normalized = matrix[valid] / sums[valid, None]
                stats["stack"] += normalized.sum(axis=0)
                stats["edge_mass_total"] += float(
                    normalized[:, :edge_bins].sum() + normalized[:, -edge_bins:].sum()
                )
                valid_sums = sums[valid]
                stats["sum_count"] += len(valid_sums)
                stats["sum_total"] += float(valid_sums.sum())
                stats["sum_sumsq"] += float(np.square(valid_sums).sum())
                stats["sum_min"] = min(stats["sum_min"], float(valid_sums.min()))
                stats["sum_max"] = max(stats["sum_max"], float(valid_sums.max()))
                sampled_valid = valid & sample_rows[start:stop]
                stats["sum_samples"].extend(sums[sampled_valid].tolist())

        sampled_valid = positive & sample_rows[start:stop]
        if sampled_valid.any():
            summaries = _pdf_summaries(matrix[sampled_valid], grid)
            sample = pd.DataFrame({"objectId": ids.iloc[start:stop].to_numpy()[sampled_valid], **summaries})
            result["sample"].append(sample)

    result["sample"] = pd.concat(result["sample"], ignore_index=True) if result["sample"] else pd.DataFrame()
    return result


def _nested_pdf_partition(
    frame,
    pdf_column,
    selections,
    grid,
    batch_rows,
    sample_probability,
    edge_bins,
    selection_masks=None,
):
    """Adapt one LSDB NestedFrame partition to the common PDF QA reducer."""
    nested = frame[pdf_column]
    xvals, yvals = [], []
    for index in range(len(frame)):
        value = nested.iloc[index]
        try:
            xvals.append(value["xvals"])
            yvals.append(value["yvals"])
        except (KeyError, TypeError):
            xvals.append(None)
            yvals.append(None)

    xvals_valid = []
    yvals_dtype_valid = []
    reference_grid = np.asarray(grid, dtype=np.float32)
    for row_xvals, row_yvals in zip(xvals, yvals):
        row_grid = np.asarray(row_xvals) if row_xvals is not None else np.asarray([])
        row_pdf = np.asarray(row_yvals) if row_yvals is not None else np.asarray([])
        xvals_valid.append(
            row_grid.shape == grid.shape
            and row_grid.dtype == np.float32
            and np.array_equal(row_grid, reference_grid)
        )
        yvals_dtype_valid.append(row_pdf.dtype == np.float32)

    flat = pd.DataFrame(
        {
            "objectId": frame["objectId"].to_numpy(),
            **{
                column: frame[column].to_numpy()
                for column in _selection_columns(selections)
            },
            "pdf": yvals,
            "_nested_xvals_valid": xvals_valid,
            "_nested_yvals_dtype_valid": yvals_dtype_valid,
        }
    )
    return _pdf_partition(
        flat,
        selections,
        grid,
        batch_rows,
        sample_probability,
        edge_bins,
        selection_masks,
    )


def _nested_partition_bundle(
    frame,
    pdf_column,
    selections,
    edges,
    grid,
    low_z_threshold,
    batch_rows,
    sample_probability,
    edge_bins,
):
    """Reduce scalar and Nested-PDF QA from one physical partition read."""
    selection_masks = _selection_masks(frame, selections)
    return (
        _summary_partition(
            frame,
            selections,
            edges,
            grid,
            low_z_threshold,
            sample_probability,
            selection_masks,
        ),
        _nested_pdf_partition(
            frame,
            pdf_column,
            selections,
            grid,
            batch_rows,
            sample_probability,
            edge_bins,
            selection_masks,
        ),
    )


def _reduce_pdfs(parts, selections, n_bins):
    result = {
        "id": {"count": 0, "missing": 0, "sum": 0, "xor": 0, "sumsq": 0},
        "selections": {item["name"]: _empty_pdf_stats(n_bins) for item in selections},
        "sample": [],
    }
    for part in parts:
        _add_digest(result["id"], part["id"])
        if len(part["sample"]):
            result["sample"].append(part["sample"])
        for selection in selections:
            name = selection["name"]
            dst, src = result["selections"][name], part["selections"][name]
            _add_digest(dst["id"], src["id"])
            for key in (
                "rows", "valid", "invalid", "wrong_length", "nonfinite", "negative",
                "nonpositive_sum", "invalid_xvals", "invalid_yvals_dtype",
                "sum_count",
            ):
                dst[key] += src[key]
            for key in ("sum_total", "sum_sumsq", "edge_mass_total"):
                dst[key] += src[key]
            dst["sum_min"] = min(dst["sum_min"], src["sum_min"])
            dst["sum_max"] = max(dst["sum_max"], src["sum_max"])
            dst["sum_samples"].extend(src["sum_samples"])
            dst["stack"] += src["stack"]
    result["sample"] = pd.concat(result["sample"], ignore_index=True) if result["sample"] else pd.DataFrame()
    return result


def _moments(count: int, total: float, sumsq: float) -> tuple[float, float]:
    if not count:
        return np.nan, np.nan
    mean = total / count
    variance = max(0.0, sumsq / count - mean * mean)
    return mean, np.sqrt(variance)


def _hist_quantile(hist: np.ndarray, grid: np.ndarray, q: float) -> float:
    if hist.sum() == 0:
        return np.nan
    return float(grid[min(np.searchsorted(np.cumsum(hist), q * hist.sum(), side="left"), len(grid) - 1)])


def _id_equal(left: dict, right: dict) -> bool:
    return all(left[key] == right[key] for key in ("count", "missing", "sum", "xor", "sumsq"))


def _tree_reduce(tasks, reducer, selections, n_bins, split_every=32):
    """Reduce partition results on workers instead of gathering them all."""
    level = list(tasks)
    if not level:
        return delayed(reducer)([], selections, n_bins)
    while len(level) > 1:
        level = [
            delayed(reducer)(level[start:start + split_every], selections, n_bins)
            for start in range(0, len(level), split_every)
        ]
    return level[0]


def _crosscheck(summary: pd.DataFrame, pdf: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    if summary.empty or pdf.empty:
        return pd.DataFrame(columns=["compared", "median_abs_diff", "max_abs_diff", "fraction_over_tolerance"])
    merged = summary.merge(pdf, on="objectId", how="inner", validate="one_to_one")
    rows = []
    for column in ("zmode", "zmean", "zmedian", "z_p16", "z_p84"):
        delta = np.abs(merged[column].to_numpy(dtype=float) - merged[f"{column}_pdf"].to_numpy(dtype=float))
        finite = delta[np.isfinite(delta)]
        rows.append({
            "quantity": column,
            "compared": len(finite),
            "median_abs_diff": np.median(finite) if len(finite) else np.nan,
            "max_abs_diff": np.max(finite) if len(finite) else np.nan,
            "fraction_over_tolerance": float((finite > tolerance).mean()) if len(finite) else np.nan,
        })
    return pd.DataFrame(rows).set_index("quantity")


def run_qa(config: dict) -> QAResult:
    """Run scalable companion-Parquet or nested-HATS QA."""
    paths = config["paths"]
    summary_path = Path(paths["summary_hats"])
    if not summary_path.exists():
        raise FileNotFoundError(summary_path)
    # A collection root may contain the main catalog, margins, and indexes.
    # LSDB resolves the main catalog and attaches its default margin without
    # mixing margin rows into the main Dask dataframe.
    catalog = lsdb.open_catalog(summary_path)
    pdf_settings = config.get("pdf", {})
    pdf_layout = pdf_settings.get("layout", "companion")
    pdf_column = pdf_settings.get("column")
    pdf_dir = None
    pdf_files = []
    grid_index_detail = "nested xvals"
    nested_grid_dtype_valid = True

    if pdf_layout == "companion":
        pdf_dir = Path(paths["pdf_dir"])
        xvals_path = pdf_dir / paths.get("xvals_file", "xvals.parquet")
        for path in (pdf_dir, xvals_path):
            if not path.exists():
                raise FileNotFoundError(path)
        grid_table = pq.read_table(xvals_path)
        if "z" not in grid_table.column_names:
            raise KeyError(f"Missing z column in {xvals_path}")
        grid = grid_table.column("z").to_numpy().astype(float)
        grid_index_valid = (
            "bin_index" in grid_table.column_names
            and np.array_equal(
                grid_table.column("bin_index").to_numpy(),
                np.arange(
                    len(grid), dtype=grid_table.column("bin_index").to_numpy().dtype
                ),
            )
        )
        grid_index_detail = str(grid_table.column_names)
    elif pdf_layout == "nested":
        if not pdf_column:
            raise ValueError("pdf.column is required when pdf.layout is nested")
        if pdf_column not in catalog.nested_columns:
            raise KeyError(f"Missing nested PDF column: {pdf_column}")
        first = catalog[[pdf_column]].head(1)
        if first.empty:
            raise ValueError("The HATS catalog is empty")
        raw_grid = np.asarray(first[pdf_column].iloc[0]["xvals"])
        nested_grid_dtype_valid = raw_grid.dtype == np.float32
        grid = raw_grid.astype(float)
        grid_index_valid = True
    else:
        raise ValueError(f"Unsupported pdf.layout: {pdf_layout!r}")

    if len(grid) < 2 or not np.isfinite(grid).all() or not (np.diff(grid) > 0).all():
        raise ValueError("The redshift grid must contain at least two finite, increasing values")
    differences = np.diff(grid)
    expected = config.get("expected", {})
    expected_bins = expected.get("pdf_bins")
    expected_z_min = expected.get("z_min")
    expected_z_max = expected.get("z_max")
    edges = np.concatenate((
        [grid[0] - differences[0] / 2],
        (grid[:-1] + grid[1:]) / 2,
        [grid[-1] + differences[-1] / 2],
    ))

    selections = config["selections"]
    selection_columns = _selection_columns(selections)
    summary_columns = list(dict.fromkeys([*SUMMARY_COLUMNS, *selection_columns]))
    pdf_columns = list(dict.fromkeys(["objectId", "pdf", *selection_columns]))
    missing_summary = sorted(set(summary_columns) - set(catalog.columns))
    if missing_summary:
        raise KeyError(f"Missing HATS columns: {missing_summary}")

    expected_rows = _read_hats_nrows(catalog)
    metric_settings = config.get("metrics", {})
    # Project at the LSDB layer so the global scan never reads the large Nested
    # PDF column and Parquet can skip those pages entirely.
    summary_ddf = catalog[summary_columns].to_dask_dataframe()

    if pdf_layout == "companion":
        pdf_files = sorted(pdf_dir.glob(paths.get("pdf_glob", "*-pdf-part*.parquet")))
        if not pdf_files:
            raise FileNotFoundError(f"No PDF shards found under {pdf_dir}")
        first_schema = pq.ParquetFile(pdf_files[0]).schema_arrow
        required_pdf_columns = {"objectId", "coord_ra", "coord_dec", "pdf", *selection_columns}
        missing_pdf = sorted(required_pdf_columns - set(first_schema.names))
        if missing_pdf:
            raise KeyError(f"Missing PDF columns: {missing_pdf}")
        pdf_type = first_schema.field("pdf").type
        first_pdf_list_size = getattr(pdf_type, "list_size", None)
        pdf_ddf = dd.read_parquet(
            [str(path) for path in pdf_files],
            columns=pdf_columns,
            split_row_groups=True,
        )
        pdf_partitions_used = pdf_ddf.npartitions
    else:
        first_pdf_list_size = None
        max_pdf_partitions = int(metric_settings.get("max_pdf_partitions", 4))
        if max_pdf_partitions <= 0:
            raise ValueError("metrics.max_pdf_partitions must be positive")
        pdf_partitions_used = min(max_pdf_partitions, catalog.npartitions)
        nested_columns = list(dict.fromkeys(["objectId", *selection_columns, pdf_column]))
        combined_columns = list(dict.fromkeys([*summary_columns, *nested_columns]))
        combined_ddf = (
            catalog[combined_columns]
            .to_dask_dataframe()
            .partitions[:pdf_partitions_used]
        )
        pdf_ddf = combined_ddf[nested_columns]

    target_sample = int(metric_settings.get("crosscheck_sample_size", 10_000))
    if target_sample <= 0:
        raise ValueError("metrics.crosscheck_sample_size must be positive")
    global_sample_probability = min(1.0, target_sample / max(1, expected_rows))
    if pdf_layout == "nested":
        estimated_pdf_rows = (
            expected_rows * pdf_partitions_used / max(1, catalog.npartitions)
        )
        pdf_sample_probability = min(
            1.0, target_sample / max(1, estimated_pdf_rows)
        )
    else:
        pdf_sample_probability = global_sample_probability
    batch_rows = int(metric_settings.get("pdf_batch_rows", 10_000))
    edge_bins = int(metric_settings.get("pdf_edge_bins", 1))
    low_z_threshold = float(metric_settings.get("low_z_threshold", 0.1))
    if batch_rows <= 0:
        raise ValueError("metrics.pdf_batch_rows must be positive")
    if not 1 <= edge_bins <= len(grid) // 2:
        raise ValueError("metrics.pdf_edge_bins must be between 1 and half the grid size")
    if not grid[0] <= low_z_threshold <= grid[-1]:
        raise ValueError("metrics.low_z_threshold must lie inside the redshift grid")

    summary_tasks = [
        delayed(_summary_partition)(
            part,
            selections,
            edges,
            grid,
            low_z_threshold,
            global_sample_probability,
        )
        for part in summary_ddf.to_delayed()
    ]
    summary_task = _tree_reduce(
        summary_tasks, _reduce_summary, selections, len(grid)
    )

    if pdf_layout == "companion":
        pdf_tasks = [
            delayed(_pdf_partition)(
                part,
                selections,
                grid,
                batch_rows,
                pdf_sample_probability,
                edge_bins,
            )
            for part in pdf_ddf.to_delayed()
        ]
    else:
        # One delayed bundle per HATS partition guarantees that scalar and PDF
        # diagnostics reuse the same projected partition and the same masks.
        bundles = [
            delayed(_nested_partition_bundle)(
                part,
                pdf_column,
                selections,
                edges,
                grid,
                low_z_threshold,
                batch_rows,
                pdf_sample_probability,
                edge_bins,
            )
            for part in combined_ddf.to_delayed()
        ]
        pdf_summary_tasks = [bundle[0] for bundle in bundles]
        pdf_tasks = [bundle[1] for bundle in bundles]
        pdf_summary_task = _tree_reduce(
            pdf_summary_tasks, _reduce_summary, selections, len(grid)
        )
    pdf_task = _tree_reduce(pdf_tasks, _reduce_pdfs, selections, len(grid))
    exact_uniqueness = bool(metric_settings.get("exact_id_uniqueness", False))
    if pdf_layout == "companion":
        if exact_uniqueness:
            summary, pdf, summary_unique, pdf_unique = dask.compute(
                summary_task,
                pdf_task,
                summary_ddf["objectId"].nunique().to_delayed(),
                pdf_ddf["objectId"].nunique().to_delayed(),
            )
            summary_unique, pdf_unique = int(summary_unique), int(pdf_unique)
        else:
            summary, pdf = dask.compute(summary_task, pdf_task)
            summary_unique = pdf_unique = None
        pdf_summary = summary
    else:
        if exact_uniqueness:
            summary, pdf_summary, pdf, summary_unique, pdf_unique = dask.compute(
                summary_task,
                pdf_summary_task,
                pdf_task,
                summary_ddf["objectId"].nunique().to_delayed(),
                pdf_ddf["objectId"].nunique().to_delayed(),
            )
            summary_unique, pdf_unique = int(summary_unique), int(pdf_unique)
        else:
            summary, pdf_summary, pdf = dask.compute(
                summary_task, pdf_summary_task, pdf_task
            )
            summary_unique = pdf_unique = None

    metric_rows, pdf_metric_rows, health_rows, distance_rows = [], [], [], []
    nz = {}
    for selection in selections:
        name = selection["name"]
        label = selection.get("label", name)
        point_stats = summary["selections"][name]
        pdf_point_stats = pdf_summary["selections"][name]
        pdf_stats = pdf["selections"][name]
        nz[name] = {}
        for column in POINT_COLUMNS:
            values = point_stats["points"][column]
            mean, std = _moments(values["finite"], values["sum"], values["sumsq"])
            metric_rows.append({
                "selection": label, "estimator": column, "count": values["finite"],
                "mean": mean, "std": std,
                "p16": _hist_quantile(values["hist"], grid, 0.16),
                "median": _hist_quantile(values["hist"], grid, 0.50),
                "p84": _hist_quantile(values["hist"], grid, 0.84),
                "outside_grid_fraction": values["outside"] / max(1, values["finite"]),
                "low_z_fraction": values["low_z"] / max(1, values["finite"]),
                "lower_edge_fraction": values["lower_edge"] / max(1, values["finite"]),
                "upper_edge_fraction": values["upper_edge"] / max(1, values["finite"]),
                "edge_fraction": (values["lower_edge"] + values["upper_edge"]) / max(1, values["finite"]),
            })
            nz[name][column] = values["hist"].astype(float)
        stack = pdf_stats["stack"]
        if stack.sum():
            normalized_pdf = stack / stack.sum()
            pdf_mean = float((normalized_pdf * grid).sum())
            pdf_std = float(np.sqrt((normalized_pdf * np.square(grid - pdf_mean)).sum()))
            pdf_metric_rows.append({
                "selection": label, "estimator": "stacked_pdf", "count": pdf_stats["valid"],
                "mean": pdf_mean, "std": pdf_std,
                "p16": _hist_quantile(stack, grid, 0.16),
                "median": _hist_quantile(stack, grid, 0.50),
                "p84": _hist_quantile(stack, grid, 0.84),
                "outside_grid_fraction": 0.0,
                "low_z_fraction": float(normalized_pdf[grid <= low_z_threshold].sum()),
                "lower_edge_fraction": float(normalized_pdf[0]),
                "upper_edge_fraction": float(normalized_pdf[-1]),
                "edge_fraction": pdf_stats["edge_mass_total"] / max(1, pdf_stats["valid"]),
            })
            # Shape distances are meaningful only when both curves represent
            # exactly the same selected objects. Invalid PDFs, non-finite point
            # estimates, or point estimates outside the common grid are
            # reported by integrity checks instead of silently changing the
            # effective populations being compared here.
            populations_match = _id_equal(pdf_point_stats["id"], pdf_stats["id"])
            all_pdfs_valid = pdf_stats["valid"] == pdf_stats["rows"]
            for column in POINT_COLUMNS:
                point_stats_for_pdf_rows = pdf_point_stats["points"][column]
                point = point_stats_for_pdf_rows["hist"]
                all_points_valid = (
                    point_stats_for_pdf_rows["finite"] == pdf_point_stats["rows"]
                    and point_stats_for_pdf_rows["outside"] == 0
                )
                if (
                    populations_match
                    and all_pdfs_valid
                    and all_points_valid
                    and point.sum()
                ):
                    normalized_point = point / point.sum()
                    dz = np.diff(edges)
                    distance_rows.append({
                        "selection": label,
                        "point_estimate": column,
                        "total_variation": 0.5 * float(np.abs(normalized_point - normalized_pdf).sum()),
                        "wasserstein_z": float((np.abs(np.cumsum(normalized_point) - np.cumsum(normalized_pdf)) * dz).sum()),
                    })
        sum_mean, sum_std = _moments(pdf_stats["sum_count"], pdf_stats["sum_total"], pdf_stats["sum_sumsq"])
        sampled_sums = np.asarray(pdf_stats["sum_samples"])
        widths = np.asarray(point_stats["width_values"])
        health_rows.append({
            "selection": label,
            "HATS rows": point_stats["rows"],
            "PDF QA HATS rows": pdf_point_stats["rows"],
            "PDF rows": pdf_stats["rows"],
            "valid PDF fraction": pdf_stats["valid"] / max(1, pdf_stats["rows"]),
            "wrong length": pdf_stats["wrong_length"],
            "non-finite": pdf_stats["nonfinite"],
            "negative": pdf_stats["negative"],
            "non-positive sum": pdf_stats["nonpositive_sum"],
            "invalid nested xvals": pdf_stats["invalid_xvals"],
            "non-float32 nested yvals": pdf_stats["invalid_yvals_dtype"],
            "PDF sum mean": sum_mean,
            "PDF sum std": sum_std,
            "PDF sum min": pdf_stats["sum_min"] if pdf_stats["sum_count"] else np.nan,
            "PDF sum max": pdf_stats["sum_max"] if pdf_stats["sum_count"] else np.nan,
            "PDF sum p01 (sample)": np.quantile(sampled_sums, 0.01) if len(sampled_sums) else np.nan,
            "PDF sum median (sample)": np.median(sampled_sums) if len(sampled_sums) else np.nan,
            "PDF sum p99 (sample)": np.quantile(sampled_sums, 0.99) if len(sampled_sums) else np.nan,
            "interval width median (sample)": np.median(widths) if len(widths) else np.nan,
            "invalid coordinates": point_stats["coord_invalid"],
            "invalid intervals": point_stats["interval_invalid"],
            "non-finite intervals": point_stats["interval_nonfinite"],
            "intervals outside grid": point_stats["interval_outside"],
        })

    tolerance = float(config.get("thresholds", {}).get("summary_pdf_abs_tolerance", 1e-5))
    crosscheck = _crosscheck(pdf_summary["sample"], pdf["sample"], tolerance)
    unfiltered = [item["name"] for item in selections if not item.get("filters")]
    if not unfiltered:
        raise ValueError("One enabled selection without filters is required for product-level checks")
    all_name = unfiltered[0]
    all_summary = summary["selections"][all_name]
    thresholds = config.get("thresholds", {})
    max_bad_pdf = float(thresholds.get("max_invalid_pdf_fraction", 0.0))
    max_outside = float(thresholds.get("max_point_outside_fraction", 0.0))
    checks = [
        ("xvals are finite and strictly increasing", bool(np.isfinite(grid).all() and (differences > 0).all()), f"{len(grid)} bins"),
        ("xvals metadata is valid", grid_index_valid, grid_index_detail),
        ("expected PDF bin count", expected_bins is None or len(grid) == expected_bins, f"{len(grid)} / {expected_bins}"),
        ("expected redshift minimum", expected_z_min is None or np.isclose(grid[0], expected_z_min), f"{grid[0]} / {expected_z_min}"),
        ("expected redshift maximum", expected_z_max is None or np.isclose(grid[-1], expected_z_max), f"{grid[-1]} / {expected_z_max}"),
        ("global HATS rows match metadata", summary["id"]["count"] == expected_rows, f"observed={summary['id']['count']:,}; metadata={expected_rows:,}"),
        ("PDF-QA HATS and PDF row counts match", pdf_summary["id"]["count"] == pdf["id"]["count"], f"{pdf_summary['id']['count']:,} / {pdf['id']['count']:,}"),
        ("PDF-QA HATS and PDF objectId fingerprints match", _id_equal(pdf_summary["id"], pdf["id"]), "count + 3 commutative uint64 digests"),
        ("no missing objectId", summary["id"]["missing"] == 0 and pdf_summary["id"]["missing"] == 0 and pdf["id"]["missing"] == 0, f"global HATS={summary['id']['missing']:,}; PDF-QA HATS={pdf_summary['id']['missing']:,}; PDF={pdf['id']['missing']:,}"),
        ("coordinates are valid", all_summary["coord_invalid"] == 0, f"{all_summary['coord_invalid']:,} invalid"),
        ("credible intervals are finite and ordered", all_summary["interval_invalid"] + all_summary["interval_nonfinite"] == 0, f"{all_summary['interval_invalid']:,} unordered; {all_summary['interval_nonfinite']:,} non-finite"),
        ("credible intervals lie inside the redshift grid", all_summary["interval_outside"] == 0, f"{all_summary['interval_outside']:,} outside"),
    ]
    if pdf_layout == "nested":
        checks.append((
            "nested reference xvals use float32",
            nested_grid_dtype_valid,
            str(nested_grid_dtype_valid),
        ))
    else:
        checks.append((
            "companion PDF schema uses the expected list size",
            first_pdf_list_size == len(grid),
            f"{first_pdf_list_size} / {len(grid)}",
        ))
    if exact_uniqueness:
        checks.extend([
            ("global HATS objectId values are unique", summary_unique == summary["id"]["count"], f"{summary_unique:,} unique / {summary['id']['count']:,} non-null"),
            ("PDF-QA objectId values are unique", pdf_unique == pdf["id"]["count"], f"{pdf_unique:,} unique / {pdf['id']['count']:,} non-null"),
        ])
    max_nonfinite = float(thresholds.get("max_nonfinite_point_fraction", 0.0))
    for selection in selections:
        name = selection["name"]
        label = selection.get("label", name)
        selected_summary = summary["selections"][name]
        selected_pdf_summary = pdf_summary["selections"][name]
        selected_pdf = pdf["selections"][name]
        invalid_fraction = selected_pdf["invalid"] / max(1, selected_pdf["rows"])
        checks.extend([
            (f"[{label}] global selection is non-empty", selected_summary["rows"] > 0, f"{selected_summary['rows']:,} rows"),
            (f"[{label}] PDF-QA selection is non-empty", selected_pdf_summary["rows"] > 0, f"{selected_pdf_summary['rows']:,} rows"),
            (f"[{label}] PDF-QA HATS and PDF rows match", selected_pdf_summary["rows"] == selected_pdf["rows"], f"{selected_pdf_summary['rows']:,} / {selected_pdf['rows']:,}"),
            (f"[{label}] PDF-QA objectId fingerprints match", _id_equal(selected_pdf_summary["id"], selected_pdf["id"]), "count + 3 commutative uint64 digests"),
            (f"[{label}] PDF-QA invalid fraction within limit", invalid_fraction <= max_bad_pdf, f"{invalid_fraction:.3g} <= {max_bad_pdf:.3g}"),
        ])
        if pdf_layout == "nested":
            checks.extend([
                (
                    f"[{label}] PDF-QA nested xvals match the reference float32 grid",
                    selected_pdf["invalid_xvals"] == 0,
                    f"{selected_pdf['invalid_xvals']:,} invalid",
                ),
                (
                    f"[{label}] PDF-QA nested yvals use float32",
                    selected_pdf["invalid_yvals_dtype"] == 0,
                    f"{selected_pdf['invalid_yvals_dtype']:,} invalid",
                ),
                (
                    f"[{label}] PDF-QA nested yvals use the expected list size",
                    selected_pdf["wrong_length"] == 0,
                    f"{selected_pdf['wrong_length']:,} invalid",
                ),
            ])
        for column in POINT_COLUMNS:
            values = selected_summary["points"][column]
            outside_fraction = values["outside"] / max(1, values["finite"])
            nonfinite_fraction = (selected_summary["rows"] - values["finite"]) / max(1, selected_summary["rows"])
            checks.extend([
                (f"[{label}] {column} outside-grid fraction within limit", outside_fraction <= max_outside, f"{outside_fraction:.3g} <= {max_outside:.3g}"),
                (f"[{label}] {column} non-finite fraction within limit", nonfinite_fraction <= max_nonfinite, f"{nonfinite_fraction:.3g} <= {max_nonfinite:.3g}"),
            ])
    if not crosscheck.empty:
        checks.append((
            "PDF-QA sampled summaries reproduce HATS",
            bool((crosscheck["fraction_over_tolerance"] == 0).all()),
            f"n={int(crosscheck['compared'].min()):,}; tolerance={tolerance:g}",
        ))

    paths_report = pd.Series({
        "configuration": config["_config_path"],
        "HATS summary": str(summary_path),
        "PDF layout": pdf_layout,
        "PDF source": str(pdf_dir) if pdf_dir is not None else pdf_column,
        "PDF shards/partitions": len(pdf_files) if pdf_layout == "companion" else pdf_partitions_used,
        "HATS partitions": catalog.npartitions,
        "HATS partitions inspected for science metrics": catalog.npartitions,
        "HATS partitions inspected for PDF QA": (
            catalog.npartitions if pdf_layout == "companion" else pdf_partitions_used
        ),
        "exact objectId uniqueness": exact_uniqueness,
    }, name="value")
    grid_report = pd.Series({
        "bins": len(grid), "z minimum": grid[0], "z maximum": grid[-1],
        "minimum spacing": differences.min(), "maximum spacing": differences.max(),
        "low-z diagnostic threshold": low_z_threshold,
    }, name="value")
    distance_table = pd.DataFrame(distance_rows)
    if len(distance_table):
        distance_table = distance_table.set_index(["selection", "point_estimate"])
    else:
        distance_table = pd.DataFrame(
            columns=["total_variation", "wasserstein_z"],
            index=pd.MultiIndex.from_arrays([[], []], names=["selection", "point_estimate"]),
        )
    pdf_metrics_table = pd.DataFrame(pdf_metric_rows)
    if len(pdf_metrics_table):
        pdf_metrics_table = pdf_metrics_table.set_index(["selection", "estimator"])
    else:
        pdf_metrics_table = pd.DataFrame(
            columns=[
                "count", "mean", "std", "p16", "median", "p84",
                "outside_grid_fraction", "low_z_fraction",
                "lower_edge_fraction", "upper_edge_fraction", "edge_fraction",
            ],
            index=pd.MultiIndex.from_arrays(
                [[], []], names=["selection", "estimator"]
            ),
        )
    return QAResult(
        config=config,
        paths=paths_report,
        grid=grid_report,
        grid_values=grid.copy(),
        checks=pd.DataFrame(checks, columns=["check", "passed", "detail"]).set_index("check"),
        global_metrics=pd.DataFrame(metric_rows).set_index(["selection", "estimator"]),
        pdf_metrics=pdf_metrics_table,
        pdf_health=pd.DataFrame(health_rows).set_index("selection"),
        distribution_distances=distance_table,
        crosscheck=crosscheck,
        nz=nz,
    )


def _set_robust_y_range(axis, curves, grid, quantile, headroom):
    """Cap display range robustly and disclose every off-scale curve maximum."""
    positive_curves = [values[values > 0] for _, values in curves if np.any(values > 0)]
    if not positive_curves or quantile >= 1:
        return
    positive = np.concatenate(positive_curves)
    ceiling = float(np.quantile(positive, quantile))
    if not np.isfinite(ceiling) or ceiling <= 0:
        return
    display_max = ceiling * headroom
    off_scale = []
    for label, values in curves:
        index = int(np.argmax(values))
        peak = float(values[index])
        if peak > display_max:
            off_scale.append(f"{label}: {peak:.3g} at z={grid[index]:.3g}")
    if not off_scale:
        return
    axis.set_ylim(0, display_max)
    axis.text(
        0.99,
        0.72,
        "Off-scale peaks (retained in metrics):\n" + "\n".join(off_scale),
        transform=axis.transAxes,
        horizontalalignment="right",
        verticalalignment="top",
        fontsize=8,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "0.6", "alpha": 0.9},
    )


def _plot_grid(result: QAResult) -> np.ndarray:
    return np.asarray(result.grid_values)


def plot_nz(result: QAResult):
    """Plot counts and normalized N(z) for each configured selection."""
    grid = _plot_grid(result)
    selections = result.config["selections"]
    plot_settings = result.config.get("plots", {})
    ymax_quantile = float(plot_settings.get("nz_ymax_quantile", 0.995))
    ymax_headroom = float(plot_settings.get("nz_ymax_headroom", 1.10))
    if not 0 < ymax_quantile <= 1:
        raise ValueError("plots.nz_ymax_quantile must be in (0, 1]")
    if ymax_headroom <= 1:
        raise ValueError("plots.nz_ymax_headroom must be greater than 1")
    fig, axes = plt.subplots(len(selections), 2, figsize=(15, 4.5 * len(selections)), squeeze=False, constrained_layout=True)
    colors = {"zmode": "#0072B2", "zmean": "#D55E00", "zmedian": "#009E73"}
    for row, selection in enumerate(selections):
        name, label = selection["name"], selection.get("label", selection["name"])
        count_curves = []
        normalized_curves = []
        for estimator in POINT_COLUMNS:
            values = result.nz[name][estimator]
            curve_label = f"HATS {estimator}"
            axes[row, 0].step(grid, values, where="mid", label=curve_label, color=colors[estimator], linewidth=1.5)
            count_curves.append((curve_label, values))
            if values.sum():
                normalized = values / values.sum()
                axes[row, 1].plot(grid, normalized, label=curve_label, color=colors[estimator], linewidth=1.5)
                normalized_curves.append((curve_label, normalized))
        _set_robust_y_range(axes[row, 0], count_curves, grid, ymax_quantile, ymax_headroom)
        _set_robust_y_range(axes[row, 1], normalized_curves, grid, ymax_quantile, ymax_headroom)
        axes[row, 0].set(title=f"{label}: HATS point-estimate N(z)", xlabel="Photometric redshift", ylabel="Objects per bin")
        axes[row, 1].set(title=f"{label}: normalized global HATS estimates", xlabel="Photometric redshift", ylabel="Fraction per bin")
        axes[row, 0].legend()
        axes[row, 1].legend()
    return fig


def plot_zmean_selections(result: QAResult):
    """Plot one HATS zmean count distribution per configured science sample."""
    selections = result.config.get("selections", [])
    if not selections:
        raise ValueError("At least one configured selection is required")

    grid = _plot_grid(result)
    plot_settings = result.config.get("plots", {})
    ymax_quantile = float(plot_settings.get("nz_ymax_quantile", 0.995))
    ymax_headroom = float(plot_settings.get("nz_ymax_headroom", 1.10))
    if not 0 < ymax_quantile <= 1:
        raise ValueError("plots.nz_ymax_quantile must be in (0, 1]")
    if ymax_headroom <= 1:
        raise ValueError("plots.nz_ymax_headroom must be greater than 1")

    ncols = 2
    nrows = int(np.ceil(len(selections) / ncols))
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(15, 4.5 * nrows),
        sharex=True,
        squeeze=False,
        constrained_layout=True,
    )
    full_scan = (
        result.paths["HATS partitions inspected for science metrics"]
        == result.paths["HATS partitions"]
    )
    scope = "global" if full_scan else "bounded-partition"
    for axis, selection in zip(axes.flat, selections):
        name = selection["name"]
        if name not in result.nz:
            raise ValueError(f"Selection {name!r} is absent from QA results")
        label = selection.get("label", name)
        values = np.asarray(result.nz[name]["zmean"], dtype=float)
        curve_label = "HATS zmean"
        axis.step(
            grid,
            values,
            where="mid",
            color="#D55E00",
            linewidth=1.8,
            label=curve_label,
        )
        _set_robust_y_range(
            axis,
            [(curve_label, values)],
            grid,
            ymax_quantile,
            ymax_headroom,
        )
        axis.set(
            title=label,
            xlabel="Mean photometric redshift (zmean)",
            ylabel="Objects per bin",
        )
        axis.legend(title=f"N in plotted range = {int(values.sum()):,}")
    for axis in axes.flat[len(selections):]:
        axis.set_visible(False)
    fig.suptitle(f"{scope.capitalize()} zmean distributions by science sample")
    return fig


def write_report(result: QAResult) -> Path | None:
    """Optionally save compact CSV/JSON tables; never writes full catalog data."""
    value = result.config.get("paths", {}).get("report_dir")
    if not value:
        return None
    directory = Path(value)
    directory.mkdir(parents=True, exist_ok=True)
    result.checks.to_csv(directory / "checks.csv")
    result.global_metrics.to_csv(directory / "global_metrics.csv")
    result.pdf_metrics.to_csv(directory / "pdf_qa_metrics.csv")
    result.pdf_health.to_csv(directory / "pdf_health.csv")
    result.distribution_distances.to_csv(directory / "distribution_distances.csv")
    result.crosscheck.to_csv(directory / "summary_pdf_crosscheck.csv")
    compact = {
        "run": result.config.get("run", {}),
        "checks_passed": int(result.checks["passed"].sum()),
        "checks_total": len(result.checks),
    }
    (directory / "summary.json").write_text(json.dumps(compact, indent=2) + "\n")
    return directory
