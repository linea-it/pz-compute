#!/usr/bin/env python3
"""Wrap a custom DP2 DNF cModel artifact with explicit provenance."""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

from rail.core.model import Model


VARIANTS = ("griz", "riz")
CREATION_CLASS = "rail.estimation.algos.dnf.DNFInformer"
CATALOG_TAG = "lsst_cmodel"


def provenance(variant: str) -> dict[str, str]:
    if variant not in VARIANTS:
        raise ValueError(f"unsupported variant: {variant}")
    return {
        "project": "dp2_v3p1_custom",
        "flavor": f"dnf_cmodel_{variant}",
        "selection": "gold",
    }


def wrap_model(variant: str, raw: Path, output: Path) -> None:
    if not raw.is_file():
        raise FileNotFoundError(raw)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite model: {output}")
    with raw.open("rb") as stream:
        loaded = pickle.load(stream)
    data = loaded.data if isinstance(loaded, Model) else loaded

    wrapped = Model(
        data=data,
        creation_class_name=CREATION_CLASS,
        version=0,
        catalog_tag=CATALOG_TAG,
        provenance=provenance(variant),
    )
    temporary = output.with_name(f".{output.name}.inprogress")
    if temporary.exists():
        raise FileExistsError(f"stale temporary model exists: {temporary}")
    try:
        wrapped.write(str(temporary))
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=VARIANTS)
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    wrap_model(args.variant, args.raw, args.output)
    print(f"wrote: {args.output}")


if __name__ == "__main__":
    main()
