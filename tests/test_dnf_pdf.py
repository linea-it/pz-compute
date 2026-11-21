import numpy as np
import pytest

from rail_scripts.dnf_pdf import (
    DNF_PDF_QUALITY_VERSION,
    DNFStablePdfTracker,
    stable_dnf_pdf_generation,
)


def direct_gaussian(photoz, photozerr, grid):
    z = np.asarray(photoz)[:, None]
    sigma = np.asarray(photozerr)[:, None]
    pdf = np.exp(-0.5 * ((grid - z) / sigma) ** 2)
    return pdf / np.trapezoid(pdf, grid, axis=1)[:, None]


def test_stable_pdf_matches_direct_gaussian_where_direct_formula_is_stable():
    grid = np.linspace(0.0, 6.0, 601)
    photoz = np.array([0.2, 1.5, 5.8])
    photozerr = np.array([0.1, 0.3, 0.2])

    tracker = DNFStablePdfTracker()
    actual = tracker.compute(photoz, photozerr, grid)

    np.testing.assert_allclose(
        actual,
        direct_gaussian(photoz, photozerr, grid),
        rtol=2e-13,
        atol=1e-14,
    )
    np.testing.assert_allclose(np.trapezoid(actual, grid, axis=1), 1.0)
    assert tracker.summary() == {
        "method": DNF_PDF_QUALITY_VERSION,
        "pdf_rows": 3,
        "nonfinite_dnf_z_rows": 0,
        "nonfinite_photozerr_rows": 0,
        "nonpositive_photozerr_rows": 0,
        "dnf_z_below_grid_rows": 0,
        "dnf_z_above_grid_rows": 0,
        "no_estimate_rows": 0,
        "legacy_gaussian_all_zero_rows": 0,
        "pdf_nonfinite_rows": 0,
        "pdf_nonpositive_integral_rows": 0,
        "pdf_bad_normalization_rows": 0,
        "pdf_mode_at_lower_grid_rows": 0,
        "pdf_mode_at_upper_grid_rows": 0,
        "zmin": 0.0,
        "zmax": 6.0,
    }


def test_stable_pdf_normalizes_gaussian_that_underflows_in_direct_formula():
    grid = np.linspace(0.0, 6.0, 601)
    tracker = DNFStablePdfTracker()

    pdf = tracker.compute(np.array([-0.30]), np.array([0.005]), grid)

    assert np.isfinite(pdf).all()
    np.testing.assert_allclose(np.trapezoid(pdf, grid, axis=1), 1.0)
    assert np.argmax(pdf[0]) == 0
    summary = tracker.summary()
    assert summary["dnf_z_below_grid_rows"] == 1
    assert summary["legacy_gaussian_all_zero_rows"] == 1
    assert summary["pdf_mode_at_lower_grid_rows"] == 1


def test_stable_pdf_handles_observed_extreme_fit_scales():
    grid = np.linspace(0.0, 6.0, 601)
    photoz = np.array([-6.30923721, -0.30283153, 9.58680578e12])
    photozerr = np.array([0.0302830661, 0.00479552469, 3.53417433e16])

    pdf = DNFStablePdfTracker().compute(photoz, photozerr, grid)

    assert np.isfinite(pdf).all()
    np.testing.assert_allclose(np.trapezoid(pdf, grid, axis=1), 1.0)


def test_legacy_underflow_counter_handles_narrow_fit_between_grid_points():
    grid = np.linspace(0.0, 6.0, 601)
    photoz = np.array([0.21461758])
    photozerr = np.array([9.35e-5])
    tracker = DNFStablePdfTracker()

    pdf = tracker.compute(photoz, photozerr, grid)

    assert np.isfinite(pdf).all()
    assert tracker.summary()["legacy_gaussian_all_zero_rows"] == 1
    assert np.exp(-0.5 * ((grid - photoz[0]) / photozerr[0]) ** 2).max() == 0


@pytest.mark.parametrize(
    ("photoz", "photozerr", "message"),
    [
        ([np.nan], [0.1], "nonfinite_DNF_Z=1"),
        ([0.2], [np.inf], "nonfinite_photozerr=1"),
        ([0.2], [0.0], "nonpositive_photozerr=1"),
        ([0.2], [-0.1], "nonpositive_photozerr=1"),
    ],
)
def test_stable_pdf_rejects_undefined_parameters(photoz, photozerr, message):
    tracker = DNFStablePdfTracker()

    with pytest.raises(ValueError, match=message):
        tracker.compute(photoz, photozerr, np.linspace(0.0, 6.0, 601))

    assert sum(
        tracker.summary()[name]
        for name in (
            "nonfinite_dnf_z_rows",
            "nonfinite_photozerr_rows",
            "nonpositive_photozerr_rows",
        )
    ) == 1


def test_stable_pdf_accumulates_quality_across_chunks():
    grid = np.linspace(0.0, 6.0, 601)
    tracker = DNFStablePdfTracker()

    tracker.compute(np.array([-0.1, 0.5]), np.array([0.1, 0.2]), grid)
    tracker.compute(np.array([5.5, 6.2]), np.array([0.2, 0.1]), grid)

    summary = tracker.summary()
    assert summary["pdf_rows"] == 4
    assert summary["dnf_z_below_grid_rows"] == 1
    assert summary["dnf_z_above_grid_rows"] == 1
    assert summary["pdf_mode_at_lower_grid_rows"] == 1
    assert summary["pdf_mode_at_upper_grid_rows"] == 1


def test_stable_pdf_context_is_scoped_and_restores_pinned_function():
    dnf_module = pytest.importorskip("rail.estimation.algos.dnf")
    original = dnf_module.compute_pdfs_fit
    grid = np.linspace(0.0, 6.0, 601)

    with stable_dnf_pdf_generation(0.0, 6.0) as tracker:
        assert dnf_module.compute_pdfs_fit.__self__ is tracker
        pdf = dnf_module.compute_pdfs_fit(
            np.array([-0.3]), np.array([0.005]), grid
        )
        assert np.isfinite(pdf).all()

    assert dnf_module.compute_pdfs_fit is original


def test_no_estimate_mask_allows_undefined_fit_and_returns_nan_pdf():
    grid = np.linspace(0.0, 6.0, 601)
    tracker = DNFStablePdfTracker(
        no_estimate_mask=np.array([False, True, True])
    )

    pdf = tracker.compute(
        np.array([0.5, np.nan, 0.2]),
        np.array([0.1, 0.0, -1.0]),
        grid,
    )
    tracker.assert_mask_consumed()

    assert np.isfinite(pdf[0]).all()
    assert np.isnan(pdf[1:]).all()
    assert tracker.summary()["no_estimate_rows"] == 2
    assert tracker.summary()["pdf_rows"] == 3
    assert tracker.summary()["nonpositive_photozerr_rows"] == 0
