# DP2 BPZ test Stage 3: build standalone HATS products

> **TEST ONLY:** this creates an engineering HATS catalog, not an official DP2
> BPZ product.

Stage 3 requires every input shard to have a corresponding completed HDF5
below `bpz_test/stage2/output`. It does not inspect or consume `bpz/stage2`.

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-hats.sh bpz_test
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
`algorithm=bpz_test` to follow the driver, inspect Dask worker logs, check its
exit marker, and validate the final test-product row counts and schemas.

After the driver and Dask workers complete, validate only the test product:

```bash
doc/dp2_v3/scripts/validate-hats.py bpz_test
```

The engineering `pz_summary` catalog embeds the PDFs in
`bpz_test_ens_interp`, using 601-element `float32` `xvals` and `yvals` lists.
The lightweight validator opens the catalog with LSDB, reconstructs a bounded
sample through `qp`, checks PDF health and summaries, and compares the HATS
and Stage 2 row counts.

Successful construction removes `<hats_dir>.parquet_staging/` automatically
and does not retain a duplicate `<hats_dir>.pdf/` tree. Keep the Stage 2 HDF5
tree through validation because this test workflow may still require
investigation of BPZ warnings.

For the optional full-catalog notebook QA, start Jupyter with:

```bash
PZ_QA_CONFIG=doc/notebooks/config/dp2-v3-bpz-test.yaml jupyter lab
```

## Profile the test driver and Dask workers

After validation passes, recover the test driver ID and run tag from its
independent submission ledger:

```bash
stage3=$PZ_DP2_ROOT/bpz_test/stage3
IFS=$'\t' read -r submitted recorded_algorithm jobid run_tag < \
  <(tail -n 1 "$stage3/submitted-job-ids.tsv")
test "$recorded_algorithm" = bpz_test
test -n "$jobid"
test -n "$run_tag"

benchmark_dir=$stage3/benchmark/$run_tag
driver_logs=$stage3/log/driver-$run_tag
worker_logs=$stage3/log/dask-$run_tag

performance/slurm/slurm-profile \
  --job-id "$jobid" \
  --expected-jobs 1 \
  --concurrency-target 1 \
  --label "bpz-test-stage3-driver-$jobid" \
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
  --label "bpz-test-stage3-workers-$run_tag" \
  --output-dir "$benchmark_dir/workers" \
  --capture-slurm-snapshot

cat "$benchmark_dir/driver/summary.log"
cat "$benchmark_dir/workers/summary.log"
cat "$driver_logs/driver-resource-usage.log"
```

Do not add `--fail-on-unsuccessful` to the worker profile: adaptive Dask can
cancel healthy workers while scaling down or closing the cluster. Success
still requires the completed test driver, its zero exit marker, clean logs,
and successful test-product validation. These artifacts are engineering
benchmarks and must not be cited as official BPZ measurements.

All artifacts remain visibly separated:

```text
$PZ_DP2_ROOT/bpz_test/stage3/
├── output/
│   └── pz-bpz_test-gaap1p0-clipped-hats/
├── log/{dask-*,driver-*}/
├── benchmark/<run-tag>/
│   ├── driver/
│   ├── workers/
│   ├── worker-job-ids.txt
│   ├── worker-job-name.txt
│   └── run-context.log
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Both profile directories contain a lightweight `slurm-snapshot/` for future
shared-versus-exclusive cluster comparisons.

Do not rename, copy, or publish this tree as `bpz`. Its scientific limitations
remain those documented in
[`bpz_test_science.md`](../references/bpz_test_science.md).
