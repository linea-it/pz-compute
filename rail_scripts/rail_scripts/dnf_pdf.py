"""Numerically stable DNF Gaussian PDFs and inexpensive quality accounting."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np


DNF_PDF_QUALITY_VERSION = "logspace-truncated-gaussian-v1"


@dataclass
class DNFStablePdfTracker:
    """Generate DNF PDFs and accumulate objective, per-row quality counters."""

    counters: dict[str, int] = field(
        default_factory=lambda: {
            "pdf_rows": 0,
            "nonfinite_dnf_z_rows": 0,
            "nonfinite_photozerr_rows": 0,
            "nonpositive_photozerr_rows": 0,
            "dnf_z_below_grid_rows": 0,
            "dnf_z_above_grid_rows": 0,
            "legacy_gaussian_all_zero_rows": 0,
            "pdf_nonfinite_rows": 0,
            "pdf_nonpositive_integral_rows": 0,
            "pdf_bad_normalization_rows": 0,
            "pdf_mode_at_lower_grid_rows": 0,
            "pdf_mode_at_upper_grid_rows": 0,
        }
    )
    zmin: float | None = None
    zmax: float | None = None

    def compute(self, photoz, photozerr, zgrid) -> np.ndarray:
        """Return the pinned DNF Gaussian on its grid using stable arithmetic.

        Subtracting the per-row maximum log density changes neither the
        normalized PDF nor its scientific inputs. It only prevents numerical
        underflow when the fitted redshift lies far outside the configured
        grid. Undefined fitted parameters remain hard failures.
        """
        z = np.asarray(photoz, dtype=np.float64)
        sigma = np.asarray(photozerr, dtype=np.float64)
        grid = np.asarray(zgrid, dtype=np.float64)

        if z.ndim != 1 or sigma.ndim != 1 or z.shape != sigma.shape:
            raise ValueError("DNF_Z and photozerr must be same-length vectors")
        if grid.ndim != 1 or len(grid) < 2:
            raise ValueError("DNF PDF grid must be a vector with at least two points")
        if not np.isfinite(grid).all() or not np.all(np.diff(grid) > 0):
            raise ValueError("DNF PDF grid must be finite and strictly increasing")

        nonfinite_z = ~np.isfinite(z)
        nonfinite_sigma = ~np.isfinite(sigma)
        nonpositive_sigma = np.isfinite(sigma) & (sigma <= 0)
        invalid = nonfinite_z | nonfinite_sigma | nonpositive_sigma
        if invalid.any():
            self.counters["nonfinite_dnf_z_rows"] += int(nonfinite_z.sum())
            self.counters["nonfinite_photozerr_rows"] += int(
                nonfinite_sigma.sum()
            )
            self.counters["nonpositive_photozerr_rows"] += int(
                nonpositive_sigma.sum()
            )
            raise ValueError(
                "undefined DNF Gaussian parameters: "
                f"rows={int(invalid.sum())}, "
                f"nonfinite_DNF_Z={int(nonfinite_z.sum())}, "
                f"nonfinite_photozerr={int(nonfinite_sigma.sum())}, "
                f"nonpositive_photozerr={int(nonpositive_sigma.sum())}"
            )

        self._set_or_check_grid(float(grid[0]), float(grid[-1]))
        if len(z) == 0:
            return np.empty((0, len(grid)), dtype=np.float64)

        # The closest grid point has maximum Gaussian density. Express every
        # exponent relative to it using the difference-of-squares identity;
        # this preserves a finite zero log weight at the peak even when the
        # unshifted Gaussian would underflow everywhere on the grid.
        right = np.searchsorted(grid, z, side="left")
        right = np.clip(right, 0, len(grid) - 1)
        left = np.clip(right - 1, 0, len(grid) - 1)
        use_left = np.abs(z - grid[left]) <= np.abs(grid[right] - z)
        peak_index = np.where(use_left, left, right)
        peak = grid[peak_index]

        # Reconstruct the precise all-zero underflow mechanism in the pinned
        # direct implementation without evaluating another rows-by-grid array.
        # If exp(exponent) is zero even at the closest grid point, it is zero
        # at every grid point and the legacy numerical integral is zero.
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            legacy_peak_exponent = -0.5 * ((peak - z) / sigma) ** 2
            legacy_peak = np.exp(legacy_peak_exponent)
        self.counters["legacy_gaussian_all_zero_rows"] += int(
            np.count_nonzero(legacy_peak == 0)
        )

        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            log_pdf = (grid[None, :] - peak[:, None]) / sigma[:, None]
            second = (
                grid[None, :] + peak[:, None] - 2.0 * z[:, None]
            ) / sigma[:, None]
            log_pdf *= second
            log_pdf *= -0.5
        del second
        log_pdf[np.arange(len(z)), peak_index] = 0.0

        row_max = np.max(log_pdf, axis=1)
        invalid_log = ~np.isfinite(row_max)
        if invalid_log.any():
            self.counters["pdf_nonfinite_rows"] += int(invalid_log.sum())
            raise ValueError(
                "stable DNF log-PDF is undefined for "
                f"{int(invalid_log.sum())} rows"
            )
        log_pdf -= row_max[:, None]

        with np.errstate(under="ignore", invalid="ignore"):
            np.exp(log_pdf, out=log_pdf)
        pdf = log_pdf
        nonfinite_pdf = ~np.isfinite(pdf).all(axis=1)
        if nonfinite_pdf.any():
            self.counters["pdf_nonfinite_rows"] += int(nonfinite_pdf.sum())
            raise ValueError(
                "stable DNF PDF contains non-finite values in "
                f"{int(nonfinite_pdf.sum())} rows"
            )

        integrals = np.trapezoid(pdf, grid, axis=1)
        invalid_integral = ~np.isfinite(integrals) | (integrals <= 0)
        if invalid_integral.any():
            self.counters["pdf_nonpositive_integral_rows"] += int(
                invalid_integral.sum()
            )
            raise ValueError(
                "stable DNF PDF has a non-positive or non-finite integral in "
                f"{int(invalid_integral.sum())} rows"
            )
        pdf /= integrals[:, None]

        normalized = np.trapezoid(pdf, grid, axis=1)
        bad_normalization = ~np.isfinite(normalized) | ~np.isclose(
            normalized, 1.0, rtol=1e-10, atol=1e-12
        )
        if bad_normalization.any():
            self.counters["pdf_bad_normalization_rows"] += int(
                bad_normalization.sum()
            )
            raise ValueError(
                "stable DNF PDF normalization failed for "
                f"{int(bad_normalization.sum())} rows"
            )

        modes = np.argmax(pdf, axis=1)
        self.counters["pdf_rows"] += len(z)
        self.counters["dnf_z_below_grid_rows"] += int((z < grid[0]).sum())
        self.counters["dnf_z_above_grid_rows"] += int((z > grid[-1]).sum())
        self.counters["pdf_mode_at_lower_grid_rows"] += int((modes == 0).sum())
        self.counters["pdf_mode_at_upper_grid_rows"] += int(
            (modes == len(grid) - 1).sum()
        )
        return pdf

    def _set_or_check_grid(self, zmin: float, zmax: float) -> None:
        if self.zmin is None:
            self.zmin = zmin
            self.zmax = zmax
        elif self.zmin != zmin or self.zmax != zmax:
            raise ValueError("DNF PDF grid changed between estimator chunks")

    def summary(self) -> dict[str, str | float | int]:
        result: dict[str, str | float | int] = {
            "method": DNF_PDF_QUALITY_VERSION,
            **self.counters,
        }
        if self.zmin is not None:
            result["zmin"] = self.zmin
            result["zmax"] = self.zmax
        return result


@contextmanager
def stable_dnf_pdf_generation(zmin: float | None = None, zmax: float | None = None):
    """Temporarily install stable PDF generation in the pinned DNF module."""
    import rail.estimation.algos.dnf as dnf_module

    if (zmin is None) != (zmax is None):
        raise ValueError("both zmin and zmax are required when initializing a grid")
    tracker = DNFStablePdfTracker(
        zmin=None if zmin is None else float(zmin),
        zmax=None if zmax is None else float(zmax),
    )
    original = dnf_module.compute_pdfs_fit
    dnf_module.compute_pdfs_fit = tracker.compute
    try:
        yield tracker
    finally:
        dnf_module.compute_pdfs_fit = original
