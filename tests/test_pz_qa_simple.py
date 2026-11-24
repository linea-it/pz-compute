import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import warnings
from datetime import datetime

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

    linea = qa.load_config(
        NOTEBOOK_DIR / "config/dp2-v3-fzboost-hpc-public.yaml"
    )
    rubin = qa.load_config(
        NOTEBOOK_DIR / "config/dp2-v3-fzboost-rubin-hpc-public.yaml"
    )
    assert linea["cluster"]["queue"] == "cpu_small"
    assert linea["cluster"]["account"] == "hpc-public"
    assert linea["cluster"]["minimum_jobs"] == 4
    assert rubin["describe"]["include_contains"] == ["fzboost"]
    assert rubin["selections"] == [
        {
            "name": "all",
            "label": "All objects",
            "description": "All catalog rows before any configured science selection.",
        }
    ]


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
            "objectId": np.array(
                [
                    9223372036854775808,
                    9223372036854775810,
                    9223372036854775812,
                    9223372036854775814,
                ],
                dtype=np.uint64,
            ),
            "coord_ra": [10.0, 20.0, 30.0, 40.0],
            "coord_dec": [-2.0, -1.0, 1.0, 2.0],
            "fzboost_z_best": [0.2, 0.8, np.nan, 1.6],
            "bpz_z_best": [0.3, 0.9, 1.2, 1.7],
            "i_gaap1p0Mag_sfd": [25.0, 26.5, 24.5, 25.5],
            "refExtendedness": pd.array([1, 1, 0, 1], dtype="Int64"),
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
    opened = []

    def open_catalog(path, columns=None):
        opened.append({"path": path, "columns": columns})
        if columns == "all":
            return catalog
        catalog.projections.append(list(columns))
        return Projection(list(columns))

    monkeypatch.setattr(qa.lsdb, "open_catalog", open_catalog)
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
    assert opened == [
        {"path": "/unused", "columns": "all"},
        {
            "path": "/unused",
            "columns": [
                "objectId",
                "coord_ra",
                "coord_dec",
                "fzboost_z_best",
                "bpz_z_best",
                "i_gaap1p0Mag_sfd",
                "refExtendedness",
            ],
        },
    ]
    assert result.nested_columns == ("fzboost_ens_interp",)
    assert all("fzboost_ens_interp" not in columns for columns in catalog.projections)
    assert set(result.describe.index) == set(frame.columns) - {"fzboost_ens_interp"}
    assert result.describe.loc["objectId", "mean"] > 9.0e18
    assert result.describe.loc["fzboost_z_best", "count"] == 3
    assert result.describe.loc["fzboost_z_best", "null"] == 1
    assert result.selection_counts.loc["All", "selected rows"] == 4
    assert result.selection_counts.loc["Bright extended", "selected rows"] == 2
    assert result.redshift_histograms["all"].sum() == 3
    box = qa.columns_box(result)
    assert "nested — not read" in box
    assert "var(--jp-layout-color1, transparent)" in box

    catalog.projections.clear()
    filtered_config = {
        **config,
        "describe": {
            "percentiles": [0.25, 0.5, 0.75],
            "include_contains": ["fzboost"],
        },
    }
    opened.clear()
    filtered = qa.run_qa(filtered_config)
    assert list(filtered.describe.index) == ["fzboost_z_best"]
    assert "bpz_z_best" not in catalog.projections[0]
    assert set(catalog.projections[0]) == {
        "fzboost_z_best",
        "i_gaap1p0Mag_sfd",
        "refExtendedness",
    }
    assert opened[0]["columns"] == "all"
    assert opened[1]["columns"] == catalog.projections[0]


def test_describe_column_filter_is_case_insensitive():
    qa = load_simple_qa()
    columns = ["objectId", "fzboost_z_best", "FZBOOST_z_mean", "bpz_z_best"]

    assert qa._describe_columns({"describe": {}}, columns) == columns
    assert qa._describe_columns(
        {"describe": {"include_contains": ["fzboost"]}}, columns
    ) == ["fzboost_z_best", "FZBOOST_z_mean"]


def test_execution_metadata_uses_yaml_and_configured_timezone():
    qa = load_simple_qa()
    config = {
        "report": {
            "author": "Luigi Lucas de Carvalho Silva",
            "contact": "luigi.lcsilva@gmail.com",
            "timezone": "America/Sao_Paulo",
        }
    }

    html = qa.execution_metadata_html(config, datetime(2026, 11, 24, 12, 0))

    assert "Author: Luigi Lucas de Carvalho Silva<br>" in html
    assert "Contact: luigi.lcsilva@gmail.com<br>" in html
    assert "Last verified execution: November 24, 2026<br>" in html


def test_slurm_startup_suppresses_only_known_distributed_warnings(monkeypatch):
    qa = load_simple_qa()

    class FakeCluster:
        def __init__(self, **kwargs):
            warnings.warn_explicit(
                "Port 8787 is already in use. Hosting on another port.",
                UserWarning,
                "distributed/node.py",
                195,
                module="distributed.node",
            )
            warnings.warn_explicit(
                "Couldn't detect a suitable IP address for reaching '8.8.8.8'",
                RuntimeWarning,
                "distributed/utils.py",
                200,
                module="distributed.utils",
            )

        def adapt(self, **kwargs):
            pass

    class FakeClient:
        def __init__(self, cluster):
            self.cluster = cluster

        def wait_for_workers(self, workers, timeout):
            pass

    monkeypatch.setitem(
        sys.modules, "dask_jobqueue", SimpleNamespace(SLURMCluster=FakeCluster)
    )
    monkeypatch.setattr(qa, "Client", FakeClient)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        qa.start_cluster(
            {
                "cluster": {
                    "type": "slurm",
                    "minimum_jobs": 1,
                    "maximum_jobs": 2,
                }
            }
        )

    assert captured == []


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
    assert "plt.show()" in text
    assert "display(figure)" not in text
    assert "logo-linea" in text
    assert "execution_metadata_html" in text
    assert "### Acknowledgments" in text
    assert "yvals" not in text
    assert "qp." not in text
