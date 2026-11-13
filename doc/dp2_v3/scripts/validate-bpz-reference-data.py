#!/usr/bin/env python3
"""Validate a BPZ reference-data root and optionally list checksum inputs."""

import argparse
from pathlib import Path


BANDS = "ugrizy"


def read_spectra(path: Path) -> list[str]:
    entries = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            entries.append(line)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("spectra_file")
    parser.add_argument("expected_count", type=int)
    parser.add_argument("--list-files", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    sed_dir = root / "SED"
    filter_dir = root / "FILTER"
    list_path = sed_dir / args.spectra_file
    if not list_path.is_file():
        raise SystemExit(f"Missing BPZ spectra list: {list_path}")

    entries = read_spectra(list_path)
    if len(entries) != args.expected_count:
        raise SystemExit(
            f"{list_path}: expected {args.expected_count} SED entries, found {len(entries)}"
        )

    files = [list_path]
    for entry in entries:
        relative = Path(entry)
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit(f"Unsafe SED entry in {list_path}: {entry}")
        sed_path = sed_dir / relative
        if not sed_path.is_file():
            raise SystemExit(f"Missing BPZ SED: {sed_path}")
        files.append(sed_path)

    for band in BANDS:
        filter_path = filter_dir / f"lsstcam_{band}.res"
        if not filter_path.is_file():
            raise SystemExit(f"Missing BPZ filter: {filter_path}")
        files.append(filter_path)

    if args.list_files:
        for path in files:
            print(path)
    else:
        print(
            f"valid BPZ reference data: {root} "
            f"({len(entries)} SEDs, {len(BANDS)} filters)"
        )


if __name__ == "__main__":
    main()
