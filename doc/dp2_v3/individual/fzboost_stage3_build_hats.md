# DP2 FlexZBoost Stage 3: build the HATS products

Load the shared Stage 3 environment, then submit FlexZBoost only:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

PZ_HATS_MAX_WORKERS=64 \
PZ_HATS_WORKER_TIME=03:00:00 \
PZ_HATS_DRIVER_TIME=06:00:00 \
PZ_HATS_DRIVER_MEMORY=12G \
  doc/dp2_v3/scripts/submit-hats.sh fzboost
```

The FlexZBoost Dask cluster starts with one requested worker and scales
adaptively up to 64. Each worker requests 2 CPUs, 40 GiB, and 3 hours; idle
workers become eligible for scale-down after approximately 180 seconds. There
is no `wait_for_workers` barrier, so work can begin with the first worker Slurm
can start. The driver requests 2 CPUs, 12 GiB, and 6 hours. Override
`PZ_HATS_MIN_WORKERS`, `PZ_HATS_MAX_WORKERS`, `PZ_HATS_WORKER_TIME`,
`PZ_HATS_DRIVER_TIME`, `PZ_HATS_DRIVER_MEMORY`, `PZ_HATS_SCALE_DOWN_DELAY`, or
the default 5 arcsecond margin through `PZ_HATS_MARGIN_ARCSEC` before
submission when required.

The single worker process therefore runs at most two concurrent tasks sharing
the 40 GiB allocation. This limit protects the memory-intensive hats-import
reduction from the OOM failures observed with eight concurrent threads. Do not
reduce worker memory from 40 GiB: the v3 profile measured 37.99 GiB at p95 and
38.00 GiB at maximum, or 95% of the allocation. The worker profile also
measured 86.73% CPU efficiency, supporting the current two-CPU shape. The
driver peaked at 7.60 GiB, or 94.98% of its former 8-GiB request, which is why
the individual command now requests 12 GiB.

Use the [Stage 3 terminal commands](inspect_runs.md#stage-3-hats-build) with
`algorithm=fzboost` to follow the driver, inspect Dask worker logs, check its
exit marker, and validate the final row counts and schemas.

After the driver completes, validate this product with:

```bash
doc/dp2_v3/scripts/validate-hats.py fzboost
```

The final catalog is `pz_summary` inside the HATS collection. Its ordered
top-level schema is:

```text
objectId
coord_ra
coord_dec
fzboost_z_mode
fzboost_z_mean
fzboost_z_median
fzboost_z_best
fzboost_z_err68_low
fzboost_z_err68_high
fzboost_z_err95_low
fzboost_z_err95_high
i_gaap1p0Mag_sfd
refExtendedness
fzboost_ens_interp
```

The scalar photo-z names and `float32` representation follow the public Rubin
DP2 photo-z schema, while `coord_ra` and `coord_dec` deliberately retain the
original DP2 Object provenance. The scientific definitions and numerical
integration policy are documented in the [DP2 v3 overview](../README.md).
The DP1-inspired nested column `fzboost_ens_interp` contains `xvals` and
`yvals` lists of 601 `float32` values.
The validator opens the catalog through LSDB, reconstructs a small
`qp.Ensemble`, checks a bounded sample of PDFs and their scalar summaries, and
compares the HATS row count with Stage 2. It intentionally does not scan every
601-bin PDF.

Successful construction deletes `<hats_dir>.parquet_staging/` automatically,
and this DP2 v3 route does not create a duplicate `<hats_dir>.pdf/` companion.
Stage 2 HDF5 files remain until this external validation and the resource
profiles below are complete; retain them for the first nested production run.

For the optional full-catalog science notebook QA, start Jupyter with:

```bash
PZ_QA_CONFIG=doc/notebooks/pz_compute_v2/config/dp2-v3-fzboost.yaml jupyter lab
```

Open `doc/notebooks/pz_compute_v2/pz_compute_qa.ipynb` for the lightweight,
scalar-only HATS characterization.

## Profile the driver and Dask workers

After validation passes, recover the driver ID and run tag from the submission
ledger. Profile the driver separately because it is the authoritative Slurm
job for end-to-end Stage 3 success:

```bash
stage3=$PZ_DP2_ROOT/fzboost/stage3
IFS=$'\t' read -r submitted recorded_algorithm jobid run_tag < \
  <(tail -n 1 "$stage3/submitted-job-ids.tsv")
test "$recorded_algorithm" = fzboost
test -n "$jobid"
test -n "$run_tag"

benchmark_dir=$stage3/benchmark/$run_tag
driver_logs=$stage3/log/driver-$run_tag
worker_logs=$stage3/log/dask-$run_tag
run_context=$benchmark_dir/run-context.log
worker_name=$benchmark_dir/worker-job-name.txt

performance/slurm/slurm-profile \
  --job-id "$jobid" \
  --expected-jobs 1 \
  --concurrency-target 1 \
  --label "fzboost-stage3-driver-$jobid" \
  --output-dir "$benchmark_dir/driver" \
  --context algorithm=fzboost \
  --context stage=3 \
  --context role=driver \
  --context-file "$run_context" \
  --context-file "$worker_name" \
  --storage-path "$PZ_DP2_ROOT" \
  --capture-slurm-snapshot \
  --fail-on-unsuccessful
```

Then recover every submitted worker ID from its run-specific Slurm job name,
union that accounting result with the started-worker logs, and profile the
actual allocation and concurrency:

```bash
doc/dp2_v3/scripts/collect-hats-worker-job-ids.sh \
  "$benchmark_dir" "$worker_logs"

worker_count=$(wc -l < "$benchmark_dir/worker-job-ids.txt")
worker_target=${PZ_HATS_MAX_WORKERS:-64}
test "$worker_count" -gt 0

performance/slurm/slurm-profile \
  --job-id-file "$benchmark_dir/worker-job-ids.txt" \
  --expected-jobs "$worker_count" \
  --concurrency-target "$worker_target" \
  --cluster-context-nodes 'apl[01-28]' \
  --label "fzboost-stage3-workers-$run_tag" \
  --output-dir "$benchmark_dir/workers" \
  --context algorithm=fzboost \
  --context stage=3 \
  --context role=worker \
  --context-file "$run_context" \
  --context-file "$worker_name" \
  --storage-path "$PZ_DP2_ROOT" \
  --capture-slurm-snapshot

cat "$benchmark_dir/driver/summary.log"
cat "$benchmark_dir/workers/summary.log"
cat "$driver_logs/driver-resource-usage.log"
```

Do not add `--fail-on-unsuccessful` to the worker profile: adaptive Dask can
cancel healthy workers while scaling down or closing the cluster. Stage 3
success requires the completed driver, its zero exit marker, clean logs, and a
successful HATS validation. The worker profile measures resource use and
scheduler behavior; `driver-resource-usage.log` retains the authoritative
end-to-end `pz-build-hats` timing. Cluster context is collected on the worker
profile rather than the driver profile so the workflow's own workers are not
misclassified as external cluster load.

All FlexZBoost-attributable output remains under:

```text
$PZ_DP2_ROOT/fzboost/stage3/
├── output/
│   └── pz-fzboost-gaap1p0-clipped-hats/
├── log/
│   ├── dask-*/
│   └── driver-*/
├── smoke/
└── benchmark/<run-tag>/
    ├── driver/
    ├── workers/
    ├── live/  # when slurm-watch is used
    ├── worker-job-ids.txt
    ├── worker-job-name.txt
    └── run-context.log
```

Both profile directories contain a lightweight `slurm-snapshot/`, compressed
accounting, storage capacity, and checksummed Stage 3 context. The `live/`
directory retains transient scheduler, step-resource, I/O, and storage samples.

Technical history and the evidence required to certify a new production run
are documented in [`fzboost_runs.md`](../references/fzboost_runs.md).
