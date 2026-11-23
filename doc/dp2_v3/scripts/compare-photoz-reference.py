#!/usr/bin/env python3
"""Compare an authorized FlexZBoost reference with local Stage 3 output."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


SCIENCE_COLUMNS = [
    "fzboost_z_mode",
    "fzboost_z_mean",
    "fzboost_z_median",
    "fzboost_z_best",
    "fzboost_z_err68_low",
    "fzboost_z_err68_high",
    "fzboost_z_err95_low",
    "fzboost_z_err95_high",
]


def read_parquet_matches(path: Path, object_ids: list[int]) -> pd.DataFrame:
    columns = ["objectId", *SCIENCE_COLUMNS]
    try:
        return pd.read_parquet(
            path,
            columns=columns,
            filters=[("objectId", "in", object_ids)],
        )
    except (TypeError, ValueError):
        frame = pd.read_parquet(path, columns=columns)
        return frame[frame["objectId"].isin(object_ids)]


def read_candidate(path: Path, object_ids: list[int]) -> pd.DataFrame:
    if path.is_file():
        return read_parquet_matches(path, object_ids)

    staging_files = sorted(
        candidate for candidate in path.glob("*.parquet")
        if candidate.name != "pz_pdf_xvals.parquet"
    )
    if staging_files:
        return pd.concat(
            [
                read_parquet_matches(candidate, object_ids)
                for candidate in staging_files
            ],
            ignore_index=True,
        )

    try:
        import lsdb
    except ImportError as error:
        raise RuntimeError(
            f"{path} is not Parquet staging; install LSDB to open it as HATS"
        ) from error
    catalog = lsdb.open_catalog(path, columns=["objectId", *SCIENCE_COLUMNS])
    return catalog.query(f"objectId in {object_ids}").compute()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    reference = pd.read_parquet(
        args.reference, columns=["objectId", *SCIENCE_COLUMNS]
    )
    object_ids = reference["objectId"].astype("int64").tolist()
    candidate = read_candidate(args.candidate, object_ids)
    if reference["objectId"].duplicated().any():
        raise ValueError("reference objectId values are not unique")
    if candidate["objectId"].duplicated().any():
        raise ValueError("candidate objectId values are not unique")

    merged = reference.merge(
        candidate,
        on="objectId",
        how="inner",
        suffixes=("_reference", "_local"),
        validate="one_to_one",
    )
    if len(merged) != len(reference):
        raise ValueError(
            f"matched {len(merged):,} of {len(reference):,} reference objects"
        )

    rows = []
    for name in SCIENCE_COLUMNS:
        expected = merged[f"{name}_reference"].to_numpy(dtype=np.float64)
        actual = merged[f"{name}_local"].to_numpy(dtype=np.float64)
        finite = np.isfinite(expected) & np.isfinite(actual)
        delta = actual[finite] - expected[finite]
        absolute = np.abs(delta)
        correlation = (
            np.corrcoef(expected[finite], actual[finite])[0, 1]
            if finite.sum() > 1
            else np.nan
        )
        rows.append(
            {
                "quantity": name,
                "compared": int(finite.sum()),
                "local_nonfinite": int((~np.isfinite(actual)).sum()),
                "bias": float(np.mean(delta)) if len(delta) else np.nan,
                "median_abs_diff": (
                    float(np.median(absolute)) if len(absolute) else np.nan
                ),
                "p95_abs_diff": (
                    float(np.quantile(absolute, 0.95)) if len(absolute) else np.nan
                ),
                "max_abs_diff": (
                    float(np.max(absolute)) if len(absolute) else np.nan
                ),
                "correlation": float(correlation),
            }
        )

    report = pd.DataFrame(rows).set_index("quantity")
    print(report.to_string(float_format=lambda value: f"{value:.7g}"))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(args.output)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
