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

## Configuration

`redshift.column` selects the scalar estimate used in the histograms. The
displayed interval and bin count are set by `minimum`, `maximum`, and `bins`.
The default DP2-v3 configurations use each algorithm's `*_z_best` column.

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

Set `paths.report_dir` to write `schema.csv`, `describe.csv`,
`selection-counts.csv`, `redshift-histograms.csv`, and `summary.json`.

Required packages are `lsdb`, `dask`, `distributed`, `dask-jobqueue` for
SLURM, `pandas`, `numpy`, `matplotlib`, and `pyyaml`.
