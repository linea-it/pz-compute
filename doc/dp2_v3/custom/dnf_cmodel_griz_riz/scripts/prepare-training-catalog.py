#!/usr/bin/env python3
"""Build row-preserving cModel griz/riz DNF training tables."""

from __future__ import annotations

import argparse
import hashlib
from math import log
from pathlib import Path

import numpy as np
import pandas as pd
import tables_io


EXPECTED_SHA256 = "0c645457352446bfe9288b2b0d1e85577166f5ca8318c78dfb350453c349e511"
EXPECTED_ROWS = 554_676
LEGACY_SFD_A_EBV = {"g": 3.64, "r": 2.70, "i": 2.06, "z": 1.58}
AB_NJY_ZEROPOINT = 31.4
MAG_ERROR_FACTOR = 2.5 / log(10.0)
VARIANTS = {"griz": tuple("griz"), "riz": tuple("riz")}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def required_source_columns() -> list[str]:
    columns = ["redshift", "ebv"]
    for band in "griz":
        columns.extend(
            [
                f"{band}_cModelFlux",
                f"{band}_cModelFluxErr",
                f"{band}_cModelMag",
                f"{band}_cModelMagErr",
            ]
        )
    return columns


def validate_source(data: pd.DataFrame) -> None:
    if len(data) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} rows, received {len(data)}")
    redshift = data["redshift"].to_numpy(dtype=np.float64)
    if not np.isfinite(redshift).all():
        raise ValueError("reference redshift contains non-finite values")
    if not np.isclose(redshift.min(), 0.0010000000474974513):
        raise ValueError(f"unexpected minimum reference redshift: {redshift.min()}")
    if not np.isclose(redshift.max(), 9.975):
        raise ValueError(f"unexpected maximum reference redshift: {redshift.max()}")
    above_six = int(np.count_nonzero(redshift > 6.0))
    if above_six != 501:
        raise ValueError(f"expected 501 rows above redshift 6; received {above_six}")

    ebv = data["ebv"].to_numpy(dtype=np.float64)
    for band, coefficient in LEGACY_SFD_A_EBV.items():
        flux = data[f"{band}_cModelFlux"].to_numpy(dtype=np.float64)
        flux_error = data[f"{band}_cModelFluxErr"].to_numpy(dtype=np.float64)
        magnitude = data[f"{band}_cModelMag"].to_numpy(dtype=np.float64)
        magnitude_error = data[f"{band}_cModelMagErr"].to_numpy(dtype=np.float64)

        raw_magnitude = np.full(len(data), np.nan, dtype=np.float64)
        positive_flux = np.isfinite(flux) & (flux > 0)
        raw_magnitude[positive_flux] = (
            AB_NJY_ZEROPOINT - 2.5 * np.log10(flux[positive_flux])
        )
        expected_magnitude = raw_magnitude - coefficient * ebv
        comparable = np.isfinite(magnitude) & np.isfinite(expected_magnitude)
        if not np.allclose(
            magnitude[comparable], expected_magnitude[comparable], rtol=0, atol=1e-10
        ):
            difference = np.max(
                np.abs(magnitude[comparable] - expected_magnitude[comparable])
            )
            raise ValueError(
                f"{band} cModel magnitudes do not match the expected legacy "
                f"SFD correction; maximum difference={difference}"
            )

        expected_error = np.full(len(data), np.nan, dtype=np.float64)
        valid_error = positive_flux & np.isfinite(flux_error)
        expected_error[valid_error] = (
            MAG_ERROR_FACTOR * np.abs(flux_error[valid_error] / flux[valid_error])
        )
        comparable_error = np.isfinite(magnitude_error) & np.isfinite(expected_error)
        if not np.allclose(
            magnitude_error[comparable_error],
            expected_error[comparable_error],
            rtol=1e-14,
            atol=1e-12,
        ):
            raise ValueError(f"{band} cModel magnitude errors do not match source fluxes")


def variant_frame(data: pd.DataFrame, bands: tuple[str, ...]) -> pd.DataFrame:
    columns = ["redshift"]
    columns.extend(f"{band}_cModelMag" for band in bands)
    columns.extend(f"{band}_cModelMagErr" for band in bands)
    return data.loc[:, columns].copy()


def output_path(output_dir: Path, variant: str) -> Path:
    return output_dir / f"train_clipped_v3_cmodel_{variant}.hdf5"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="trusted clipped RTN-124 parquet")
    parser.add_argument("output_dir", type=Path, help="custom common/training directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    if not source.is_file():
        raise SystemExit(f"source parquet does not exist: {source}")
    digest = file_sha256(source)
    if digest != EXPECTED_SHA256:
        raise SystemExit(
            f"source SHA-256 mismatch: expected {EXPECTED_SHA256}, received {digest}"
        )

    targets = {name: output_path(output_dir, name) for name in VARIANTS}
    existing = [str(path) for path in targets.values() if path.exists()]
    if existing:
        raise SystemExit(f"refusing to overwrite existing outputs: {existing}")
    output_dir.mkdir(parents=True, exist_ok=True)

    data = pd.read_parquet(source, columns=required_source_columns())
    validate_source(data)

    for variant, bands in VARIANTS.items():
        target = targets[variant]
        temporary = output_dir / f".{target.stem}.inprogress.hdf5"
        if temporary.exists():
            raise SystemExit(f"stale temporary output exists: {temporary}")
        try:
            frame = variant_frame(data, bands)
            tables_io.write(frame, str(temporary))
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        print(f"wrote {variant}: {target} rows={len(frame)} columns={list(frame.columns)}")


if __name__ == "__main__":
    main()
