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
the final HATS catalog. Their `paths.summary_hats` points to the HATS collection
root, and the QA code opens it with `lsdb.open_catalog()`. LSDB selects the main
`pz_summary` catalog and attaches the collection's default margin without
including margin rows in the main catalog scan.

Do not recursively read Parquet from a DP2-v3 collection root: that would mix
the main catalog with its margin catalog and duplicate boundary objects. Code
that intentionally bypasses LSDB and performs a recursive Parquet read must
start at `<hats_collection>/pz_summary/dataset`, for example:

```text
/scratch/users/app.photoz/pz-compute-runs/dp2-v3/fzboost/stage3/output/
  pz-fzboost-gaap1p0-clipped-hats/pz_summary/dataset
```

DP2-v3 always performs a full distributed scan of the scalar HATS columns used
by the scientific redshift distributions and selections. Nested-PDF integrity
checks default to `metrics.max_pdf_partitions: 4`, because reading the repeated
601-value `xvals` and `yvals` arrays for every object is far more expensive.
PDF-derived results are explicitly technical subset diagnostics, never global
scientific N(z) measurements. The Nested subset consists of the first
configured HATS partitions for reproducibility; because HATS partitions are
spatial, it is not claimed to be statistically representative.
The DP2-v3 SLURM profiles start with one adaptive worker and allow the scan to
begin under cluster contention. Each worker uses one process, two threads, and
40 GiB so at most two memory-intensive Nested-PDF partition tasks share that
allocation.

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

All DP2-v3 configurations also select `refExtendedness == 1` as an extended-
source galaxy proxy and define its intersection with the magnitude cut.
Point-like objects (`0`) and null, unclassified values are excluded. The
notebook presents all four samples in a dedicated 2-by-2 `zmean` figure as well
as in the standard multi-estimator panels:

```yaml
  - name: galaxies
    label: "Extended sources (galaxy proxy)"
    filters:
      - column: refExtendedness
        minimum: 1.0
        maximum: 2.0
        finite: true
  - name: galaxies_i_lt_26
    label: "Extended sources with i_gaap1p0Mag_sfd < 26"
    filters:
      - column: refExtendedness
        minimum: 1.0
        maximum: 2.0
        finite: true
      - column: i_gaap1p0Mag_sfd
        maximum: 26.0
        finite: true
```

This is a morphology-based proxy, not a truth-level star/galaxy label. It is
computed with the other selections in the same distributed catalog pass. In
Nested mode, the four masks share one global scalar pass rather than triggering
four reads. Inside the bounded PDF-QA subset, scalar and PDF diagnostics are
bundled into one task per HATS partition so their comparisons use identical
rows without duplicating the heavy Nested read.

## N(z) display range and low-redshift peaks

The standard configurations report `low_z_fraction` for `z <= 0.1` and the
fractions in the first and last redshift-grid bins. The scalar fraction is
counted directly from every finite point estimate in the complete HATS catalog;
the PDF value is posterior mass on grid points at or below the threshold within
the explicitly reported PDF-QA coverage. These metrics help distinguish a
concentration of point-estimate modes at `z = 0` from posterior probability in
the stacked PDFs without presenting the bounded DP2-v3 PDF subset as global.

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
- within the configured PDF-QA partitions, full-row Nested checks for a common
  float32 `xvals` grid, float32 `yvals`, expected vector length, finite
  non-negative values, and positive PDF sums;
- commutative `objectId` fingerprints between the scalar and PDF projections;
- global moments and histogram percentiles for scalar point estimates;
- a four-panel `zmean` comparison for the uncut, magnitude-limited,
  extended-source, and combined DP2-v3 samples;
- PDF raw-sum diagnostics before per-object normalization;
- complete-catalog interval-validity and redshift-edge diagnostics, with the
  interval-width median explicitly identified as a deterministic sample;
- total-variation and Wasserstein distances between point estimates and PDFs
  on identical PDF-QA rows, emitted only when the selected identifier
  fingerprints match and all PDFs and scalar values are valid on the common
  grid;
- a deterministic sampled reconstruction of all five HATS summaries from valid
  PDFs and their matching HATS rows.

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
cross-check sample. DP2-v3 scans every HATS partition for scalar science
metrics and only the configured subset for heavy Nested-PDF diagnostics.

Required packages are `lsdb`, `nested-pandas`, `dask`, `distributed`,
`dask-jobqueue` for SLURM, `pandas`, `numpy`, `pyarrow`, `matplotlib`, and
`pyyaml`.
