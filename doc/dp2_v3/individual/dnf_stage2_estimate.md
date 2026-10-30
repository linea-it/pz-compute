# DP2 DNF Stage 2: estimate all catalogs

This is the canonical individual path for official six-band DP2 DNF. The run
stays under `$PZ_DP2_ROOT/dnf/stage2/`.

## 1. Check the model and run the smoke test

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

test -f "$PZ_DP2_ROOT/dnf/stage1/model/model_dp2_v3p1_dnf_dp2_6band_gold.pickle"
doc/dp2_v3/scripts/validate-models.py dnf
PZ_SMOKE_ROWS=10000 doc/dp2_v3/scripts/smoke-estimates.sh dnf
```

The smoke path projects 10,000 rows, materializes the reviewed LSSTCam SFD
columns, runs DNF with the versioned configuration, and writes model, YAML,
and SFD-configuration checksums to
`$PZ_DP2_ROOT/dnf/stage2/smoke/READY`.

## 2. Run and profile the mandatory five-file pilot

Prepare the manifests using the
[shared procedure](../common/prepare_estimation_manifests.md), then submit the
five largest shards:

```bash
pilot=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
PZ_INPUT_MANIFEST="$pilot" \
PZ_DNF_MAX_CONCURRENT=5 \
  doc/dp2_v3/scripts/submit-estimates.sh dnf
```

Save the pilot ID before making another submission. Use the
[Stage 2 terminal commands](inspect_runs.md#stage-2-estimation-array) with
`algorithm=dnf` to monitor it. Once all five tasks have completed, create the
pilot benchmark:

```bash
stage2=$PZ_DP2_ROOT/dnf/stage2
pilot_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
pilot_manifest=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
pilot_expected=$(wc -l < "$pilot_manifest")
test -n "$pilot_jobid"

performance/slurm/slurm-profile \
  --job-id "$pilot_jobid" \
  --expected-jobs "$pilot_expected" \
  --concurrency-target 5 \
  --cluster-context-nodes 'apl[01-26]' \
  --label "dnf-stage2-pilot-$pilot_jobid" \
  --output-dir "$stage2/benchmark/pilot-$pilot_jobid" \
  --fail-on-unsuccessful

cat "$stage2/benchmark/pilot-$pilot_jobid/summary.log"
```

Pilot array job `217097` completed all five largest shards. Its maximum RSS was
28.57 GiB, its longest task took 56 minutes 26 seconds, and aggregate CPU use
was 0.994 logical CPU per running task. The resulting defaults are 82
concurrent tasks, 40 GiB, and two hours per task. The memory request retains a
40.0% margin over the observed maximum; the throttle is 95% of the 86 tasks
that fit by memory across the former `apl01-25` topology. With `apl26` now
included, the same throttle uses at most 82 of 92 discrete 40-GiB slots and
intentionally leaves coexistence headroom. See
[`dnf_runs.md`](../references/dnf_runs.md) for the measurements and capacity
calculation. Override `PZ_DNF_MAX_CONCURRENT`, `PZ_DNF_MEMORY`, and
`PZ_DNF_TIME` only when newer pilot evidence or a different partition supports
a change.

## 3. Submit and profile the complete catalog

After accepting the pilot:

```bash
doc/dp2_v3/scripts/submit-estimates.sh dnf

stage2=$PZ_DP2_ROOT/dnf/stage2
production_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
test -n "$production_jobid"
```

Use the [Stage 2 terminal commands](inspect_runs.md#stage-2-estimation-array)
with `algorithm=dnf` to watch task states and output counts, summarize
completed and failed tasks, inspect logs, and validate every HDF5 afterward.

After the array leaves `squeue`, all tasks are successful, and Stage 2
validation passes, generate its production benchmark:

```bash
stage2=$PZ_DP2_ROOT/dnf/stage2
production_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
production_manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
production_expected=$(wc -l < "$production_manifest")
test -n "$production_jobid"

performance/slurm/slurm-profile \
  --job-id "$production_jobid" \
  --expected-jobs "$production_expected" \
  --concurrency-target 82 \
  --cluster-context-nodes 'apl[01-26]' \
  --label "dnf-stage2-production-$production_jobid" \
  --output-dir "$stage2/benchmark/production-$production_jobid" \
  --fail-on-unsuccessful

cat "$stage2/benchmark/production-$production_jobid/summary.log"
```

If retries are needed, retain every array ID. The generic
[Slurm profiling guide](../../slurm_profile.md) explains how to combine all
attempts with `--job-id-file` instead of profiling only the last array.

Outputs and logs remain isolated:

```text
$PZ_DP2_ROOT/dnf/stage2/
├── output/Norder=*/Dir=*/Npix=*.hdf5
├── log/slurm-*.{out,err}
├── smoke/
│   ├── smoke-test.hdf5
│   └── READY
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Complete HDF5 files are validated and skipped on resubmission. The scientific
feature, neighbor, PDF, missing-data, and version contracts are documented in
[`dnf_science.md`](../references/dnf_science.md).

Continue with [`dnf_stage3_build_hats.md`](dnf_stage3_build_hats.md).
