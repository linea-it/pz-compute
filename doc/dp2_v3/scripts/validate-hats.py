#!/usr/bin/env python3
"""Validate Stage 3 products for one DP2 algorithm or the full registry."""

import argparse
import os
from pathlib import Path

import h5py
import lsdb
import pyarrow.parquet as pq


ALGORITHMS = ("fzboost", "bpz")
SUMMARY_COLUMNS = [
    "objectId",
    "coord_ra",
    "coord_dec",
    "zmode",
    "zmean",
    "zmedian",
    "z_p16",
    "z_p84",
    "i_gaap1p0Mag_sfd",
]
PDF_COLUMNS = [
    "objectId",
    "coord_ra",
    "coord_dec",
    "i_gaap1p0Mag_sfd",
    "pdf",
]


def stage2_rows(input_root: Path, output_root: Path) -> int:
    total = 0
    for input_path in input_root.glob("**/*.parquet"):
        relative = input_path.relative_to(input_root)
        output_path = output_root / relative.with_suffix(".hdf5")
        if not output_path.is_file():
            raise FileNotFoundError(output_path)
        with h5py.File(output_path, "r") as handle:
            total += handle["data/yvals"].shape[0]
    return total


def validate(root: Path, input_root: Path, algorithm: str) -> None:
    stage2_output = root / algorithm / "stage2" / "output"
    hats_dir = (
        root
        / algorithm
        / "stage3"
        / "output"
        / f"pz-{algorithm}-gaap1p0-clipped-hats"
    )
    pdf_dir = Path(f"{hats_dir}.pdf")
    staging = Path(f"{hats_dir}.parquet_staging")

    catalog = lsdb.read_hats(hats_dir / "pz_summary")
    assert list(catalog.columns) == SUMMARY_COLUMNS, algorithm
    summary_rows = len(catalog)

    parts = sorted(pdf_dir.glob("*pdf-part*.parquet"))
    if not parts:
        raise FileNotFoundError(f"{algorithm}: no PDF parquet parts under {pdf_dir}")
    first = pq.read_table(parts[0])
    xvals = pq.read_table(pdf_dir / "xvals.parquet")
    assert first.column_names == PDF_COLUMNS, algorithm
    assert len(first.column("pdf")[0].as_py()) == 601, algorithm
    assert xvals.column_names == ["bin_index", "z"], algorithm
    assert xvals.num_rows == 601, algorithm

    hdf5_rows = stage2_rows(input_root, stage2_output)
    pdf_rows = sum(pq.read_metadata(path).num_rows for path in parts)
    assert hdf5_rows == summary_rows == pdf_rows, (
        algorithm,
        hdf5_rows,
        summary_rows,
        pdf_rows,
    )
    assert not staging.exists(), f"temporary staging still exists: {staging}"
    print(
        f"{algorithm}: compatible "
        f"(stage2={hdf5_rows}, summary={summary_rows}, pdf={pdf_rows})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", choices=(*ALGORITHMS, "all"))
    args = parser.parse_args()

    try:
        root = Path(os.environ["PZ_DP2_ROOT"])
    except KeyError as error:
        raise SystemExit("PZ_DP2_ROOT is not set") from error
    input_root = Path(
        os.environ.get(
            "PZ_DP2_INPUT_DATASET",
            "/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset",
        )
    )
    algorithms = ALGORITHMS if args.selection == "all" else (args.selection,)
    for algorithm in algorithms:
        validate(root, input_root, algorithm)


if __name__ == "__main__":
    main()
