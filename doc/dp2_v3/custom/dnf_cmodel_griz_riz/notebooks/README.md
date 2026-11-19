# DNF cModel QA notebook

`dnf_cmodel_griz_riz_qa.ipynb` builds a compact, delivery-oriented QA report
for the completed `griz` and `riz` scalar HATS catalogs. It reads the final
HATS products, their Stage 3 validation records, and the persisted Stage 2 DNF
quality counters. It does not modify any run artifact.

The report deliberately distinguishes exact catalog-wide results from the
deterministic hash sample used only for the object-by-object `griz`/`riz`
comparison. Histograms, extrema, integrity counts, missing-photometry counts,
DNF diagnostic counters, and identifier fingerprints are global.

The HATS scan starts a Dask `SLURMCluster` by default. Each catalog is opened
with `lsdb.open_catalog()`, projected to the 11 required columns, and scanned
once across all main-catalog partitions. Workers return only fixed-size
histograms, counters, three 64-bit identifier fingerprints, and the small
deterministic sample. The Stage 2 pass opens HDF5 files only to read persisted
attributes and remains sequential to avoid a burst of metadata operations.

After both Stage 3 products validate, render the delivery artifacts with:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/custom/dnf_cmodel_griz_riz/notebooks/render-qa.sh
```

By default the command writes below `$PZ_DP2_CUSTOM_ROOT/qa/delivery`. Override
that location with `PZ_QA_OUTPUT_DIR`. The selected `PZ_PY` environment must
provide `nbclient`, `nbconvert`, and `nbformat`; the renderer fails before
creating artifacts if those Jupyter components are unavailable. Distributed
execution additionally requires `distributed` and `dask-jobqueue`. The result
contains:

```text
dnf_cmodel_griz_riz_qa.ipynb  # executed notebook with code and outputs
dnf_cmodel_griz_riz_qa.html   # rendered report with code inputs hidden
qa_summary.json               # machine-readable aggregate QA record
SHA256SUMS                    # checksums for the three delivery artifacts
```

The HTML and executed notebook are product-level scientific QA records.
Accuracy and calibration metrics require a representative external reference
sample and belong to a separate analysis. The notebook stops with an error if
the final schema, null pattern, interval ordering, grid support, row counts,
or persisted numerical-failure counters violate the documented contract.

Default Dask settings match the established DP2 QA profile: one initial
adaptive worker, up to eight workers, two cores, one process, 40 GiB, and one
hour in `cpu_photoz`. They can be overridden before rendering:

```text
PZ_QA_DASK_CLUSTER=slurm|local
PZ_QA_DASK_MINIMUM_JOBS
PZ_QA_DASK_MAXIMUM_JOBS
PZ_QA_DASK_CORES
PZ_QA_DASK_MEMORY
PZ_QA_DASK_QUEUE
PZ_QA_DASK_ACCOUNT
PZ_QA_DASK_INTERFACE
PZ_QA_DASK_WALLTIME
PZ_QA_DASK_WAIT_TIMEOUT
```

Local mode exists for small development fixtures. It is not the recommended
mode for scanning the full Apollo products.
