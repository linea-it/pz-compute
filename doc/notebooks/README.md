# Photo-z final-product QA

`pz_compute_qa.ipynb` is the single QA notebook for final HATS point-estimate
catalogs and either companion-Parquet or HATS-embedded Nested PDFs. Run layout,
selections, thresholds, and Dask resources live in YAML instead of notebook
cells.

Available run configurations:

- `config/dp1-v2-fzboost.yaml`
- `config/dp2-v2-fzboost.yaml`
- `config/dp2-v3-fzboost.yaml`
- `config/dp2-v3-bpz.yaml`
- `config/dp2-v3-dnf.yaml`
- `config/dp2-v3-bpz-test.yaml`

The first two configurations retain the companion layout used by DP1-v2 and
DP2-v2. All DP2-v3 configurations read `<algorithm>_ens_interp` directly from
the final HATS catalog.

DP2-v3 defaults to `metrics.max_hats_partitions: 4`. Point-estimate and PDF
metrics are therefore explicitly sample diagnostics, not catalog-wide N(z)
measurements. Increase the limit deliberately or set it to `0` for a full
distributed scan.

From the repository root, start Jupyter with the selected configuration:

```bash
PZ_QA_CONFIG=doc/notebooks/config/dp1-v2-fzboost.yaml jupyter lab
```

Open `doc/notebooks/pz_compute_qa.ipynb` and run all cells. If
`PZ_QA_CONFIG` is absent, the notebook uses the DP1 configuration. Relative
configuration paths are resolved relative to the YAML file; environment
variables such as `${PZ_RUN_ROOT}` are expanded.

After execution, export a report without input cells using:

```bash
jupyter nbconvert \
  --to html \
  --no-input \
  --output pz-compute-qa.html \
  doc/notebooks/pz_compute_qa.ipynb
```

Section text, output captions, table definitions, product provenance, and plot
legends are written to remain understandable when the Python code is hidden.

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

Every filter column must be available with the scalar and PDF fields. For the
nested DP2-v3 layout they are in the same HATS row. Multiple filters within a
selection are combined with logical AND.
`minimum` is inclusive and `maximum` is exclusive.

## N(z) display range and low-redshift peaks

The standard configurations report `low_z_fraction` for `z <= 0.1` and the
fractions in the first and last redshift-grid bins. These metrics help
distinguish a concentration of point-estimate modes at `z = 0` from integrated
posterior probability in the stacked PDFs.

N(z) panels use a robust y-axis display range so isolated boundary spikes do
not flatten the scientifically useful part of the curves. Off-scale maxima are
annotated with their amplitude and redshift, and the uncapped values remain in
every calculation and exported table. To show the full linear range instead:

```yaml
plots:
  nz_ymax_quantile: 1.0
  nz_ymax_headroom: 1.10
```

## Outputs and interpretation

The notebook reports:

- schema, grid, row-count, coordinate, interval, and PDF validity checks;
- commutative `objectId` fingerprints between the scalar and PDF projections;
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

Set `paths.report_dir` to save the compact result tables as CSV/JSON. No full
object catalog or PDF matrix is collected into notebook memory. The only
collected objects are fixed-size reductions and the configured deterministic
sample; nested DP2-v3 QA also bounds the number of source partitions by
default.

Required packages are `lsdb`, `nested-pandas`, `dask`, `distributed`,
`dask-jobqueue` for SLURM, `pandas`, `numpy`, `pyarrow`, `matplotlib`, and
`pyyaml`.
