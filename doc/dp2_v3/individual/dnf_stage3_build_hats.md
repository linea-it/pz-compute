# DP2 DNF Stage 3: build the HATS products

Load the shared Stage 3 environment and submit DNF only:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-hats.sh dnf
```

The default Dask cluster starts with one requested worker and scales adaptively
up to 80. Each worker requests 2 CPUs, 40 GiB, and 12 hours; idle workers become
eligible for scale-down after approximately 180 seconds. There is no
`wait_for_workers` barrier, so work can begin with the first worker Slurm can
start. Override `PZ_HATS_MIN_WORKERS`, `PZ_HATS_MAX_WORKERS`, or
`PZ_HATS_SCALE_DOWN_DELAY` before submission when required.

The single worker process therefore runs at most two concurrent tasks sharing
the 40 GiB allocation. This limit protects the memory-intensive hats-import
reduction from the OOM failures observed with eight concurrent threads.

Use the [Stage 3 terminal commands](inspect_runs.md#stage-3-hats-build) with
`algorithm=dnf` to follow the driver, inspect Dask worker logs, check its exit
marker, and validate the final row counts and schemas.

After the driver completes, validate the DNF products:

```bash
doc/dp2_v3/scripts/validate-hats.py dnf
```

The final `pz_summary` HATS catalog contains the scalar columns and the
DP1-inspired nested column `dnf_ens_interp`, whose `xvals` and `yvals` fields
each contain 601 `float32` values. The validator opens it with LSDB,
reconstructs a small `qp.Ensemble`, checks PDF health and reconstructed
summaries, and compares the HATS and Stage 2 row counts without a full PDF
scan.

Successful construction removes `<hats_dir>.parquet_staging/` automatically
and does not create a duplicate `<hats_dir>.pdf/` companion. Keep the Stage 2
HDF5 tree through validation and profiling, especially for the first nested
production run.

For the optional full-catalog notebook QA, start Jupyter with:

```bash
PZ_QA_CONFIG=doc/notebooks/config/dp2-v3-dnf.yaml jupyter lab
```

## Profile the driver and Dask workers

After validation passes, recover the driver ID and run tag from the submission
ledger. Profile the driver separately because it is the authoritative Slurm
job for end-to-end Stage 3 success:

```bash
stage3=$PZ_DP2_ROOT/dnf/stage3
IFS=$'\t' read -r submitted recorded_algorithm jobid run_tag < \
  <(tail -n 1 "$stage3/submitted-job-ids.tsv")
test "$recorded_algorithm" = dnf
test -n "$jobid"
test -n "$run_tag"

benchmark_dir=$stage3/benchmark/$run_tag
driver_logs=$stage3/log/driver-$run_tag
worker_logs=$stage3/log/dask-$run_tag

performance/slurm/slurm-profile \
  --job-id "$jobid" \
  --expected-jobs 1 \
  --concurrency-target 1 \
  --label "dnf-stage3-driver-$jobid" \
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
  --label "dnf-stage3-workers-$run_tag" \
  --output-dir "$benchmark_dir/workers" \
  --capture-slurm-snapshot

cat "$benchmark_dir/driver/summary.log"
cat "$benchmark_dir/workers/summary.log"
cat "$driver_logs/driver-resource-usage.log"
```

Do not add `--fail-on-unsuccessful` to the worker profile: adaptive Dask can
cancel healthy workers while scaling down or closing the cluster. Stage 3
success requires the completed driver, its zero exit marker, clean logs, and a
successful HATS validation. Cluster context is collected on the worker profile
so the workflow's own workers are not misclassified as external cluster load.

All DNF-attributable output remains under:

```text
$PZ_DP2_ROOT/dnf/stage3/
├── output/
│   └── pz-dnf-gaap1p0-clipped-hats/
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

The HATS catalog retains the common scalar statistics,
`i_gaap1p0Mag_sfd`, `refExtendedness`, and the nested 601-bin PDFs.
DNF-specific Stage 2 ancillary values remain in the estimator HDF5 files and
are not added to the common HATS schema by this workflow.
