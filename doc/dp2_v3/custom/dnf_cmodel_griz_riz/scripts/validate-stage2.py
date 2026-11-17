#!/usr/bin/env python3
"""Validate custom DNF cModel Stage 2 output pairs or complete manifests."""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import sys

import h5py
import numpy as np
import pyarrow.parquet as pq
import yaml


PROJECT_DIR = Path(__file__).resolve().parent.parent
DP2_DOC_DIR = PROJECT_DIR.parents[1]
REPOSITORY_ROOT = DP2_DOC_DIR.parents[1]
SFD_PATH = DP2_DOC_DIR / "config/dp2-v3-sfd-lsstcam.yaml"
VARIANTS = {"griz": tuple("griz"), "riz": tuple("riz")}
DEFAULT_INPUT = Path(
    "/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset"
)
EXPECTED_ANCILLARY = {"DNF_ZN"}

sys.path.insert(0, str(REPOSITORY_ROOT / "rail_scripts"))
from rail_scripts.integrity import (  # noqa: E402
    FINGERPRINT_ALGORITHM,
    row_id_fingerprint,
)
from rail_scripts.photometry import (  # noqa: E402
    materialize_sfd_columns,
    projected_input_columns,
)


def load_sfd() -> dict[str, float]:
    with SFD_PATH.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)["sfd_a_ebv"]


def expected_input_columns(
    path: Path, bands: tuple[str, ...], coefficients: dict[str, float]
):
    parquet = pq.ParquetFile(path)
    generated = []
    for band in bands:
        generated.extend(
            (f"{band}_cModelMag_sfd", f"{band}_cModelMagErr_sfd")
        )
    required = [*generated, "objectId"]
    columns = projected_input_columns(parquet.schema_arrow.names, required, "ebv")
    if "objectId" not in parquet.schema_arrow.names:
        raise ValueError("input is missing objectId")
    if "objectId" not in columns:
        columns.append("objectId")
    table = parquet.read(columns=columns).to_pandas()
    materialize_sfd_columns(table, generated, "ebv", coefficients)
    return table


def sampled_pdf_indices(rows: int) -> np.ndarray:
    if rows == 0:
        return np.array([], dtype=np.int64)
    return np.unique(np.linspace(0, rows - 1, min(rows, 9), dtype=np.int64))


def validate_pair(input_path: Path, output_path: Path, variant: str) -> int:
    bands = VARIANTS[variant]
    coefficients = load_sfd()
    expected = expected_input_columns(input_path, bands, coefficients)
    expected_rows = len(expected)

    with h5py.File(output_path, "r") as handle:
        yvals = handle["data/yvals"]
        if yvals.shape != (expected_rows, 601):
            raise ValueError(
                f"data/yvals has shape {yvals.shape}; expected {(expected_rows, 601)}"
            )
        xvals = np.asarray(handle["meta/xvals"])
        if xvals.shape != (1, 601):
            raise ValueError(f"meta/xvals has shape {xvals.shape}; expected (1, 601)")
        np.testing.assert_allclose(
            xvals[0], np.linspace(0.0, 6.0, 601), rtol=0, atol=1e-14
        )

        if "ancillary" not in handle:
            raise ValueError("promoted ancillary group is absent")
        actual_ancillary = set(handle["ancillary"])
        if actual_ancillary != EXPECTED_ANCILLARY:
            raise ValueError(
                f"promoted ancillary fields are {sorted(actual_ancillary)}; "
                f"expected {sorted(EXPECTED_ANCILLARY)}"
            )
        for name in EXPECTED_ANCILLARY:
            if handle[f"ancillary/{name}"].shape != (expected_rows,):
                raise ValueError(f"ancillary/{name} row count differs from input")

        promoted_zn = handle["ancillary/DNF_ZN"][...]
        internal_zn = handle["ancil/DNF_ZN"][...]
        np.testing.assert_array_equal(promoted_zn, internal_zn)
        if not np.isfinite(promoted_zn).all():
            raise ValueError("DNF_ZN contains non-finite values")

        marker = handle["pz_compute"].attrs
        if not bool(marker.get("complete", False)):
            raise ValueError("completion marker is false or absent")
        if int(marker.get("row_count", -1)) != expected_rows:
            raise ValueError("completion-marker row count differs from input")
        if marker.get("row_id_column", "") != "objectId":
            raise ValueError("row identifier marker is not objectId")
        if marker.get("row_id_fingerprint_algorithm", "") != FINGERPRINT_ALGORITHM:
            raise ValueError("row fingerprint algorithm differs from contract")
        fingerprint = row_id_fingerprint(expected["objectId"].to_numpy())
        if marker.get("row_id_fingerprint", "") != fingerprint:
            raise ValueError("row identifier fingerprint differs from input")
        if marker.get("sfd_bands", "") != "".join(bands):
            raise ValueError("SFD band marker differs from variant")
        np.testing.assert_array_equal(
            marker.get("sfd_a_ebv", []), [coefficients[band] for band in bands]
        )

        indices = sampled_pdf_indices(expected_rows)
        if len(indices):
            sample = np.asarray(yvals[indices, :])
            if not np.isfinite(sample).all():
                raise ValueError("sampled PDFs contain non-finite values")
            if np.any(sample < -1e-12):
                raise ValueError("sampled PDFs contain negative density")
            integrals = np.trapezoid(sample, xvals[0], axis=1)
            np.testing.assert_allclose(integrals, 1.0, rtol=1e-6, atol=1e-6)
    return expected_rows


def manifest_inputs(path: Path) -> list[Path]:
    result = [
        Path(line.strip())
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not result:
        raise ValueError(f"empty manifest: {path}")
    if len(result) != len(set(result)):
        raise ValueError(f"duplicate paths in manifest: {path}")
    return result


def model_path(root: Path, variant: str) -> Path:
    name = f"model_dp2_v3p1_custom_dnf_cmodel_{variant}_gold.pickle"
    return root / variant / "stage1/model" / name


def ready_sources(root: Path, variant: str, manifest: Path) -> list[Path]:
    return [
        model_path(root, variant),
        PROJECT_DIR / f"config/dnf-{variant}-estimate.yaml",
        SFD_PATH,
        manifest,
        REPOSITORY_ROOT / "rail_scripts/rail-estimate",
        PROJECT_DIR / "scripts/run-one-estimate.sbatch",
        Path(__file__).resolve(),
    ]


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_ready(root: Path, variant: str, manifest: Path, scope: str) -> Path:
    destination = root / variant / "stage2" / scope / "READY"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name("READY.inprogress")
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite validation marker: {destination}")
    lines = [f"{digest(path)}  {path.resolve()}\n" for path in ready_sources(root, variant, manifest)]
    temporary.write_text("".join(lines), encoding="utf-8")
    temporary.replace(destination)
    return destination


def validate_manifest(
    root: Path,
    input_root: Path,
    manifest: Path,
    variant: str,
    ready_scope: str | None,
) -> None:
    inputs = manifest_inputs(manifest)
    output_root = root / variant / "stage2/output"
    expected_outputs = set()
    missing = []
    invalid = []
    rows = 0
    valid = 0
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
            rows += validate_pair(input_path, output_path, variant)
            valid += 1
        except (AssertionError, KeyError, OSError, TypeError, ValueError) as error:
            invalid.append((output_path, str(error)))

    actual_outputs = set(output_root.glob("**/*.hdf5"))
    unexpected = sorted(actual_outputs - expected_outputs)
    print(f"variant: {variant}")
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
    if ready_scope:
        marker = write_ready(root, variant, manifest, ready_scope)
        print(f"wrote: {marker}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pair = subparsers.add_parser("pair", help="validate one input/output pair")
    pair.add_argument("variant", choices=VARIANTS)
    pair.add_argument("input", type=Path)
    pair.add_argument("output", type=Path)

    manifest = subparsers.add_parser("manifest", help="validate a manifest")
    manifest.add_argument("selection", choices=(*VARIANTS, "all"))
    manifest.add_argument("--manifest", type=Path)
    manifest.add_argument("--ready-scope", choices=("pilot", "production"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "pair":
        rows = validate_pair(args.input, args.output, args.variant)
        print(f"{args.variant}: valid pair ({rows} rows, {args.output})")
        return

    try:
        root = Path(os.environ["PZ_DP2_CUSTOM_ROOT"])
        official_root = Path(os.environ["PZ_DP2_ROOT"])
    except KeyError as error:
        raise SystemExit(f"{error.args[0]} is not set") from error
    input_root = Path(os.environ.get("PZ_DP2_INPUT_DATASET", DEFAULT_INPUT))
    manifest = args.manifest or official_root / "common/manifests/input-parquet-files.txt"
    variants = VARIANTS if args.selection == "all" else (args.selection,)
    if args.ready_scope and len(variants) > 1:
        destinations = [
            root / variant / "stage2" / args.ready_scope / "READY"
            for variant in variants
        ]
        existing = [path for path in destinations if path.exists()]
        if existing:
            raise FileExistsError(
                f"refusing to overwrite validation markers: {existing}"
            )
        for variant in variants:
            validate_manifest(root, input_root, manifest, variant, None)
        for variant in variants:
            marker = write_ready(root, variant, manifest, args.ready_scope)
            print(f"wrote: {marker}")
    else:
        for variant in variants:
            validate_manifest(root, input_root, manifest, variant, args.ready_scope)


if __name__ == "__main__":
    main()
