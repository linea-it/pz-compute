#!/usr/bin/env python3
"""Add the DP2 Model metadata used by the published reference artifacts."""

import argparse
import pickle
from pathlib import Path

from rail.core.model import Model


CREATION_CLASSES = {
    "fzboost": "rail.estimation.algos.flexzboost.FlexZBoostInformer",
    "bpz": "rail.estimation.algos.bpz_lite.BPZliteInformer",
    "bpz_test": "rail.estimation.algos.bpz_lite.BPZliteInformer",
}

FLAVORS = {
    "fzboost": "dp2_6band",
    "bpz": "dp2_6band",
    "bpz_test": "cosmos31_test",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("algorithm", choices=sorted(CREATION_CLASSES))
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with args.raw.open("rb") as stream:
        loaded = pickle.load(stream)
    data = loaded.data if isinstance(loaded, Model) else loaded

    wrapped = Model(
        data=data,
        creation_class_name=CREATION_CLASSES[args.algorithm],
        version=0,
        catalog_tag="lsst_gaap_1p0",
        provenance={
            "project": "dp2_v3p1",
            "flavor": FLAVORS[args.algorithm],
            "selection": "gold",
        },
    )
    wrapped.write(str(args.output))
    print(f"wrote: {args.output}")


if __name__ == "__main__":
    main()
