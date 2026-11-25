# DNF cModel QA notebook

`dnf_cmodel_griz_riz_qa.ipynb` reports catalog sizes, column names, global
descriptive statistics, and global histograms of `dnf_z_best` and `DNF_ZN`
for both band selections. One distributed scan per HATS catalog computes
those summaries and gathers the rows matching the spectroscopic test objects.

Place `dp2_clean_test_set.parquet` in `$PZ_DP2_ROOT/common/validation/` or
set `PZ_QA_TEST_SET` to its path. The test set should contain
`objectId`, `redshift`, `instrument_type_homogenized`, and
`z_flag_homogenized`. Prepare it from the matched reference catalog by
retaining type `s` and excluding every `objectId` in the actual training
catalog. The notebook reports separate results for quality flag 4 and for
flags 3 and 4 together. It collapses repeat measurements per object and
documents its rule for conflicting redshifts.

The accuracy comparison reports match and estimate counts, paired metrics
for `dnf_z_mean`, `dnf_z_best`, and `DNF_ZN`, and empirical coverage of
the 68% and 95% intervals. The metrics apply to the selected spectroscopic
sample. The notebook reads scalar HATS columns.

After both Stage 3 products validate, render the delivery artifacts with:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
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

The default SLURM profile starts 48 adaptive workers and can scale to 96, with
two cores, one process, 40 GiB, and one hour per worker in `cpu_photoz`. These
settings can be overridden before rendering:

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

The scheduler and workers use the system-selected routable interface by
default. Set `PZ_QA_DASK_INTERFACE` only when the same named interface is
available on both the notebook host and SLURM worker nodes.

Local mode exists for small development fixtures. It is not the recommended
mode for scanning the full Apollo products.
