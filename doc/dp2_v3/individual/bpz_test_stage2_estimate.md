# DP2 BPZ test Stage 2: estimate with COSMOS31

> **TEST ONLY:** outputs may be used for engineering and preliminary resource
> measurements, not as official DP2 BPZ or scientific products.

Everything in this procedure stays below `$PZ_DP2_ROOT/bpz_test/stage2/`.

## 1. Load and verify the independent test model

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

test -f "$PZ_DP2_ROOT/bpz_test/stage1/model/model_dp2_v3p1_bpz_test_cosmos31_gold.pickle"
doc/dp2_v3/scripts/validate-models.py bpz_test
```

The launcher discovers the public RAIL reference-data directory automatically.
If a separate copy is required, set only the test-specific override:

```bash
export PZ_BPZ_TEST_DATA_ROOT=/absolute/path/to/cosmos31-reference-data
```

See [`bpz_test_science.md`](../references/bpz_test_science.md) for the required
layout and scientific limitations.

## 2. Run the mandatory smoke test

```bash
PZ_SMOKE_ROWS=10000 doc/dp2_v3/scripts/smoke-estimates.sh bpz_test
```

This validates `COSMOS_seds.list`, all 31 SEDs, six filters, and AB-cache
writability; then it checksums those files together with the test model and
test YAML in:

```text
$PZ_DP2_ROOT/bpz_test/stage2/smoke/READY
```

Never bypass this warm-up: BPZ may create AB cache files, and concurrent array
tasks must not race to initialize them.

## 3. Run the five-file pilot

Prepare the manifests using the
[shared procedure](../common/prepare_estimation_manifests.md), then run:

```bash
pilot=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
PZ_INPUT_MANIFEST="$pilot" \
PZ_BPZ_TEST_MAX_CONCURRENT=5 \
  doc/dp2_v3/scripts/submit-estimates.sh bpz_test
```

Inspect its recorded job and resource usage before changing the defaults:

```bash
jobid=$(tail -1 "$PZ_DP2_ROOT/bpz_test/stage2/submitted-job-ids.tsv" | cut -f3)
sacct -j "$jobid" --units=G \
  --format=JobID%30,State,ExitCode,Elapsed,TotalCPU,AllocCPUS,MaxRSS,ReqMem
```

Pilot array job `217091` completed all five largest shards. Its maximum RSS was
20.53 GiB, its longest task took 53 minutes 31 seconds, and aggregate CPU use
was 0.993 logical CPU per running task. A subsequent full-catalog attempt with
24 GiB produced OOM kills, and a retry also killed task 21 with 26 GiB, so both
requests are rejected. The revised trial defaults are 105 concurrent tasks,
32 GiB, and two hours per task. This is 55.9% above the pilot maximum; the
concurrency is 95% of the 111 tasks that fit by memory across `apl01-25`. See
[`bpz_test_runs.md`](../references/bpz_test_runs.md) for the measurements and
capacity calculation. Treat 32 GiB as provisional until the failed tasks have
completed successfully on retry.

Override these values with `PZ_BPZ_TEST_MAX_CONCURRENT`,
`PZ_BPZ_TEST_MEMORY`, and `PZ_BPZ_TEST_TIME` only when newer test-pilot
evidence supports a change. These measurements do not predict official
136-template BPZ reliably.

## 4. Run the full test estimate

```bash
doc/dp2_v3/scripts/submit-estimates.sh bpz_test
```

Use the [Stage 2 terminal commands](inspect_runs.md#stage-2-estimation-array)
with `algorithm=bpz_test` to watch task states and output counts, summarize
completed and failed tasks, inspect logs, and validate every test HDF5
afterward.

Outputs and logs remain in:

```text
$PZ_DP2_ROOT/bpz_test/stage2/
├── output/Norder=*/Dir=*/Npix=*.hdf5
├── log/
├── smoke/
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

`bpz_test` is not accepted by any batch guide and is never included in `all`.
Continue with [`bpz_test_stage3_build_hats.md`](bpz_test_stage3_build_hats.md).
