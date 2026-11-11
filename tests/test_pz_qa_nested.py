from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "doc" / "notebooks"))

import pz_qa  # noqa: E402


def test_nested_pdf_partition_uses_yvals_and_parent_selection_columns():
    grid = np.linspace(0, 1, 4, dtype=np.float32)
    frame = pd.DataFrame(
        {
            "objectId": [10, 20],
            "i_gaap1p0Mag_sfd": [25.0, 27.0],
            "fzboost_ens_interp": [
                {"xvals": grid, "yvals": np.asarray([0, 1, 2, 1], dtype=np.float32)},
                {"xvals": grid, "yvals": np.asarray([1, 1, 1, 1], dtype=np.float32)},
            ],
        }
    )
    selections = [
        {"name": "all"},
        {
            "name": "bright",
            "filters": [{"column": "i_gaap1p0Mag_sfd", "maximum": 26.0}],
        },
    ]

    result = pz_qa._nested_pdf_partition(
        frame,
        "fzboost_ens_interp",
        selections,
        grid.astype(float),
        batch_rows=2,
        sample_probability=1.0,
        edge_bins=1,
    )

    assert result["selections"]["all"]["rows"] == 2
    assert result["selections"]["all"]["valid"] == 2
    assert result["selections"]["bright"]["rows"] == 1
    assert result["selections"]["bright"]["valid"] == 1
    assert len(result["sample"]) == 2


def test_dp2_v3_qa_configs_use_bounded_nested_layout():
    for algorithm in ("fzboost", "bpz", "dnf", "bpz-test"):
        config = pz_qa.load_config(
            ROOT / "doc" / "notebooks" / "config" / f"dp2-v3-{algorithm}.yaml"
        )
        assert config["pdf"]["layout"] == "nested"
        assert config["metrics"]["max_hats_partitions"] == 4
        assert "pdf_dir" not in config["paths"]

