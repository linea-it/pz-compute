#!/usr/bin/env python3
"""Quickly validate every expected DP2 Stage 2 HDF5 output."""

import argparse
import os
from pathlib import Path

import h5py
import numpy as np
import yaml


ALGORITHMS = ("fzboost", "bpz", "dnf", "bpz_test")
DEFAULT_INPUT = Path(
    "/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset"
)


def expected_inputs(manifest: Path) -> list[Path]:
    paths = [
        Path(line.strip())
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not paths:
        raise ValueError(f"empty manifest: {manifest}")
    if len(paths) != len(set(paths)):
        raise ValueError(f"duplicate paths in manifest: {manifest}")
    return paths


def validate_file(path: Path, expected_sfd: dict[str, float]) -> int:
    with h5py.File(path, "r") as handle:
        yvals = handle["data/yvals"]
        rows, bins = yvals.shape
        if bins != 601:
            raise ValueError(f"data/yvals has {bins} bins, expected 601")
        if handle["meta/xvals"].shape[-1] != 601:
            raise ValueError("meta/xvals does not contain 601 bins")
        if handle["ancillary/i_gaap1p0Mag_sfd"].shape != (rows,):
            raise ValueError("retained magnitude shape does not match PDF rows")

        marker = handle["pz_compute"].attrs
        if not bool(marker.get("complete", False)):
            raise ValueError("completion marker is false or absent")
        if int(marker.get("row_count", -1)) != rows:
            raise ValueError("completion-marker row count does not match data")
        if not marker.get("row_id_fingerprint", ""):
            raise ValueError("row identifier fingerprint is absent")
        if marker.get("sfd_bands", "") != "ugrizy":
            raise ValueError("SFD band marker is not ugrizy")
        if not np.array_equal(
            marker.get("sfd_a_ebv", []),
            [expected_sfd[band] for band in "ugrizy"],
        ):
            raise ValueError("SFD coefficients differ from the versioned contract")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("algorithm", choices=ALGORITHMS)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="input manifest; defaults to the full DP2 v3 manifest",
    )
    args = parser.parse_args()

    try:
        root = Path(os.environ["PZ_DP2_ROOT"])
    except KeyError as error:
        raise SystemExit("PZ_DP2_ROOT is not set") from error
    input_root = Path(os.environ.get("PZ_DP2_INPUT_DATASET", DEFAULT_INPUT))
    manifest = args.manifest or root / "common/manifests/input-parquet-files.txt"
    output_root = root / args.algorithm / "stage2/output"
    sfd_path = Path(__file__).resolve().parent.parent / "config/dp2-v3-sfd-lsstcam.yaml"
    with sfd_path.open(encoding="utf-8") as stream:
        expected_sfd = yaml.safe_load(stream)["sfd_a_ebv"]

    inputs = expected_inputs(manifest)
    missing: list[Path] = []
    invalid: list[tuple[Path, str]] = []
    valid = 0
    rows = 0
    expected_outputs: set[Path] = set()

    for input_path in inputs:
        try:
            relative = input_path.relative_to(input_root)
        except ValueError:
            invalid.append((input_path, f"input is outside {input_root}"))
            continue
        output_path = output_root / relative.with_suffix(".hdf5")
        expected_outputs.add(output_path)
        if not output_path.is_file():
            missing.append(output_path)
            continue
        try:
            rows += validate_file(output_path, expected_sfd)
            valid += 1
        except (KeyError, OSError, TypeError, ValueError) as error:
            invalid.append((output_path, str(error)))

    actual_outputs = set(output_root.glob("**/*.hdf5"))
    unexpected = sorted(actual_outputs - expected_outputs)
    print(f"algorithm: {args.algorithm}")
    print(f"manifest: {manifest}")
    print(f"expected outputs: {len(inputs)}")
    print(f"valid outputs: {valid}")
    print(f"validated rows: {rows}")
    print(f"missing outputs: {len(missing)}")
    print(f"invalid outputs: {len(invalid)}")
    print(f"unexpected outputs: {len(unexpected)}")

    for label, entries in (
        ("missing", [(path, "") for path in missing]),
        ("invalid", invalid),
        ("unexpected", [(path, "") for path in unexpected]),
    ):
        for path, detail in entries[:20]:
            suffix = f": {detail}" if detail else ""
            print(f"{label}: {path}{suffix}")
        if len(entries) > 20:
            print(f"{label}: ... and {len(entries) - 20} more")

    if missing or invalid or unexpected or valid != len(inputs):
        raise SystemExit(1)
    print(f"{args.algorithm}: all Stage 2 outputs are structurally complete")


if __name__ == "__main__":
    main()
