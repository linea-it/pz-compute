from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "doc" / "notebooks"))

import pz_qa  # noqa: E402


def test_main_catalog_row_count_comes_from_loaded_catalog_metadata():
    catalog = SimpleNamespace(
        hc_structure=SimpleNamespace(
            catalog_info=SimpleNamespace(total_rows=123)
        )
    )

    assert pz_qa._read_hats_nrows(catalog) == 123


def test_dp2_v3_configs_open_collection_roots_without_pz_summary_suffix():
    config_dir = ROOT / "doc" / "notebooks" / "config"
    for name in (
        "dp2-v3-fzboost.yaml",
        "dp2-v3-bpz.yaml",
        "dp2-v3-dnf.yaml",
        "dp2-v3-bpz-test.yaml",
    ):
        config = pz_qa.load_config(config_dir / name)
        assert Path(config["paths"]["summary_hats"]).name != "pz_summary"

    source = (ROOT / "doc" / "notebooks" / "pz_qa.py").read_text()
    assert "lsdb.open_catalog(summary_path)" in source
    assert "lsdb.read_hats(summary_path)" not in source


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
    assert result["selections"]["all"]["invalid_xvals"] == 0
    assert result["selections"]["all"]["invalid_yvals_dtype"] == 0
    assert result["selections"]["bright"]["rows"] == 1
    assert result["selections"]["bright"]["valid"] == 1
    assert len(result["sample"]) == 2


def test_nested_bundle_reduces_scalars_and_pdfs_from_the_same_partition():
    grid = np.linspace(0, 1, 4, dtype=np.float32)
    frame = pd.DataFrame(
        {
            "objectId": [10, 20],
            "coord_ra": [10.0, 20.0],
            "coord_dec": [-10.0, 10.0],
            "zmode": [2 / 3, 0.0],
            "zmean": [0.5, 0.5],
            "zmedian": [2 / 3, 1 / 3],
            "z_p16": [1 / 3, 0.0],
            "z_p84": [1.0, 1.0],
            "i_gaap1p0Mag_sfd": [25.0, 27.0],
            "refExtendedness": [1.0, 0.0],
            "fzboost_ens_interp": [
                {"xvals": grid, "yvals": np.asarray([0, 1, 2, 1], dtype=np.float32)},
                {"xvals": grid, "yvals": np.ones(4, dtype=np.float32)},
            ],
        }
    )
    selections = [
        {"name": "all"},
        {
            "name": "galaxies_i_lt_26",
            "filters": [
                {"column": "refExtendedness", "minimum": 1.0, "maximum": 2.0},
                {"column": "i_gaap1p0Mag_sfd", "maximum": 26.0},
            ],
        },
    ]
    grid64 = grid.astype(float)
    differences = np.diff(grid64)
    edges = np.concatenate((
        [grid64[0] - differences[0] / 2],
        (grid64[:-1] + grid64[1:]) / 2,
        [grid64[-1] + differences[-1] / 2],
    ))

    summary, pdf = pz_qa._nested_partition_bundle(
        frame,
        "fzboost_ens_interp",
        selections,
        edges,
        grid64,
        batch_rows=2,
        sample_probability=1.0,
        edge_bins=1,
    )

    assert summary["selections"]["all"]["rows"] == 2
    assert pdf["selections"]["all"]["rows"] == 2
    assert summary["selections"]["galaxies_i_lt_26"]["rows"] == 1
    assert pdf["selections"]["galaxies_i_lt_26"]["rows"] == 1


def test_nested_pdf_partition_rejects_grid_dtype_and_length_errors():
    grid = np.linspace(0, 1, 4, dtype=np.float32)
    valid_pdf = np.asarray([0, 1, 2, 1], dtype=np.float32)
    frame = pd.DataFrame(
        {
            "objectId": [10, 20, 30, 40, 50],
            "fzboost_ens_interp": [
                {"xvals": grid, "yvals": valid_pdf},
                {"xvals": grid.astype(np.float64), "yvals": valid_pdf},
                {"xvals": grid + np.float32(0.01), "yvals": valid_pdf},
                {"xvals": grid, "yvals": valid_pdf.astype(np.float64)},
                {"xvals": grid, "yvals": valid_pdf[:3]},
            ],
        }
    )

    result = pz_qa._nested_pdf_partition(
        frame,
        "fzboost_ens_interp",
        [{"name": "all"}],
        grid.astype(float),
        batch_rows=2,
        sample_probability=1.0,
        edge_bins=1,
    )["selections"]["all"]

    assert result["rows"] == 5
    assert result["valid"] == 1
    assert result["invalid"] == 4
    assert result["invalid_xvals"] == 2
    assert result["invalid_yvals_dtype"] == 1
    assert result["wrong_length"] == 1


def test_nested_pdf_partition_reports_invalid_pdf_values():
    grid = np.linspace(0, 1, 4, dtype=np.float32)
    frame = pd.DataFrame(
        {
            "objectId": [10, 20, 30, 40],
            "fzboost_ens_interp": [
                {"xvals": grid, "yvals": np.asarray([0, 1, 2, 1], dtype=np.float32)},
                {"xvals": grid, "yvals": np.asarray([0, np.nan, 2, 1], dtype=np.float32)},
                {"xvals": grid, "yvals": np.asarray([0, -1, 2, 1], dtype=np.float32)},
                {"xvals": grid, "yvals": np.zeros(4, dtype=np.float32)},
            ],
        }
    )

    result = pz_qa._nested_pdf_partition(
        frame,
        "fzboost_ens_interp",
        [{"name": "all"}],
        grid.astype(float),
        batch_rows=2,
        sample_probability=1.0,
        edge_bins=1,
    )["selections"]["all"]

    assert result["valid"] == 1
    assert result["invalid"] == 3
    assert result["nonfinite"] == 1
    assert result["negative"] == 1
    assert result["nonpositive_sum"] == 1


def test_pdf_summaries_match_stage3_discrete_definitions():
    grid = np.asarray([0.0, 1.0, 2.0])
    matrix = np.asarray([[0.0, 1.0, 3.0], [2.0, 1.0, 1.0]])

    summaries = pz_qa._pdf_summaries(matrix, grid)

    np.testing.assert_array_equal(summaries["zmode_pdf"], [2.0, 0.0])
    np.testing.assert_allclose(summaries["zmean_pdf"], [1.75, 0.75])
    np.testing.assert_array_equal(summaries["z_p16_pdf"], [1.0, 0.0])
    np.testing.assert_array_equal(summaries["zmedian_pdf"], [2.0, 0.0])
    np.testing.assert_array_equal(summaries["z_p84_pdf"], [2.0, 2.0])


def test_dp2_v3_qa_configs_use_full_nested_layout():
    for algorithm in ("fzboost", "bpz", "dnf", "bpz-test"):
        config = pz_qa.load_config(
            ROOT / "doc" / "notebooks" / "config" / f"dp2-v3-{algorithm}.yaml"
        )
        assert config["pdf"]["layout"] == "nested"
        assert config["metrics"]["max_hats_partitions"] == 0
        assert "pdf_dir" not in config["paths"]
        assert config["cluster"]["minimum_jobs"] == 1
        assert config["cluster"]["cores"] == 2
        assert config["cluster"]["memory"] == "40GiB"
        galaxy = next(item for item in config["selections"] if item["name"] == "galaxies")
        assert galaxy["filters"] == [
            {
                "column": "refExtendedness",
                "minimum": 1.0,
                "maximum": 2.0,
                "finite": True,
            }
        ]
        combined = next(
            item for item in config["selections"]
            if item["name"] == "galaxies_i_lt_26"
        )
        assert [item["column"] for item in combined["filters"]] == [
            "refExtendedness",
            "i_gaap1p0Mag_sfd",
        ]


def test_extendedness_selection_excludes_point_sources_and_nulls():
    frame = pd.DataFrame({"refExtendedness": [0.0, 1.0, np.nan]})
    selection = {
        "filters": [
            {
                "column": "refExtendedness",
                "minimum": 1.0,
                "maximum": 2.0,
                "finite": True,
            }
        ]
    }

    assert pz_qa._selection_mask(frame, selection).tolist() == [False, True, False]


def test_combined_selection_applies_magnitude_and_extendedness_cuts():
    frame = pd.DataFrame(
        {
            "i_gaap1p0Mag_sfd": [25.0, 27.0, 25.0, 25.0],
            "refExtendedness": [1.0, 1.0, 0.0, np.nan],
        }
    )
    selection = {
        "filters": [
            {
                "column": "refExtendedness",
                "minimum": 1.0,
                "maximum": 2.0,
                "finite": True,
            },
            {
                "column": "i_gaap1p0Mag_sfd",
                "maximum": 26.0,
                "finite": True,
            },
        ]
    }

    assert pz_qa._selection_mask(frame, selection).tolist() == [True, False, False, False]

