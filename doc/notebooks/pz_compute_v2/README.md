# Simple scalar-only HATS QA

This directory contains a lightweight characterization notebook for final HATS
photo-z catalogs. It intentionally does not read, reconstruct, normalize, or
validate PDFs. Nested columns are listed in the schema and then excluded from
all distributed projections.

The notebook reports:

- row, column, and HATS-partition counts;
- every available top-level column in a scrollable HTML box;
- schema and dtype information;
- `describe`-style statistics for every numeric scalar column;
- selected-row counts for the configured samples;
- global and optionally filtered redshift distributions, as counts and
  normalized shapes.

## Run

From the repository root:

```bash
PZ_QA_CONFIG=doc/notebooks/pz_compute_v2/config/dp2-v3-fzboost.yaml \
  jupyter lab
```

Open `doc/notebooks/pz_compute_v2/pz_compute_qa.ipynb` and run all cells.
Equivalent configurations are provided for BPZ, DNF, and the BPZ test product.
Two additional FlexZBoost examples use the `hpc-public` account:

- `config/dp2-v3-fzboost-hpc-public.yaml` for the LIneA-produced HATS catalog;
- `config/dp2-v3-fzboost-rubin-hpc-public.yaml` for the multi-algorithm
  reference catalog.

## Configuration

`redshift.column` selects the scalar estimate used in the histograms. The
displayed interval and bin count are set by `minimum`, `maximum`, and `bins`.
The default DP2-v3 configurations use each algorithm's `*_z_best` column.
By default, the `describe` table covers every numeric scalar column. For a
multi-algorithm catalog, `describe.include_contains` limits that table using
case-insensitive column-name substrings. The Rubin FlexZBoost example therefore
describes only columns whose names contain `fzboost` while still listing the
complete catalog schema.

The optional `report` section supplies the author, contact, and timezone. The
notebook evaluates the current date at execution time in that timezone:

```yaml
report:
  author: Luigi Lucas de Carvalho Silva
  contact: luigi.lcsilva@gmail.com
  timezone: America/Sao_Paulo
```

Selections are optional and evaluated together in one scalar projection. A
selection may combine `equals`, `minimum`, `maximum`, and `finite` filters:

```yaml
selections:
  - name: all
    label: All objects
  - name: i_lt_26
    label: "i_gaap1p0Mag_sfd < 26"
    filters:
      - column: i_gaap1p0Mag_sfd
        maximum: 26.0
        finite: true
  - name: extended
    label: "refExtendedness == 1"
    filters:
      - column: refExtendedness
        equals: 1
        finite: true
```

Multiple filters use logical AND. Lower bounds are inclusive and upper bounds
are exclusive. At least one unfiltered selection is required for the global
distribution.

### Optional spectroscopic comparison

The supplied DP2 YAMLs enable two side-by-side heatmaps of the configured
`redshift.column` versus the spectroscopic redshift, using the shared test set
under `common/validation/`. Set `paths.spectroscopic_test_set: null` to skip
this section, or override the path for a different environment:

```yaml
paths:
  spectroscopic_test_set: ${PZ_DP2_ROOT}/common/validation/dp2_clean_test_set.parquet

spectroscopic_plot:
  minimum: 0.0
  maximum: 2.0
```

Both axes use the same configured range, and the colorbar shows object counts
per bin on a logarithmic scale. The plotted range affects the heatmaps only.
The comparison metrics use the full matched sample with finite estimates.

Use a test set matched by `objectId` to the same Object catalog and excluded
from the estimator's training set. The notebook uses spectroscopy (instrument
type `s`) and reports flag 4 alone and flags 3+4 together. For repeat
measurements, it keeps the highest flag, takes the median for measurements
whose normalized spread is at most 0.001, and excludes conflicting objects.
The table reports sample sizes, median normalized residual, NMAD, and
outlier fraction. The optional CSV export also writes
`spectroscopic-metrics.csv`.

Set `paths.report_dir` to write `schema.csv`, `describe.csv`,
`selection-counts.csv`, `redshift-histograms.csv`, and `summary.json`.

Required packages are `lsdb`, `dask`, `distributed`, `dask-jobqueue` for
SLURM, `pandas`, `numpy`, `matplotlib`, and `pyyaml`.
