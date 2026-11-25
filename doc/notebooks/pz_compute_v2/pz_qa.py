"""Simple, scalable characterization of scalar columns in a HATS catalog.

The helper deliberately never projects nested columns. It reports catalog
metadata, scalar-column descriptive statistics, and configured redshift
histograms for the complete catalog and optional filtered samples.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
import json
import os
import warnings
from zoneinfo import ZoneInfo

import dask
from dask import delayed
from dask.distributed import Client, LocalCluster
import lsdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
import yaml


@dataclass
class QAResult:
    config: dict
    row_count: int
    partition_count: int
    columns: tuple[str, ...]
    nested_columns: tuple[str, ...]
    schema: pd.DataFrame
    describe: pd.DataFrame
    selection_counts: pd.DataFrame
    redshift_edges: np.ndarray
    redshift_histograms: dict[str, np.ndarray]
    spectroscopic_metrics: pd.DataFrame | None = None
    spectroscopic_pairs: dict[str, pd.DataFrame] | None = None


def load_config(path: str | Path) -> dict:
    """Load and validate one scalar-only HATS QA configuration."""
    path = Path(path).expanduser().resolve()
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a YAML mapping: {path}")

    config["_config_path"] = str(path)
    paths = config.setdefault("paths", {})
    for key in ("summary_hats", "report_dir", "spectroscopic_test_set"):
        value = paths.get(key)
        if value:
            expanded = Path(os.path.expandvars(os.path.expanduser(str(value))))
            if not expanded.is_absolute():
                expanded = path.parent / expanded
            paths[key] = str(expanded.resolve())
    if not paths.get("summary_hats"):
        raise ValueError("paths.summary_hats is required")

    redshift = config.setdefault("redshift", {})
    if not redshift.get("column"):
        raise ValueError("redshift.column is required")
    redshift.setdefault("minimum", 0.0)
    redshift.setdefault("maximum", 6.0)
    redshift.setdefault("bins", 120)
    z_min = float(redshift["minimum"])
    z_max = float(redshift["maximum"])
    bins = int(redshift["bins"])
    if not np.isfinite([z_min, z_max]).all() or z_min >= z_max:
        raise ValueError("redshift.minimum must be smaller than redshift.maximum")
    if bins < 1:
        raise ValueError("redshift.bins must be positive")

    selections = config.setdefault(
        "selections", [{"name": "all", "label": "All objects"}]
    )
    selections = [item for item in selections if item.get("enabled", True)]
    if not selections:
        raise ValueError("At least one selection must be enabled")
    names = [item["name"] for item in selections]
    if len(names) != len(set(names)):
        raise ValueError("Selection names must be unique")
    if not any(not item.get("filters") for item in selections):
        raise ValueError("At least one unfiltered selection is required")
    config["selections"] = selections

    percentiles = config.setdefault("describe", {}).setdefault(
        "percentiles", [0.25, 0.50, 0.75]
    )
    if any(not 0 < float(value) < 1 for value in percentiles):
        raise ValueError("describe.percentiles values must lie between zero and one")
    return config


def _format_filter(filter_config: dict) -> str:
    column = str(filter_config["column"])
    clauses = []
    if filter_config.get("finite", True):
        clauses.append(f"finite({column})")
    if "equals" in filter_config:
        clauses.append(f"{column} == {filter_config['equals']!r}")
    minimum = filter_config.get("minimum")
    maximum = filter_config.get("maximum")
    if minimum is not None and maximum is not None:
        clauses.append(f"{minimum:g} ≤ {column} < {maximum:g}")
    elif minimum is not None:
        clauses.append(f"{column} ≥ {minimum:g}")
    elif maximum is not None:
        clauses.append(f"{column} < {maximum:g}")
    return " and ".join(clauses) if clauses else f"configured values of {column}"


def selection_report(config: dict) -> pd.DataFrame:
    """Render configured samples without assigning extra scientific meaning."""
    rows = []
    for selection in config["selections"]:
        filters = selection.get("filters", [])
        rows.append(
            {
                "sample": selection.get("label", selection["name"]),
                "configured cut": (
                    "No additional cut (complete catalog)"
                    if not filters
                    else " and ".join(_format_filter(item) for item in filters)
                ),
                "description": selection.get("description", ""),
            }
        )
    return pd.DataFrame(rows).set_index("sample")


def start_cluster(config: dict):
    """Start the local, SLURM, or existing Dask client in the configuration."""
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

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Port 8787 is already in use.*",
                category=UserWarning,
                module=r"distributed\.node",
            )
            warnings.filterwarnings(
                "ignore",
                message=r"Couldn't detect a suitable IP address.*",
                category=RuntimeWarning,
                module=r"distributed\.utils",
            )
            cluster = SLURMCluster(
                n_workers=settings.get("minimum_jobs", 4)
                * settings.get("processes", 1),
                queue=settings.get("queue", "cpu"),
                account=settings.get("account", "hpc-public"),
                cores=settings.get("cores", 2),
                memory=settings.get("memory", "8GiB"),
                processes=settings.get("processes", 1),
                interface=settings.get("interface"),
                walltime=settings.get("walltime", "01:00:00"),
                job_extra_directives=settings.get(
                    "job_extra_directives", ["--propagate"]
                ),
            )
            client = None
            try:
                cluster.adapt(
                    minimum_jobs=settings.get("minimum_jobs", 4),
                    maximum_jobs=settings.get("maximum_jobs", 16),
                )
                client = Client(cluster)
                client.wait_for_workers(
                    settings.get("minimum_jobs", 4),
                    timeout=settings.get("wait_timeout", 300),
                )
            except BaseException:
                # Preserve the startup error while cleaning up submitted jobs.
                if client is not None:
                    with suppress(Exception):
                        client.close()
                with suppress(Exception):
                    cluster.close()
                raise
    elif cluster_type == "existing":
        address = settings.get("scheduler_address") or os.environ.get(
            "DASK_SCHEDULER_ADDRESS"
        )
        if not address:
            raise ValueError(
                "Set cluster.scheduler_address or DASK_SCHEDULER_ADDRESS"
            )
        client = Client(address)
    else:
        raise ValueError(f"Unsupported cluster.type: {cluster_type!r}")
    return client, cluster


def _read_hats_nrows(catalog) -> int:
    total_rows = catalog.hc_structure.catalog_info.total_rows
    if total_rows is None:
        raise ValueError("The HATS main catalog metadata does not define total_rows")
    return int(total_rows)


def _selection_columns(selections: list[dict]) -> list[str]:
    return sorted(
        {
            item["column"]
            for selection in selections
            for item in selection.get("filters", [])
        }
    )


def _selection_mask(frame: pd.DataFrame, selection: dict) -> np.ndarray:
    mask = np.ones(len(frame), dtype=bool)
    for filter_config in selection.get("filters", []):
        raw = frame[filter_config["column"]]
        numeric = pd.to_numeric(raw, errors="coerce").to_numpy(
            dtype=np.float64, na_value=np.nan
        )
        if filter_config.get("finite", True):
            mask &= np.isfinite(numeric)
        if "equals" in filter_config:
            equal = raw.eq(filter_config["equals"]).fillna(False).to_numpy(dtype=bool)
            mask &= equal
        if filter_config.get("minimum") is not None:
            mask &= numeric >= float(filter_config["minimum"])
        if filter_config.get("maximum") is not None:
            mask &= numeric < float(filter_config["maximum"])
    return mask


def _histogram_partition(
    frame: pd.DataFrame,
    selections: list[dict],
    redshift_column: str,
    edges: np.ndarray,
) -> dict[str, dict]:
    redshift = pd.to_numeric(frame[redshift_column], errors="coerce").to_numpy(
        dtype=np.float64, na_value=np.nan
    )
    finite = np.isfinite(redshift)
    in_range = finite & (redshift >= edges[0]) & (redshift <= edges[-1])
    result = {}
    for selection in selections:
        selected = _selection_mask(frame, selection)
        selected_finite = selected & finite
        selected_in_range = selected & in_range
        result[selection["name"]] = {
            "selected": int(selected.sum()),
            "finite_redshift": int(selected_finite.sum()),
            "nonfinite_redshift": int((selected & ~finite).sum()),
            "outside_range": int((selected_finite & ~in_range).sum()),
            "histogram": np.histogram(redshift[selected_in_range], bins=edges)[0],
        }
    return result


def _reduce_histograms(parts: list[dict], selections: list[dict]) -> dict:
    if not parts:
        return {
            item["name"]: {
                "selected": 0,
                "finite_redshift": 0,
                "nonfinite_redshift": 0,
                "outside_range": 0,
                "histogram": np.array([], dtype=np.int64),
            }
            for item in selections
        }
    result = {}
    for selection in selections:
        name = selection["name"]
        result[name] = {
            key: sum(part[name][key] for part in parts)
            for key in (
                "selected",
                "finite_redshift",
                "nonfinite_redshift",
                "outside_range",
            )
        }
        result[name]["histogram"] = np.sum(
            [part[name]["histogram"] for part in parts], axis=0, dtype=np.int64
        )
    return result


def _tree_reduce(tasks, selections, fan_in: int = 32):
    current = list(tasks)
    if not current:
        return delayed(_reduce_histograms)([], selections)
    while len(current) > 1:
        current = [
            delayed(_reduce_histograms)(current[index : index + fan_in], selections)
            for index in range(0, len(current), fan_in)
        ]
    return current[0]


def _schema_table(catalog, columns: list[str], nested: set[str]) -> pd.DataFrame:
    dtypes = catalog.dtypes
    if hasattr(dtypes, "items"):
        dtype_map = {str(name): str(dtype) for name, dtype in dtypes.items()}
    else:
        dtype_map = {name: "unknown" for name in columns}
    return pd.DataFrame(
        {
            "column": columns,
            "dtype": [dtype_map.get(name, "unknown") for name in columns],
            "nested (not read)": [name in nested for name in columns],
        }
    ).set_index("column")


def _describe_columns(config: dict, numeric_columns: list[str]) -> list[str]:
    """Apply optional case-insensitive substring filters to scalar columns."""
    contains = config.get("describe", {}).get("include_contains", [])
    if isinstance(contains, str):
        contains = [contains]
    needles = [str(value).casefold() for value in contains if str(value)]
    if not needles:
        return numeric_columns
    return [
        column
        for column in numeric_columns
        if any(needle in column.casefold() for needle in needles)
    ]


def _spectroscopic_samples(path: str | Path) -> dict[str, pd.Series]:
    reference = pd.read_parquet(
        path, columns=["objectId", "redshift", "instrument_type_homogenized", "z_flag_homogenized"]
    )
    valid = reference.loc[
        reference["instrument_type_homogenized"].eq("s")
        & reference["objectId"].notna()
        & np.isfinite(reference["redshift"])
        & (reference["redshift"] >= 0)
    ]
    samples = {}
    for label, flags in (("Flag 4", (4,)), ("Flags 3 + 4", (3, 4))):
        selected = valid.loc[valid["z_flag_homogenized"].isin(flags)]
        best_flag = selected.groupby("objectId")["z_flag_homogenized"].transform("max")
        best = selected.loc[selected["z_flag_homogenized"].eq(best_flag)]
        redshifts = best.groupby("objectId")["redshift"].agg(["min", "max", "median"])
        agrees = (redshifts["max"] - redshifts["min"]) <= 0.001 * (1 + redshifts["median"])
        samples[label] = redshifts.loc[agrees, "median"].rename("z_spec")
    return samples


def _spectroscopic_matches(frame, ids, redshift_column):
    return frame.loc[frame["objectId"].isin(ids), ["objectId", redshift_column]]


def _compare_spectroscopy(samples, matches, redshift_column):
    predictions = matches.set_index("objectId")[redshift_column].rename("z_phot")
    pairs = {}
    metrics = []
    for label, reference in samples.items():
        matched = reference.to_frame().join(predictions, how="inner", validate="one_to_one")
        finite = np.isfinite(matched["z_phot"].to_numpy(dtype=float, na_value=np.nan))
        pairs[label] = matched.loc[finite]
        dz = (pairs[label]["z_phot"] - pairs[label]["z_spec"]) / (1 + pairs[label]["z_spec"])
        bias = float(dz.median()) if len(dz) else np.nan
        metrics.append({
            "selection": label,
            "reference objects": len(reference),
            "matched in HATS": len(matched),
            "finite photo-z": len(dz),
            "median bias": bias,
            "NMAD": 1.4826 * float((dz - bias).abs().median()) if len(dz) else np.nan,
            "outlier fraction": float((dz.abs() > 0.15).mean()) if len(dz) else np.nan,
        })
    return pd.DataFrame(metrics).set_index("selection"), pairs


def run_qa(config: dict) -> QAResult:
    """Run scalar-only HATS characterization without projecting PDF columns."""
    catalog = lsdb.open_catalog(config["paths"]["summary_hats"], columns="all")
    columns = [str(name) for name in catalog.columns]
    nested_columns = {str(name) for name in catalog.nested_columns}
    scalar_columns = [name for name in columns if name not in nested_columns]
    row_count = _read_hats_nrows(catalog)

    redshift_column = str(config["redshift"]["column"])
    selection_columns = _selection_columns(config["selections"])
    required = {redshift_column, *selection_columns}
    reference_path = config["paths"].get("spectroscopic_test_set")
    if reference_path:
        required.add("objectId")
    missing = sorted(required - set(scalar_columns))
    if missing:
        raise KeyError(f"Missing scalar HATS columns: {missing}")

    catalog_dtypes = catalog.dtypes
    numeric_columns = [
        name
        for name in scalar_columns
        if name in catalog_dtypes.index and is_numeric_dtype(catalog_dtypes[name])
    ]
    if redshift_column not in numeric_columns:
        raise TypeError(f"Configured redshift column is not numeric: {redshift_column}")

    describe_columns = _describe_columns(config, numeric_columns)
    if not describe_columns:
        raise ValueError("No numeric scalar columns matched the describe configuration")

    histogram_columns = list(dict.fromkeys([redshift_column, *selection_columns]))
    if reference_path and "objectId" not in histogram_columns:
        histogram_columns.append("objectId")
    projected = set(describe_columns) | set(histogram_columns)
    projected_columns = [name for name in scalar_columns if name in projected]
    # Reopen with an explicit physical projection. Selecting columns only after
    # opening an all-column catalog can leave heavy nested fields in upstream
    # read tasks, causing avoidable worker-memory pressure before SelectColumns
    # runs. The first catalog remains metadata-only; this second catalog drives
    # the distributed scan and cannot read the PDF column.
    projected_catalog = lsdb.open_catalog(
        config["paths"]["summary_hats"], columns=projected_columns
    )
    scalar_ddf = projected_catalog.to_dask_dataframe()

    percentiles = [float(value) for value in config["describe"]["percentiles"]]
    # Dask percentile currently rejects pandas nullable numeric dtypes, and
    # unsigned integer means can overflow before division. A statistics-only
    # float64 projection avoids both problems; the schema table still reports
    # every original catalog dtype.
    describe_ddf = scalar_ddf[describe_columns].astype("float64")
    describe_task = describe_ddf.describe(percentiles=percentiles)

    z_min = float(config["redshift"]["minimum"])
    z_max = float(config["redshift"]["maximum"])
    bins = int(config["redshift"]["bins"])
    edges = np.linspace(z_min, z_max, bins + 1, dtype=np.float64)
    histogram_ddf = scalar_ddf[histogram_columns]
    histogram_parts = histogram_ddf.to_delayed()
    histogram_tasks = [
        delayed(_histogram_partition)(
            partition, config["selections"], redshift_column, edges
        )
        for partition in histogram_parts
    ]
    histogram_task = _tree_reduce(histogram_tasks, config["selections"])
    # Dask DataFrame expressions and delayed reductions use different graph
    # representations. Compute them separately to avoid materializing a mixed
    # graph on the client.
    describe_raw = describe_task.compute()
    spectroscopic_metrics = spectroscopic_pairs = None
    if reference_path:
        samples = _spectroscopic_samples(reference_path)
        ids = samples["Flag 4"].index.union(samples["Flags 3 + 4"].index).to_numpy()
        match_tasks = [
            delayed(_spectroscopic_matches)(part, ids, redshift_column)
            for part in histogram_parts
        ]
        histogram_result, *matches = dask.compute(histogram_task, *match_tasks)
        matched = pd.concat(matches, ignore_index=True) if matches else histogram_ddf._meta
        spectroscopic_metrics, spectroscopic_pairs = _compare_spectroscopy(
            samples, matched, redshift_column
        )
    else:
        histogram_result = dask.compute(histogram_task)[0]

    describe = describe_raw.T
    describe.insert(1, "null", row_count - describe["count"])
    describe.index.name = "column"

    labels = {
        item["name"]: item.get("label", item["name"])
        for item in config["selections"]
    }
    count_rows = []
    histograms = {}
    for selection in config["selections"]:
        name = selection["name"]
        values = histogram_result[name]
        count_rows.append(
            {
                "sample": labels[name],
                "selected rows": values["selected"],
                "retained fraction": (
                    values["selected"] / row_count if row_count else np.nan
                ),
                "finite redshift": values["finite_redshift"],
                "non-finite redshift": values["nonfinite_redshift"],
                "outside plotted range": values["outside_range"],
            }
        )
        histograms[name] = values["histogram"]

    return QAResult(
        config=config,
        row_count=row_count,
        partition_count=int(catalog.npartitions),
        columns=tuple(columns),
        nested_columns=tuple(sorted(nested_columns)),
        schema=_schema_table(catalog, columns, nested_columns),
        describe=describe,
        selection_counts=pd.DataFrame(count_rows).set_index("sample"),
        redshift_edges=edges,
        redshift_histograms=histograms,
        spectroscopic_metrics=spectroscopic_metrics,
        spectroscopic_pairs=spectroscopic_pairs,
    )


def columns_box(result: QAResult) -> str:
    """Return a compact, scrollable HTML list of all top-level columns."""
    nested = set(result.nested_columns)
    items = []
    for name in result.columns:
        suffix = " <em>nested — not read</em>" if name in nested else ""
        items.append(f"<li><code>{escape(name)}</code>{suffix}</li>")
    return (
        '<div style="max-height:320px; overflow-y:auto; '
        'border:1px solid var(--jp-border-color2, #888); border-radius:6px; '
        'padding:0.6rem 1rem; background:var(--jp-layout-color1, transparent); '
        'color:var(--jp-ui-font-color1, inherit)">'
        f"<ol style=\"margin:0; padding-left:1.5rem\">{''.join(items)}</ol></div>"
    )


def execution_metadata_html(
    config: dict, execution_time: datetime | None = None
) -> str:
    """Render author metadata with the execution date in the configured zone."""
    settings = config.get("report", {})
    timezone_name = settings.get("timezone", "America/Sao_Paulo")
    timezone = ZoneInfo(timezone_name)
    if execution_time is None:
        execution_time = datetime.now(timezone)
    elif execution_time.tzinfo is None:
        execution_time = execution_time.replace(tzinfo=timezone)
    else:
        execution_time = execution_time.astimezone(timezone)
    author = escape(str(settings.get("author", "Not specified")))
    contact = escape(str(settings.get("contact", "Not specified")))
    verified = execution_time.strftime("%B %d, %Y")
    return (
        f"Author: {author}<br>"
        f"Contact: {contact}<br>"
        f"Last verified execution: {verified}<br>"
    )


def plot_redshift_distributions(result: QAResult):
    """Plot global and filtered redshift counts plus normalized shapes."""
    edges = result.redshift_edges
    widths = np.diff(edges)
    figure, axes = plt.subplots(1, 2, figsize=(14, 4.8), constrained_layout=True)
    labels = {
        item["name"]: item.get("label", item["name"])
        for item in result.config["selections"]
    }
    for selection in result.config["selections"]:
        name = selection["name"]
        histogram = result.redshift_histograms[name]
        axes[0].stairs(histogram, edges, label=labels[name], linewidth=1.6)
        total = histogram.sum()
        density = histogram / (total * widths) if total else np.zeros_like(widths)
        axes[1].stairs(density, edges, label=labels[name], linewidth=1.6)

    redshift_column = result.config["redshift"]["column"]
    axes[0].set(title="Redshift distribution", xlabel=redshift_column, ylabel="Objects")
    axes[1].set(
        title="Normalized redshift distribution",
        xlabel=redshift_column,
        ylabel="Density",
    )
    for axis in axes:
        axis.grid(alpha=0.2)
        axis.legend(fontsize="small")
    return figure, axes


def plot_spectroscopic_comparison(result: QAResult):
    """Plot the configured photo-z estimate against the spectroscopic reference."""
    pairs = result.spectroscopic_pairs
    fig, axes = plt.subplots(1, len(pairs), figsize=(9, 4.5), layout="constrained")
    combined = pd.concat(pairs.values())
    lower = min(0.0, combined["z_phot"].min()) if len(combined) else 0.0
    upper = max(0.1, combined.max().max()) if len(combined) else 6.0
    for ax, (label, sample) in zip(axes, pairs.items()):
        ax.scatter(sample["z_spec"], sample["z_phot"], s=5, alpha=0.3, rasterized=True)
        ax.plot([lower, upper], [lower, upper], color="0.5", linewidth=1)
        ax.set(xlim=(lower, upper), ylim=(lower, upper), xlabel="Spectroscopic redshift",
               ylabel=result.config["redshift"]["column"], title=f"{label} (N={len(sample):,})")
        ax.set_aspect("equal", adjustable="box")
    return fig, axes


def write_report(result: QAResult) -> Path | None:
    """Write compact CSV/JSON tables when paths.report_dir is configured."""
    destination_value = result.config.get("paths", {}).get("report_dir")
    if not destination_value:
        return None
    destination = Path(destination_value)
    destination.mkdir(parents=True, exist_ok=True)
    result.schema.to_csv(destination / "schema.csv")
    result.describe.to_csv(destination / "describe.csv")
    result.selection_counts.to_csv(destination / "selection-counts.csv")
    if result.spectroscopic_metrics is not None:
        result.spectroscopic_metrics.to_csv(destination / "spectroscopic-metrics.csv")

    histogram = pd.DataFrame(
        {
            "z_left": result.redshift_edges[:-1],
            "z_right": result.redshift_edges[1:],
            **result.redshift_histograms,
        }
    )
    histogram.to_csv(destination / "redshift-histograms.csv", index=False)
    summary = {
        "run": result.config.get("run", {}),
        "catalog": result.config["paths"]["summary_hats"],
        "rows": result.row_count,
        "columns": len(result.columns),
        "partitions": result.partition_count,
        "redshift_column": result.config["redshift"]["column"],
        "nested_columns_not_read": list(result.nested_columns),
    }
    (destination / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return destination
