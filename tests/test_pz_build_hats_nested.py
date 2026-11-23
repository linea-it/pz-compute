from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import types

import numpy as np
import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "rail_scripts" / "pz-build-hats"
RUNNER = ROOT / "doc" / "dp2_v3" / "scripts" / "run-one-hats.sbatch"


def load_builder():
    pytest.importorskip("h5py")
    pytest.importorskip("pyarrow")
    pytest.importorskip("docopt")
    module_name = "testable_pz_build_hats"
    module = types.ModuleType(module_name)
    module.__file__ = str(SCRIPT)
    sys.modules[module_name] = module
    SourceFileLoader(module_name, str(SCRIPT)).exec_module(module)
    return module


def test_nested_pdf_array_matches_dp1_struct_of_lists_schema():
    builder = load_builder()
    xvals = np.linspace(0, 1, 4, dtype=np.float64)
    yvals = np.asarray([[0, 1, 2, 3], [3, 2, 1, 0]], dtype=np.float64)

    nested = builder.nested_pdf_array(xvals, yvals, "float32")

    assert nested.type.names == ["xvals", "yvals"]
    assert str(nested.type.field("xvals").type) == "list<item: float>"
    assert str(nested.type.field("yvals").type) == "list<item: float>"
    assert nested[0].as_py() == {
        "xvals": xvals.astype(np.float32).tolist(),
        "yvals": yvals[0].astype(np.float32).tolist(),
    }
    assert nested[1].as_py()["xvals"] == nested[0].as_py()["xvals"]


def test_dp2_stage3_runner_builds_nested_only_algorithm_column():
    source = RUNNER.read_text(encoding="utf-8")
    assert "--pdf-layout=nested" in source
    assert '--pdf-column="${PZ_ALGORITHM}_ens_interp"' in source
    assert "--summary-schema=rubin-dp2" in source
    assert '--summary-prefix="$PZ_ALGORITHM"' in source
    assert "--delete-hdf5-outputs" not in source
    assert '--slurm-job-name="$worker_job_name"' in source
    assert '--margin-threshold="$PZ_HATS_MARGIN_ARCSEC"' in source


def test_builder_configures_default_margin_for_both_hats_paths():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--margin-threshold=<arcsec>" in source
    assert "margin_threshold=cfg.margin_threshold" in source
    assert ").add_margin(" in source
    assert "is_default=True" in source


def test_legacy_summary_schema_remains_unchanged_by_default():
    builder = load_builder()
    xvals = np.linspace(0.0, 1.0, 101)
    yvals = np.ones((2, len(xvals)))

    summary = builder.summarize_pdf(xvals, yvals)

    assert list(summary) == ["zmode", "zmean", "zmedian", "z_p16", "z_p84"]
    assert builder.summary_column_names() == (
        "zmode", "zmean", "zmedian", "z_p16", "z_p84"
    )


def test_rubin_summary_schema_adds_named_68_and_95_percentiles():
    builder = load_builder()
    xvals = np.arange(101, dtype=np.float64) / 100.0
    yvals = np.ones((1, len(xvals)))

    summary = builder.summarize_pdf(
        xvals, yvals, prefix="dnf", include_95_interval=True
    )

    assert list(summary) == [
        "dnf_z_mean",
        "dnf_z_median",
        "dnf_z_mode",
        "dnf_z_err68_low",
        "dnf_z_err68_high",
        "dnf_z_err95_low",
        "dnf_z_err95_high",
    ]
    assert summary["dnf_z_err68_low"][0] == 0.16
    assert summary["dnf_z_err68_high"][0] == 0.84
    assert summary["dnf_z_err95_low"][0] == 0.02
    assert summary["dnf_z_err95_high"][0] == 0.98


def test_piecewise_linear_method_keeps_legacy_columns_and_float64():
    builder = load_builder()
    xvals = np.arange(101, dtype=np.float64) / 100.0
    yvals = np.ones((1, len(xvals)), dtype=np.float64)

    summary = builder.summarize_pdf(
        xvals,
        yvals,
        prefix="dnf",
        include_95_interval=True,
        summary_method="piecewise-linear",
    )

    assert list(summary) == [
        "dnf_z_mean",
        "dnf_z_median",
        "dnf_z_mode",
        "dnf_z_err68_low",
        "dnf_z_err68_high",
        "dnf_z_err95_low",
        "dnf_z_err95_high",
    ]
    assert all(values.dtype == np.float64 for values in summary.values())
    assert np.isclose(summary["dnf_z_mean"][0], 0.5)
    assert np.isclose(summary["dnf_z_median"][0], 0.5)
    assert np.isclose(summary["dnf_z_err68_low"][0], 0.16)
    assert np.isclose(summary["dnf_z_err68_high"][0], 0.84)
    assert np.isclose(summary["dnf_z_err95_low"][0], 0.025)
    assert np.isclose(summary["dnf_z_err95_high"][0], 0.975)


def test_piecewise_linear_method_rejects_invalid_pdf_rows():
    builder = load_builder()
    xvals = np.linspace(0.0, 1.0, 101)
    yvals = np.vstack(
        [
            np.full(len(xvals), np.nan),
            np.zeros(len(xvals)),
            np.r_[np.ones(len(xvals) - 1), -1.0],
        ]
    )

    summary = builder.summarize_pdf(
        xvals,
        yvals,
        prefix="dnf",
        include_95_interval=True,
        summary_method="piecewise-linear",
    )

    assert all(np.isnan(values).all() for values in summary.values())


def test_rubin_dp2_schema_has_continuous_summaries_and_float32_output():
    builder = load_builder()
    xvals = np.linspace(0.0, 1.0, 101)
    yvals = np.ones((1, len(xvals)))

    summary = builder.summarize_pdf(
        xvals,
        yvals,
        prefix="fzboost",
        summary_schema="rubin-dp2",
    )

    assert list(summary) == [
        "fzboost_z_mode",
        "fzboost_z_mean",
        "fzboost_z_median",
        "fzboost_z_best",
        "fzboost_z_err68_low",
        "fzboost_z_err68_high",
        "fzboost_z_err95_low",
        "fzboost_z_err95_high",
    ]
    assert builder.summary_column_names(
        "fzboost", summary_schema="rubin-dp2"
    ) == tuple(summary)
    assert all(values.dtype == np.float32 for values in summary.values())
    assert summary["fzboost_z_mode"][0] == 0.0
    assert np.isclose(summary["fzboost_z_mean"][0], 0.5)
    assert np.isclose(summary["fzboost_z_median"][0], 0.5)
    assert np.isclose(summary["fzboost_z_err68_low"][0], 0.16)
    assert np.isclose(summary["fzboost_z_err68_high"][0], 0.84)
    assert np.isclose(summary["fzboost_z_err95_low"][0], 0.025)
    assert np.isclose(summary["fzboost_z_err95_high"][0], 0.975)
    assert 0.0 <= summary["fzboost_z_best"][0] <= 1.0


def test_rubin_dp2_best_tracks_a_narrow_pdf_peak():
    builder = load_builder()
    xvals = np.linspace(0.0, 2.0, 201)
    yvals = np.exp(-0.5 * ((xvals - 0.73) / 0.04) ** 2)[None, :]

    summary = builder.summarize_pdf(
        xvals,
        yvals,
        prefix="fzboost",
        summary_schema="rubin-dp2",
    )

    assert abs(float(summary["fzboost_z_mode"][0]) - 0.73) <= 0.01
    assert abs(float(summary["fzboost_z_mean"][0]) - 0.73) < 1e-4
    assert abs(float(summary["fzboost_z_median"][0]) - 0.73) < 1e-4
    assert abs(float(summary["fzboost_z_best"][0]) - 0.73) < 0.01


def test_rubin_dp2_best_matches_rail_bounded_risk_definition():
    from scipy.integrate import simpson
    from scipy.optimize import minimize_scalar

    builder = load_builder()
    xvals = np.linspace(0.0, 3.0, 301)
    yvals = np.vstack(
        [
            np.exp(-0.5 * ((xvals - 0.4) / 0.08) ** 2),
            0.35 * np.exp(-0.5 * ((xvals - 0.5) / 0.12) ** 2)
            + np.exp(-0.5 * ((xvals - 1.8) / 0.25) ** 2),
            0.2 + np.exp(-0.5 * ((xvals - 2.5) / 0.4) ** 2),
        ]
    )

    actual = builder.risk_based_point_estimate(
        xvals, yvals, np.ones(len(yvals), dtype=bool), chunk_size=2
    )
    expected = []
    for density in yvals:

        def risk(candidate):
            residual = (candidate - xvals) / (0.15 * (1 + xvals))
            loss = 1 - 1 / (1 + residual * residual)
            return simpson(density * loss, x=xvals)

        expected.append(
            minimize_scalar(
                risk, bounds=(xvals[0], xvals[-1]), method="bounded"
            ).x
        )

    assert np.allclose(actual, expected, rtol=0, atol=2e-5)


def test_rubin_dp2_invalid_pdf_yields_all_nan_summaries():
    builder = load_builder()
    xvals = np.linspace(0.0, 1.0, 101)
    yvals = np.vstack(
        [
            np.full(len(xvals), np.nan),
            np.zeros(len(xvals)),
            np.r_[np.ones(len(xvals) - 1), -1.0],
        ]
    )

    summary = builder.summarize_pdf(
        xvals,
        yvals,
        prefix="fzboost",
        summary_schema="rubin-dp2",
    )

    assert all(np.isnan(values).all() for values in summary.values())


def test_rubin_summary_preserves_nan_for_rows_without_estimates():
    builder = load_builder()
    xvals = np.linspace(0.0, 1.0, 101)
    yvals = np.vstack([np.ones(len(xvals)), np.full(len(xvals), np.nan)])

    summary = builder.summarize_pdf(
        xvals, yvals, prefix="dnf", include_95_interval=True
    )

    for values in summary.values():
        assert np.isfinite(values[0])
        assert np.isnan(values[1])


def test_pdf_mean_is_bounded_to_grid_after_upper_edge_roundoff():
    builder = load_builder()
    xvals = np.linspace(0.0, 6.0, 601)
    yvals = np.exp(((xvals - 6.0) / 0.00026949024815046144))[None, :]

    unbounded = (yvals * xvals).sum(axis=1) / yvals.sum(axis=1)
    assert unbounded[0] == np.nextafter(6.0, np.inf)

    summary = builder.summarize_pdf(
        xvals, yvals, prefix="dnf", include_95_interval=True
    )

    assert summary["dnf_z_mean"][0] == 6.0
    assert all(values[0] <= 6.0 for values in summary.values())

