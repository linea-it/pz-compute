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

The named files above are product-specific examples; version and algorithm
names are not encoded in the notebook. The first two use the Companion layout,
while the remaining examples read the configured Nested column directly from
the final HATS catalog. A Nested `paths.summary_hats` points to the collection
root, which the QA code opens with `lsdb.open_catalog()`. LSDB selects the main
catalog without including margin rows in its scan.

Do not recursively read Parquet from a HATS collection root: that would mix
the main catalog with its margin catalog and duplicate boundary objects. Code
that intentionally bypasses LSDB and performs a recursive Parquet read must
start at `<hats_collection>/pz_summary/dataset`, for example:

```text
/scratch/users/app.photoz/pz-compute-runs/dp2-v3/fzboost/stage3/output/
  pz-fzboost-gaap1p0-clipped-hats/pz_summary/dataset
```

The notebook always performs a full distributed scan of the projected scalar
HATS columns used by scientific redshift distributions and selections. A
Nested configuration can bound PDF integrity checks with
`metrics.max_pdf_partitions`, because reading repeated `xvals` and `yvals`
arrays for every object is much more expensive.
PDF-derived results are explicitly technical subset diagnostics, never global
scientific N(z) measurements. The Nested subset consists of the first
configured HATS partitions for reproducibility; because HATS partitions are
spatial, it is not claimed to be statistically representative.
The current Nested SLURM profiles start with one adaptive worker and allow the
scan to begin under cluster contention. Each worker uses one process, two
threads, and 40 GiB so at most two memory-intensive Nested-PDF partition tasks
share that allocation.

From the repository root, start Jupyter with the selected configuration:

```bash
PZ_QA_CONFIG=doc/notebooks/config/dp1-v2-fzboost.yaml jupyter lab
```

Open `doc/notebooks/pz_compute_qa.ipynb` and run all cells. `PZ_QA_CONFIG` is
required deliberately: the notebook will not silently select a product.
Relative configuration paths are resolved relative to the YAML file;
environment variables such as `${PZ_RUN_ROOT}` are expanded.

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

Selections are evaluated together in the same partition passes. The notebook
supports any number of selections and derives their displayed cuts, labels,
interpretations, and caveats from YAML rather than column-name conventions:

```yaml
selections:
  - name: all
    label: Complete catalog
    description: All rows before any configured science selection.
  - name: example_limited_sample
    label: Example limited sample
    description: Scientific interpretation and caveats for this sample.
    filters:
      - column: configured_measurement
        minimum: 1.0
        maximum: 2.0
        finite: true
```

Every filter column must be available in the HATS catalog and, for Companion
products, in the PDF shards. Multiple filters within a selection are combined
with logical AND. `minimum` is inclusive, `maximum` is exclusive, and `finite`
defaults to true. `description` is rendered verbatim as scientific context, so
product-specific semantics must live in the configuration. The `zmean` layout
adapts to the configured number of selections. In Nested mode, all masks share
one global scalar pass. Within bounded PDF-QA coverage, scalar and PDF
diagnostics are bundled per HATS partition so comparisons use identical rows
without duplicating the heavy Nested read.

## N(z) display range and low-redshift peaks

The configurations set `metrics.low_z_threshold`; the report displays its
actual value rather than assuming a particular scientific cut. The scalar
fraction is counted directly from every finite point estimate in the complete
HATS catalog; the PDF value is posterior mass on grid points at or below the
threshold within the explicitly reported PDF-QA coverage. These metrics help
distinguish a concentration of point-estimate modes at `z = 0` from posterior
probability in the stacked PDFs without presenting bounded Nested-PDF coverage
as global.

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
- an adaptive `zmean` comparison for every configured science sample;
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
distributed shuffle is acceptable. The sampled summary reconstruction is an
integration check, not a truth-redshift metric.

Set `paths.report_dir` to save the compact result tables as CSV/JSON. No full
object catalog or PDF matrix is collected into notebook memory. The only
collected objects are fixed-size reductions and the configured deterministic
cross-check sample. Scalar science metrics scan every HATS partition; heavy
Nested-PDF diagnostics use the explicitly configured coverage.

Required packages are `lsdb`, `nested-pandas`, `dask`, `distributed`,
`dask-jobqueue` for SLURM, `pandas`, `numpy`, `pyarrow`, `matplotlib`, and
`pyyaml`.
