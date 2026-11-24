import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import dask.dataframe as dd
import numpy as np
import pandas as pd


ROOT = Path(__file__).parents[1]
NOTEBOOK_DIR = ROOT / "doc" / "notebooks" / "pz_compute_v2"


def load_simple_qa():
    path = NOTEBOOK_DIR / "pz_qa.py"
    spec = importlib.util.spec_from_file_location("test_simple_pz_qa", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_v2_configs_are_scalar_only_and_use_algorithm_point_estimates():
    qa = load_simple_qa()
    expected = {
        "dp2-v3-fzboost.yaml": "fzboost_z_best",
        "dp2-v3-bpz.yaml": "bpz_z_best",
        "dp2-v3-dnf.yaml": "dnf_z_best",
        "dp2-v3-bpz-test.yaml": "bpz_test_z_best",
    }
    for filename, redshift_column in expected.items():
        config = qa.load_config(NOTEBOOK_DIR / "config" / filename)
        assert config["redshift"]["column"] == redshift_column
        assert "pdf" not in config
        assert "thresholds" not in config
        assert config["cluster"]["minimum_jobs"] == 8
        assert config["cluster"]["maximum_jobs"] == 32


def test_filters_support_equality_and_numeric_bounds():
    qa = load_simple_qa()
    frame = pd.DataFrame(
        {
            "magnitude": [25.0, 25.5, 26.5, np.nan],
            "extended": [1, 0, 1, 1],
        }
    )
    selection = {
        "filters": [
            {"column": "magnitude", "maximum": 26.0, "finite": True},
            {"column": "extended", "equals": 1, "finite": True},
        ]
    }

    assert qa._selection_mask(frame, selection).tolist() == [True, False, False, False]


def test_simple_qa_never_projects_nested_columns(monkeypatch):
    qa = load_simple_qa()
    frame = pd.DataFrame(
        {
            "objectId": [1, 2, 3, 4],
            "coord_ra": [10.0, 20.0, 30.0, 40.0],
            "coord_dec": [-2.0, -1.0, 1.0, 2.0],
            "fzboost_z_best": [0.2, 0.8, np.nan, 1.6],
            "i_gaap1p0Mag_sfd": [25.0, 26.5, 24.5, 25.5],
            "refExtendedness": [1, 1, 0, 1],
            "fzboost_ens_interp": [object(), object(), object(), object()],
        }
    )

    class Projection:
        def __init__(self, columns):
            self.columns = columns

        def to_dask_dataframe(self):
            return dd.from_pandas(frame[self.columns], npartitions=2)

    class Catalog:
        columns = frame.columns
        nested_columns = ["fzboost_ens_interp"]
        npartitions = 2
        dtypes = frame.dtypes
        hc_structure = SimpleNamespace(
            catalog_info=SimpleNamespace(total_rows=len(frame))
        )

        def __init__(self):
            self.projections = []

        def __getitem__(self, columns):
            self.projections.append(list(columns))
            return Projection(list(columns))

    catalog = Catalog()
    monkeypatch.setattr(qa.lsdb, "open_catalog", lambda _: catalog)
    config = {
        "run": {"name": "test"},
        "paths": {"summary_hats": "/unused", "report_dir": None},
        "redshift": {
            "column": "fzboost_z_best",
            "minimum": 0.0,
            "maximum": 2.0,
            "bins": 4,
        },
        "describe": {"percentiles": [0.25, 0.5, 0.75]},
        "selections": [
            {"name": "all", "label": "All"},
            {
                "name": "bright_extended",
                "label": "Bright extended",
                "filters": [
                    {
                        "column": "i_gaap1p0Mag_sfd",
                        "maximum": 26.0,
                        "finite": True,
                    },
                    {
                        "column": "refExtendedness",
                        "equals": 1,
                        "finite": True,
                    },
                ],
            },
        ],
    }

    result = qa.run_qa(config)

    assert result.row_count == 4
    assert result.nested_columns == ("fzboost_ens_interp",)
    assert all("fzboost_ens_interp" not in columns for columns in catalog.projections)
    assert result.describe.loc["fzboost_z_best", "count"] == 3
    assert result.describe.loc["fzboost_z_best", "null"] == 1
    assert result.selection_counts.loc["All", "selected rows"] == 4
    assert result.selection_counts.loc["Bright extended", "selected rows"] == 2
    assert result.redshift_histograms["all"].sum() == 3
    assert "nested — not read" in qa.columns_box(result)


def test_v2_notebook_is_simple_and_has_stable_cell_ids():
    notebook = json.loads((NOTEBOOK_DIR / "pz_compute_qa.ipynb").read_text())
    ids = [cell.get("id") for cell in notebook["cells"]]
    assert all(ids)
    assert len(ids) == len(set(ids))
    text = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )
    assert "columns_box" in text
    assert "result.describe" in text
    assert "plot_redshift_distributions" in text
    assert "No PDF or complex integrity checks" in text
    assert "yvals" not in text
    assert "qp." not in text
