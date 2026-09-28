"""Photometric columns derived at estimation time.

This module deliberately has no RAIL dependency so its transformations can be
tested independently and reused by command-line front ends.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import log

import numpy as np


SFD_A_EBV = {
    "u": 4.81,
    "g": 3.64,
    "r": 2.70,
    "i": 2.06,
    "z": 1.58,
    "y": 1.31,
}
SFD_SUFFIX = "_sfd"
AB_NJY_ZEROPOINT = 31.4
MAG_ERROR_FACTOR = 2.5 / log(10.0)


def parse_column_list(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated list while retaining order and removing duplicates."""
    result = []
    seen = set()
    for raw_name in (value or "").split(","):
        name = raw_name.strip()
        if not name:
            continue
        if "/" in name:
            raise ValueError(f"column names cannot contain '/': {name}")
        if name not in seen:
            result.append(name)
            seen.add(name)
    return tuple(result)


def table_column_names(table) -> set[str]:
    columns = getattr(table, "columns", None)
    if columns is not None:
        return set(columns)
    if isinstance(table, Mapping):
        return set(table)
    raise TypeError(f"unsupported input table type: {type(table).__name__}")


def table_row_count(table) -> int:
    """Return a table row count without relying on column order."""
    columns = table_column_names(table)
    if not columns:
        return 0
    first = next(iter(columns))
    return len(table[first])


def _column(table, name: str) -> np.ndarray:
    return np.asarray(table[name])


def _set_column(table, name: str, values: np.ndarray) -> None:
    if not hasattr(table, "__setitem__"):
        raise TypeError(f"input table is not mutable: {type(table).__name__}")
    table[name] = values


def projected_input_columns(
    schema_names: Sequence[str],
    required_columns: Sequence[str],
    ebv_column: str,
) -> list[str]:
    """Choose only parquet fields needed to supply or derive requested columns."""
    available = set(schema_names)
    selected = []
    for name in required_columns:
        if name in available:
            candidates = (name,)
        elif name.endswith(SFD_SUFFIX):
            raw = name[: -len(SFD_SUFFIX)]
            if raw in available:
                candidates = (raw,)
            elif raw.endswith("MagErr"):
                prefix = raw[: -len("MagErr")]
                candidates = (f"{prefix}Flux", f"{prefix}FluxErr")
            elif raw.endswith("Mag"):
                prefix = raw[: -len("Mag")]
                candidates = (f"{prefix}Flux",)
            else:
                candidates = ()
        else:
            candidates = ()
        for candidate in candidates:
            if candidate in available and candidate not in selected:
                selected.append(candidate)
        if (
            name.endswith(f"Mag{SFD_SUFFIX}")
            and name not in available
            and ebv_column in available
            and ebv_column not in selected
        ):
            selected.append(ebv_column)
    return selected


def _band_from_column(column: str) -> str:
    band = column.split("_", 1)[0]
    if band not in SFD_A_EBV:
        raise ValueError(
            f"cannot infer an LSST band from derived SFD column: {column}"
        )
    return band


def _magnitude_from_flux(flux: np.ndarray) -> np.ndarray:
    flux = np.asarray(flux, dtype=np.float64)
    result = np.full(flux.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(flux) & (flux > 0)
    result[valid] = AB_NJY_ZEROPOINT - 2.5 * np.log10(flux[valid])
    return result


def _magnitude_error_from_flux(flux: np.ndarray, flux_error: np.ndarray) -> np.ndarray:
    flux = np.asarray(flux, dtype=np.float64)
    flux_error = np.asarray(flux_error, dtype=np.float64)
    result = np.full(np.broadcast_shapes(flux.shape, flux_error.shape), np.nan)
    valid = np.isfinite(flux) & np.isfinite(flux_error) & (flux > 0)
    result[valid] = MAG_ERROR_FACTOR * np.abs(flux_error[valid] / flux[valid])
    return result


def materialize_sfd_columns(table, columns: Sequence[str], ebv_column: str = "ebv") -> None:
    """Materialize requested SFD columns in place, computing each at most once.

    Magnitudes are corrected as ``mag_sfd = mag - R_band * E(B-V)``. Magnitude
    uncertainties retain their measured value because a deterministic
    foreground correction does not change the measurement uncertainty. If raw
    magnitude columns are absent, LSST fluxes in nJy are converted first.
    """
    for output_name in dict.fromkeys(columns):
        if not output_name.endswith(SFD_SUFFIX):
            continue
        names = table_column_names(table)
        if output_name in names:
            continue

        raw_name = output_name[: -len(SFD_SUFFIX)]
        band = _band_from_column(output_name)

        if raw_name.endswith("MagErr"):
            if raw_name in names:
                values = np.array(_column(table, raw_name), copy=True)
            else:
                prefix = raw_name[: -len("MagErr")]
                flux_name = f"{prefix}Flux"
                flux_error_name = f"{prefix}FluxErr"
                missing = [name for name in (flux_name, flux_error_name) if name not in names]
                if missing:
                    raise ValueError(
                        f"cannot derive {output_name}; missing input columns: {missing}"
                    )
                values = _magnitude_error_from_flux(
                    _column(table, flux_name), _column(table, flux_error_name)
                )
        elif raw_name.endswith("Mag"):
            if ebv_column not in names:
                raise ValueError(
                    f"cannot derive {output_name}; missing E(B-V) column: {ebv_column}"
                )
            if raw_name in names:
                magnitude = np.asarray(_column(table, raw_name), dtype=np.float64)
            else:
                prefix = raw_name[: -len("Mag")]
                flux_name = f"{prefix}Flux"
                if flux_name not in names:
                    raise ValueError(
                        f"cannot derive {output_name}; missing input columns: "
                        f"{raw_name} or {flux_name}"
                    )
                magnitude = _magnitude_from_flux(_column(table, flux_name))
            values = magnitude - SFD_A_EBV[band] * np.asarray(
                _column(table, ebv_column), dtype=np.float64
            )
        else:
            raise ValueError(
                f"unsupported generated column {output_name}; SFD columns must end "
                "in Mag_sfd or MagErr_sfd"
            )

        _set_column(table, output_name, values)


def copy_columns(table, columns: Sequence[str]) -> dict[str, np.ndarray]:
    """Copy selected columns before an estimator can mutate its input arrays."""
    names = table_column_names(table)
    missing = [name for name in columns if name not in names]
    if missing:
        raise ValueError(f"output columns are unavailable: {missing}")
    return {name: np.array(_column(table, name), copy=True) for name in columns}
