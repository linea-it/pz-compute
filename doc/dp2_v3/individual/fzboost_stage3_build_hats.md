# DP2 FlexZBoost Stage 3: build the HATS products

Load the shared Stage 3 environment, then submit FlexZBoost only:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-hats.sh fzboost
```

The default Dask cluster starts with one requested worker and scales adaptively
up to 80. Each worker requests 2 CPUs, 40 GiB, and 12 hours; idle workers become
eligible for scale-down after approximately 180 seconds. There is no
`wait_for_workers` barrier, so work can begin with the first worker Slurm can
start. Override `PZ_HATS_MIN_WORKERS`, `PZ_HATS_MAX_WORKERS`,
`PZ_HATS_SCALE_DOWN_DELAY`, or the default 5 arcsecond margin through
`PZ_HATS_MARGIN_ARCSEC` before submission when required.

The single worker process therefore runs at most two concurrent tasks sharing
the 40 GiB allocation. This limit protects the memory-intensive hats-import
reduction from the OOM failures observed with eight concurrent threads.

Use the [Stage 3 terminal commands](inspect_runs.md#stage-3-hats-build) with
`algorithm=fzboost` to follow the driver, inspect Dask worker logs, check its
exit marker, and validate the final row counts and schemas.

After the driver completes, validate this product with:

```bash
doc/dp2_v3/scripts/validate-hats.py fzboost
```

The final catalog is `pz_summary` inside the HATS collection. In addition to
the scalar columns, it contains the DP1-inspired nested column
`fzboost_ens_interp`, with `xvals` and `yvals` lists of 601 `float32` values.
The validator opens the catalog through LSDB, reconstructs a small
`qp.Ensemble`, checks a bounded sample of PDFs and their scalar summaries, and
compares the HATS row count with Stage 2. It intentionally does not scan every
601-bin PDF.

Successful construction deletes `<hats_dir>.parquet_staging/` automatically,
and this DP2 v3 route does not create a duplicate `<hats_dir>.pdf/` companion.
Stage 2 HDF5 files remain until this external validation and the resource
profiles below are complete; retain them for the first nested production run.

For the optional full-catalog notebook QA, start Jupyter with:

```bash
PZ_QA_CONFIG=doc/notebooks/config/dp2-v3-fzboost.yaml jupyter lab
```

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

performance/slurm/slurm-profile \
  --job-id "$jobid" \
  --expected-jobs 1 \
  --concurrency-target 1 \
  --label "fzboost-stage3-driver-$jobid" \
  --output-dir "$benchmark_dir/driver" \
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
worker_target=${PZ_HATS_MAX_WORKERS:-80}
test "$worker_count" -gt 0

performance/slurm/slurm-profile \
  --job-id-file "$benchmark_dir/worker-job-ids.txt" \
  --expected-jobs "$worker_count" \
  --concurrency-target "$worker_target" \
  --cluster-context-nodes 'apl[01-28]' \
  --label "fzboost-stage3-workers-$run_tag" \
  --output-dir "$benchmark_dir/workers" \
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
    ├── worker-job-ids.txt
    ├── worker-job-name.txt
    └── run-context.log
```

Both profile directories contain a lightweight `slurm-snapshot/` for future
shared-versus-exclusive cluster comparisons.

Technical history and the evidence required to certify a new production run
are documented in [`fzboost_runs.md`](../references/fzboost_runs.md).
