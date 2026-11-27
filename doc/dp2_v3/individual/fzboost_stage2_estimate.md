# DP2 FlexZBoost Stage 2: estimate all catalogs

This is the canonical individual path for FlexZBoost. The entire run stays
under `$PZ_DP2_ROOT/fzboost/stage2/`, separate from BPZ and Stage 1.

## 1. Check the model and run the smoke test

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

test -f "$PZ_DP2_ROOT/fzboost/stage1/model/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle"
doc/dp2_v3/scripts/smoke-estimates.sh fzboost
```

The command creates a 10,000-row projected Parquet sample under
`$PZ_DP2_ROOT/common/smoke/` before running the estimator. Set
`PZ_SMOKE_ROWS` to a different positive row count if needed; it does not read a
complete shard into the smoke output. It uses the versioned LSSTCam SFD
coefficients in
[`dp2-v3-sfd-lsstcam.yaml`](../config/dp2-v3-sfd-lsstcam.yaml), and their
checksum is part of the `smoke/READY` marker.

## 2. Run and profile the five-shard pilot

Create the full and five-largest-shard manifests using the
[shared manifest procedure](../common/prepare_estimation_manifests.md), then run:

```bash
PZ_INPUT_MANIFEST=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt \
PZ_FZBOOST_MAX_CONCURRENT=5 \
  doc/dp2_v3/scripts/submit-estimates.sh fzboost
```

Save the pilot ID before making another submission. Use the
[Stage 2 terminal commands](inspect_runs.md#stage-2-estimation-array) with
`algorithm=fzboost` to monitor it. Once all five tasks have completed, create
the pilot benchmark:

```bash
stage2=$PZ_DP2_ROOT/fzboost/stage2
pilot_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
pilot_manifest=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
pilot_metadata=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.metadata.tsv
estimate_config=doc/dp2_v3/config/fzboost-estimate.yaml
pilot_expected=$(wc -l < "$pilot_manifest")
test -n "$pilot_jobid"

performance/slurm/slurm-profile \
  --job-id "$pilot_jobid" \
  --expected-jobs "$pilot_expected" \
  --concurrency-target 5 \
  --cluster-context-nodes 'apl[01-28]' \
  --label "fzboost-stage2-pilot-$pilot_jobid" \
  --output-dir "$stage2/benchmark/pilot-$pilot_jobid" \
  --task-metadata-file "$pilot_metadata" \
  --context algorithm=fzboost \
  --context stage=2 \
  --context scope=pilot \
  --context-file "$pilot_manifest" \
  --context-file "$pilot_metadata" \
  --context-file "$estimate_config" \
  --storage-path "$PZ_DP2_ROOT" \
  --capture-slurm-snapshot \
  --fail-on-unsuccessful

cat "$stage2/benchmark/pilot-$pilot_jobid/summary.log"
```

Require five successful tasks, inspect `MaxRSS` against the 38 GiB request,
and check `Elapsed` against the 30-minute limit before proceeding.

## 3. Submit and profile the complete catalog

Submit the complete manifest with the production defaults:

```bash
doc/dp2_v3/scripts/submit-estimates.sh fzboost

stage2=$PZ_DP2_ROOT/fzboost/stage2
production_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
test -n "$production_jobid"
```

Use the [Stage 2 terminal commands](inspect_runs.md#stage-2-estimation-array)
with `algorithm=fzboost` to watch task states and output counts, summarize
completed and failed tasks, inspect logs, and validate every HDF5 afterward.

After the array leaves `squeue`, all tasks are successful, and Stage 2
validation passes, generate its production benchmark:

```bash
stage2=$PZ_DP2_ROOT/fzboost/stage2
production_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
production_manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
production_metadata=$PZ_DP2_ROOT/common/manifests/input-parquet-files.metadata.tsv
estimate_config=doc/dp2_v3/config/fzboost-estimate.yaml
production_expected=$(wc -l < "$production_manifest")
test -n "$production_jobid"

performance/slurm/slurm-profile \
  --job-id "$production_jobid" \
  --expected-jobs "$production_expected" \
  --concurrency-target 82 \
  --cluster-context-nodes 'apl[01-28]' \
  --label "fzboost-stage2-production-$production_jobid" \
  --output-dir "$stage2/benchmark/production-$production_jobid" \
  --task-metadata-file "$production_metadata" \
  --context algorithm=fzboost \
  --context stage=2 \
  --context scope=production \
  --context-file "$production_manifest" \
  --context-file "$production_metadata" \
  --context-file "$estimate_config" \
  --storage-path "$PZ_DP2_ROOT" \
  --capture-slurm-snapshot \
  --fail-on-unsuccessful

cat "$stage2/benchmark/production-$production_jobid/summary.log"
```

If retries are needed, retain every array ID. The generic
[Slurm profiling guide](../../slurm_profile.md) explains how to combine all
attempts with `--job-id-file` instead of profiling only the last array.

The defaults are 82 concurrent tasks, 38 GiB, and 30 minutes per task. The v3
production peak was 31.50 GiB and its longest task took 18 min 08 s. The 38-GiB
request also covers the 33.85-GiB historical maximum with 4.15 GiB of
headroom. Unlike 40 GiB, 38 GiB permits three tasks to fit in the 119,984 MiB
schedulable memory of an older node, although cluster load and fragmentation
still control the concurrency actually achieved. Keep the throttle at 82: the
production peak of 37 reflected shared-cluster availability rather than an
array limit. The evidence and calculation are recorded in
[`fzboost_runs.md`](../references/fzboost_runs.md). Override these defaults with
`PZ_FZBOOST_MAX_CONCURRENT`, `PZ_FZBOOST_MEMORY`, and `PZ_FZBOOST_TIME` when a
different partition or a new pilot requires it. A future optimization may
group shards into measured memory classes, but their boundaries must be based
on retained input-size and `MaxRSS` data.

## 4. Output layout

```text
$PZ_DP2_ROOT/fzboost/stage2/
├── output/Norder=*/Dir=*/Npix=*.hdf5
├── log/slurm-*.out
├── log/slurm-*.err
├── smoke/
│   ├── smoke-test.hdf5
│   └── READY
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Complete HDF5 files are validated and skipped on resubmission. Incomplete files
are preserved with a suffix before they are retried.

The scientific photometry, feature, and PDF contracts are documented in
[`fzboost_science.md`](../references/fzboost_science.md). The prior production
evidence and resource rationale are kept separately in
[`fzboost_runs.md`](../references/fzboost_runs.md).

Continue with
[`fzboost_stage3_build_hats.md`](fzboost_stage3_build_hats.md).
