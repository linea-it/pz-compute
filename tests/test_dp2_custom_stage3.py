import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).parents[1]
PROJECT = ROOT / "doc/dp2_v3/custom/dnf_cmodel_griz_riz"
SCRIPT = PROJECT / "scripts/validate-hats.py"
QA_NOTEBOOK = PROJECT / "notebooks/dnf_cmodel_griz_riz_qa.ipynb"
QA_RENDERER = PROJECT / "notebooks/render-qa.sh"


def load_validator():
    spec = importlib.util.spec_from_file_location("test_custom_hats_validator", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_frame():
    return pd.DataFrame(
        {
            "objectId": [1, 2],
            "coord_ra": [10.0, 20.0],
            "coord_dec": [-10.0, 10.0],
            "dnf_z_mode": [0.4, 1.4],
            "dnf_z_mean": [0.5, 1.5],
            "dnf_z_median": [0.5, 1.5],
            "dnf_z_best": [0.48, 1.48],
            "dnf_z_err68_low": [0.3, 1.3],
            "dnf_z_err68_high": [0.7, 1.7],
            "dnf_z_err95_low": [0.1, 1.1],
            "dnf_z_err95_high": [0.9, 1.9],
            "DNF_ZN": [0.45, 1.55],
        }
    )


def test_partition_stats_accept_exact_scalar_contract():
    validator = load_validator()
    stats = validator.partition_stats(valid_frame())
    assert stats["rows"] == 2
    assert stats["coord_invalid"] == 0
    assert stats["interval_invalid"] == 0
    assert stats["grid_outside"] == 0
    assert not any(stats["nonfinite"].values())
    assert np.isclose(stats["zn_sum"], 2.0)


def test_partition_stats_detects_nonfinite_and_unordered_intervals():
    validator = load_validator()
    frame = valid_frame()
    frame.loc[0, "dnf_z_mean"] = np.nan
    frame.loc[1, "dnf_z_err95_low"] = 2.0
    stats = validator.partition_stats(frame)
    assert stats["nonfinite"]["dnf_z_mean"] == 1
    assert stats["partial_nonfinite_rows"] == 1
    assert stats["interval_invalid"] == 1


def test_partition_stats_accepts_all_nan_no_estimate_row():
    validator = load_validator()
    frame = valid_frame()
    frame.loc[0, list(validator.SCIENCE_COLUMNS)] = np.nan

    stats = validator.partition_stats(frame)

    assert stats["no_estimate_rows"] == 1
    assert stats["partial_nonfinite_rows"] == 0
    assert stats["interval_invalid"] == 0
    assert all(count == 1 for count in stats["nonfinite"].values())


def test_stage2_cross_check_bounds_pdf_mean_after_upper_edge_roundoff():
    validator = load_validator()
    xvals = np.linspace(0.0, 6.0, 601)
    yvals = np.exp(((xvals - 6.0) / 0.00026949024815046144))[None, :]

    mean = validator.bounded_pdf_mean(xvals, yvals)

    assert mean[0] == 6.0


def test_stage2_cross_check_uses_continuous_piecewise_linear_quantiles():
    validator = load_validator()
    xvals = np.linspace(0.0, 1.0, 101)
    yvals = np.ones((1, len(xvals)), dtype=np.float64)

    summary = validator.piecewise_linear_summaries(xvals, yvals)

    assert np.isclose(summary["mean"][0], 0.5)
    assert np.isclose(summary["median"][0], 0.5)
    assert np.isclose(summary["err68_low"][0], 0.16)
    assert np.isclose(summary["err68_high"][0], 0.84)
    assert np.isclose(summary["err95_low"][0], 0.025)
    assert np.isclose(summary["err95_high"][0], 0.975)


def test_stage2_cross_check_rejects_negative_and_all_nan_pdfs():
    validator = load_validator()
    xvals = np.linspace(0.0, 1.0, 101)
    yvals = np.vstack(
        [
            np.r_[np.ones(len(xvals) - 1), -1.0],
            np.full(len(xvals), np.nan),
        ]
    )

    summary = validator.piecewise_linear_summaries(xvals, yvals)

    assert all(np.isnan(values).all() for values in summary.values())


def test_stage2_cross_check_reconstructs_risk_based_best():
    validator = load_validator()
    xvals = np.linspace(0.0, 2.0, 201)
    yvals = np.exp(-0.5 * ((xvals - 0.73) / 0.04) ** 2)[None, :]

    best = validator.risk_based_best(xvals, yvals)

    assert abs(best[0] - 0.73) < 0.01


def test_pdf_named_product_is_rejected(tmp_path):
    validator = load_validator()
    hats = tmp_path / "scalar-hats"
    hats.mkdir()
    (tmp_path / "scalar-hats.pdf").mkdir()
    with pytest.raises(ValueError, match="PDF"):
        validator.reject_pdf_products(hats)


def test_stage3_runner_is_explicitly_scalar_only():
    runner = (PROJECT / "scripts/run-one-hats.sbatch").read_text()
    submitter = (PROJECT / "scripts/submit-hats.sh").read_text()
    assert "--pdf-layout=none" in runner
    assert "--summary-prefix=dnf" in runner
    assert "--summary-schema=rubin-dp2" in runner
    assert "--summary-dtype=float64" in runner
    assert "--summary-method=piecewise-linear" in runner
    assert "--require-complete-marker" in runner
    assert "--overwrite" not in runner
    assert "--delete-hdf5-outputs" not in runner
    assert 'printf \'git_commit=%s\\n\' "$PZ_COMPUTE_REVISION"' in runner
    assert "git -C" not in runner
    assert 'PZ_COMPUTE_REVISION=$(git -C "$PZ_COMPUTE_DIR" rev-parse HEAD)' in submitter
    assert 'PZ_COMPUTE_REVISION="$PZ_COMPUTE_REVISION"' in submitter


def test_delivery_qa_notebook_and_renderer_preserve_auditable_outputs():
    notebook = json.loads(QA_NOTEBOOK.read_text(encoding="utf-8"))
    rendered_text = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"]
    )
    renderer = QA_RENDERER.read_text(encoding="utf-8")

    assert notebook["nbformat"] == 4
    assert "dp2_clean_test_set.parquet" in rendered_text
    assert '"Flag 4": (4,), "Flags 3 and 4": (3, 4)' in rendered_text
    assert "PZ_QA_DASK_CLUSTER" in rendered_text
    assert 'PZ_QA_DASK_MINIMUM_JOBS\", \"48' in rendered_text
    assert 'PZ_QA_DASK_MAXIMUM_JOBS\", \"96' in rendered_text
    assert 'PZ_QA_DASK_CORES\", \"2' in rendered_text
    assert 'PZ_QA_DASK_MEMORY\", \"40GiB' in rendered_text
    assert 'os.environ.get(\"PZ_QA_DASK_INTERFACE\") or None' in rendered_text
    assert all(cell.get("id") for cell in notebook["cells"])
    assert "start_cluster" in rendered_text
    assert 'HIST_COLUMNS = ("dnf_z_best", "DNF_ZN")' in rendered_text
    assert "NMAD" in rendered_text
    assert "overflow-y:auto" in rendered_text
    assert "to_dask_dataframe" in rendered_text
    assert "qa_summary.json" in rendered_text
    assert "--execute" in renderer
    assert "--no-input" in renderer
    assert "dask_jobqueue" in renderer
    assert "SHA256SUMS" in renderer


def test_validation_record_captures_publication_contract(tmp_path):
    validator = load_validator()
    path = validator.write_validation_record(
        tmp_path,
        "griz",
        {
            "rows": 12,
            "columns": 12,
            "no_estimate_rows": 3,
            "margin_arcsec": 5.0,
        },
    )
    document = json.loads(path.read_text())
    assert document["project"] == "dp2_v3p1_custom"
    assert document["variant"] == "griz"
    assert document["rows"] == 12
    assert document["columns"] == list(validator.SUMMARY_COLUMNS)
    assert document["science_dtype"] == "float64"
    assert document["summary_method"] == "piecewise-linear"
    assert document["summary_schema"] == "rubin-dp2"
    assert document["pdf_layout"] == "none"
    assert document["no_photometry_policy"] == "nan"
    assert document["no_estimate_rows"] == 3
