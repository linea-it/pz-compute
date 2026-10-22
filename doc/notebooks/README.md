# Photo-z final-product QA

`pz_compute_qa.ipynb` is the single QA notebook for final HATS point-estimate
catalogs and their companion PDF parquet products. Run layout, selections,
thresholds, and Dask resources live in YAML instead of notebook cells.

Available run configurations:

- `config/dp1-v2-fzboost.yaml`
- `config/dp2-v2-fzboost.yaml`
- `config/dp2-v3-bpz-test.yaml`

The first two configurations describe the completed DP1-v2 and DP2-v2
FZBoost products. DP2-v3 currently has only the standalone `bpz_test`
engineering product; there is intentionally no DP2-v3 FZBoost configuration.

From the repository root, start Jupyter with the selected configuration:

```bash
PZ_QA_CONFIG=doc/notebooks/config/dp1-v2-fzboost.yaml jupyter lab
```

Open `doc/notebooks/pz_compute_qa.ipynb` and run all cells. If
`PZ_QA_CONFIG` is absent, the notebook uses the DP1 configuration. Relative
configuration paths are resolved relative to the YAML file; environment
variables such as `${PZ_RUN_ROOT}` are expanded.

## Quality-selected curves

Selections are evaluated alongside the full sample in the same partition
passes. All standard configurations produce both the complete-sample metrics
and a finite `i_gaap1p0Mag_sfd < 26` selection:

```yaml
selections:
  - name: all
    label: All objects
  - name: clean_i_lt_26
    label: "i_gaap1p0Mag_sfd < 26"
    filters:
      - column: i_gaap1p0Mag_sfd
        maximum: 26.0
        finite: true
```

Every filter column must exist in both the HATS summary and PDF parquet
product. Multiple filters within a selection are combined with logical AND.
`minimum` is inclusive and `maximum` is exclusive.

## Outputs and interpretation

The notebook reports:

- schema, grid, row-count, coordinate, interval, and PDF validity checks;
- commutative `objectId` fingerprints between the two final products;
- global moments and histogram percentiles for point estimates and stacked PDFs;
- PDF raw-sum diagnostics before per-object normalization;
- interval-width and redshift-edge diagnostics;
- total-variation and Wasserstein distances between global N(z) curves;
- a deterministic sampled reconstruction of all five HATS summaries from PDFs.

The fingerprints make cross-product comparison scalable without a catalog-wide
shuffle. They test equality of the identifier multisets with three independent
64-bit aggregates; they are not a formal proof of uniqueness. Set
`metrics.exact_id_uniqueness: true` to add exact `nunique` checks when the
distributed shuffle is acceptable (enabled for DP1, disabled for the much
larger DP2 configurations). The sampled summary reconstruction is an
integration check, not a truth-redshift metric.

Set `paths.report_dir` to save the compact result tables as CSV/JSON. No object
catalog or PDF matrix is collected into notebook memory. The only collected
objects are fixed-size reductions and the configured deterministic sample.

Required packages are `lsdb`, `dask`, `distributed`, `dask-jobqueue` for
SLURM, `pandas`, `numpy`, `pyarrow`, `matplotlib`, and `pyyaml`.
