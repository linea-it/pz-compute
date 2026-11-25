#!/usr/bin/env python3
"""Quickly validate every expected DP2 Stage 2 HDF5 output."""

import argparse
import os
from pathlib import Path

import h5py
import numpy as np
import yaml

from rail_scripts.dnf_pdf import DNF_PDF_QUALITY_VERSION
from rail_scripts.photometry import INPUT_PHOTOMETRY_QUALITY_VERSION


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


def validate_dnf_quality(handle: h5py.File, rows: int) -> tuple[int, int]:
    photometry = handle["pz_compute/dnf_input_quality"].attrs
    pdf = handle["pz_compute/dnf_pdf_quality"].attrs
    if (
        photometry.get("method") != INPUT_PHOTOMETRY_QUALITY_VERSION
        or photometry.get("no_photometry_policy") != "nan"
        or photometry.get("selected_bands") != "ugrizy"
        or photometry.get("rows") != rows
    ):
        raise ValueError("missing or incompatible DNF photometry policy")
    if (
        pdf.get("method") != DNF_PDF_QUALITY_VERSION
        or pdf.get("pdf_rows") != rows
        or pdf.get("zmin") != 0.0
        or pdf.get("zmax") != 6.0
    ):
        raise ValueError("missing or incompatible DNF stable PDF policy")
    for name in (
        "nonfinite_dnf_z_rows", "nonfinite_photozerr_rows",
        "nonpositive_photozerr_rows", "pdf_nonfinite_rows",
        "pdf_nonpositive_integral_rows", "pdf_bad_normalization_rows",
    ):
        if pdf.get(name) != 0:
            raise ValueError(f"DNF PDF quality counter {name} must be zero")
    no_estimate = int(pdf["no_estimate_rows"])
    recovered = int(pdf["legacy_gaussian_all_zero_rows"])
    if not (
        0 <= no_estimate <= rows
        and no_estimate == photometry.get("no_usable_selected_band_rows")
        and 0 <= recovered <= rows - no_estimate
    ):
        raise ValueError("inconsistent DNF no-estimate or underflow counts")
    return no_estimate, recovered


def validate_file(
    path: Path, expected_sfd: dict[str, float], algorithm: str,
) -> tuple[int, int, int]:
    with h5py.File(path, "r") as handle:
        yvals = handle["data/yvals"]
        rows, bins = yvals.shape
        if bins != 601:
            raise ValueError(f"data/yvals has {bins} bins, expected 601")
        if handle["meta/xvals"].shape[-1] != 601:
            raise ValueError("meta/xvals does not contain 601 bins")
        if handle["ancillary/i_gaap1p0Mag_sfd"].shape != (rows,):
            raise ValueError("retained magnitude shape does not match PDF rows")
        if handle["ancillary/refExtendedness"].shape != (rows,):
            raise ValueError("retained extendedness shape does not match PDF rows")

        marker = handle["pz_compute"].attrs
        if not bool(marker.get("complete", False)):
            raise ValueError("completion marker is false or absent")
        if int(marker.get("row_count", -1)) != rows:
            raise ValueError("completion-marker row count does not match data")
        if marker.get("row_id_column") != "objectId" or not marker.get("row_id_fingerprint"):
            raise ValueError("objectId fingerprint is absent")
        if marker.get("sfd_bands", "") != "ugrizy":
            raise ValueError("SFD band marker is not ugrizy")
        if not np.array_equal(
            marker.get("sfd_a_ebv", []),
            [expected_sfd[band] for band in "ugrizy"],
        ):
            raise ValueError("SFD coefficients differ from the versioned contract")
        no_estimate, recovered = validate_dnf_quality(handle, rows) if algorithm == "dnf" else (0, 0)
    return rows, no_estimate, recovered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("algorithm", choices=ALGORITHMS)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--manifest",
        type=Path,
        help="input manifest; defaults to the full DP2 v3 manifest",
    )
    scope.add_argument("--file", type=Path, help="validate one smoke or output file")
    parser.add_argument("--sfd-config", type=Path, help="override the SFD configuration path")
    args = parser.parse_args()

    sfd_path = args.sfd_config or Path(__file__).resolve().parent.parent / "config/dp2-v3-sfd-lsstcam.yaml"
    with sfd_path.open(encoding="utf-8") as stream:
        expected_sfd = yaml.safe_load(stream)["sfd_a_ebv"]
    if args.file is not None:
        try:
            rows, no_estimate, recovered = validate_file(args.file, expected_sfd, args.algorithm)
        except (KeyError, OSError, TypeError, ValueError) as error:
            raise SystemExit(f"invalid: {args.file}: {error}") from error
        print(f"valid: {args.file} ({rows} rows)")
        if args.algorithm == "dnf":
            print(f"DNF no-estimate rows: {no_estimate}; legacy underflows recovered: {recovered}")
        return

    try:
        root = Path(os.environ["PZ_DP2_ROOT"])
    except KeyError as error:
        raise SystemExit("PZ_DP2_ROOT is not set") from error
    input_root = Path(os.environ.get("PZ_DP2_INPUT_DATASET", DEFAULT_INPUT))
    manifest = args.manifest or root / "common/manifests/input-parquet-files.txt"
    output_root = root / args.algorithm / "stage2/output"
    inputs = expected_inputs(manifest)
    missing: list[Path] = []
    invalid: list[tuple[Path, str]] = []
    valid = 0
    rows = 0
    no_estimate = recovered = 0
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
            file_rows, file_no_estimate, file_recovered = validate_file(
                output_path, expected_sfd, args.algorithm
            )
            rows += file_rows
            no_estimate += file_no_estimate
            recovered += file_recovered
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
    if args.algorithm == "dnf":
        print(f"DNF no-estimate rows: {no_estimate}")
        print(f"DNF legacy underflows recovered: {recovered}")
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
