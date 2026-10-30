# DP2 BPZ Stage 2: estimate all catalogs

This procedure runs only BPZ over the DP2 Object catalog parquet shards. It
uses the batch runner but submits a single Slurm array and writes exclusively
under `$PZ_DP2_ROOT/bpz/stage2/`.

## 1. Load the environment and locate the model

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

test -f "$PZ_DP2_ROOT/bpz/stage1/model/model_dp2_v3p1_bpz_dp2_6band_gold.pickle"
```

## 2. BPZ photometry contract

The launcher applies the reviewed [`bpz-estimate.yaml`](../config/bpz-estimate.yaml)
to the dereddened six-band GAaP magnitudes and errors. The complete scientific
rationale for the photometry, templates, prior, uncertainties, non-detections,
and redshift grid is maintained in
[`bpz_science.md`](../references/bpz_science.md). `objectId` records row
identity and order in the HDF5 output.

BPZ also requires the official 136-template reference-data tree. Follow
[`bpz_reference_data.md`](../references/bpz_reference_data.md) and place it at
`$PZ_INSTALL_ROOT/bpz_dp2_v3p1_data`, or export
`PZ_BPZ_OFFICIAL_DATA_ROOT` to its absolute location. The `bpz` command always
selects this official contract; no test-selection variable exists.

## 3. Mandatory smoke test

```bash
doc/dp2_v3/scripts/smoke-estimates.sh bpz
```

The command first creates a 10,000-row projected Parquet sample under
`$PZ_DP2_ROOT/common/smoke/`; set `PZ_SMOKE_ROWS` to another positive row count
when needed. In addition to validating the model, columns, and output, it
creates any missing SED/filter AB files. Do not submit the full array before
this warm-up: concurrent cache creation can cause races and unnecessary I/O.
It also validates the official list length, all 136 SED files, the six filters,
and AB-cache writability before invoking BPZ.

The smoke test writes:

```text
$PZ_DP2_ROOT/bpz/stage2/smoke/smoke-test.hdf5
$PZ_DP2_ROOT/bpz/stage2/smoke/READY
```

The `READY` marker contains model, estimator YAML, and DP2 v3 LSSTCam SFD
configuration checksums. If any changes, the launcher requires a new smoke
test. For BPZ it also contains checksums for the SED list, every referenced
SED, and the filters.

## 4. Run and profile the mandatory pilot

Create the full and five-largest-shard manifests using the
[shared manifest procedure](../common/prepare_estimation_manifests.md). For the
pilot, run the same launcher with BPZ selected:

```bash
PZ_INPUT_MANIFEST=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt \
PZ_BPZ_MAX_CONCURRENT=5 \
  doc/dp2_v3/scripts/submit-estimates.sh bpz
```

Save the pilot ID before making another submission. Use the
[Stage 2 terminal commands](inspect_runs.md#stage-2-estimation-array) with
`algorithm=bpz` to monitor it. Once all five tasks have completed, create the
pilot benchmark:

```bash
stage2=$PZ_DP2_ROOT/bpz/stage2
pilot_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
pilot_manifest=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
pilot_expected=$(wc -l < "$pilot_manifest")
test -n "$pilot_jobid"

performance/slurm/slurm-profile \
  --job-id "$pilot_jobid" \
  --expected-jobs "$pilot_expected" \
  --concurrency-target 5 \
  --cluster-context-nodes 'apl[01-26]' \
  --label "bpz-stage2-pilot-$pilot_jobid" \
  --output-dir "$stage2/benchmark/pilot-$pilot_jobid" \
  --fail-on-unsuccessful

cat "$stage2/benchmark/pilot-$pilot_jobid/summary.log"
```

Inspect `MaxRSS` and `Elapsed` before accepting or changing the conservative
production defaults. BPZ test measurements are not a substitute for this
official 136-template pilot.

## 5. Submit and profile the complete catalog

After accepting the pilot, submit all catalogs and retain the new array ID:

```bash
doc/dp2_v3/scripts/submit-estimates.sh bpz

stage2=$PZ_DP2_ROOT/bpz/stage2
production_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
test -n "$production_jobid"
```

Use the [Stage 2 terminal commands](inspect_runs.md#stage-2-estimation-array)
with `algorithm=bpz` to watch task states and output counts, summarize
completed and failed tasks, inspect logs, and validate every HDF5 afterward.

After the array leaves `squeue`, all tasks are successful, and Stage 2
validation passes, generate its production benchmark:

```bash
stage2=$PZ_DP2_ROOT/bpz/stage2
production_jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
production_manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
production_expected=$(wc -l < "$production_manifest")
test -n "$production_jobid"

performance/slurm/slurm-profile \
  --job-id "$production_jobid" \
  --expected-jobs "$production_expected" \
  --concurrency-target 20 \
  --cluster-context-nodes 'apl[01-26]' \
  --label "bpz-stage2-production-$production_jobid" \
  --output-dir "$stage2/benchmark/production-$production_jobid" \
  --fail-on-unsuccessful

cat "$stage2/benchmark/production-$production_jobid/summary.log"
```

If retries are needed, retain every array ID. The generic
[Slurm profiling guide](../../slurm_profile.md) explains how to combine all
attempts with `--job-id-file` instead of profiling only the last array.

The job remains in Slurm after logout. The initial defaults are 20 concurrent
tasks, 40 GiB, and 24 hours per task. They are conservative; tune
`PZ_BPZ_MAX_CONCURRENT`, `PZ_BPZ_MEMORY`, and `PZ_BPZ_TIME` from pilot evidence.

## 6. Outputs

```text
$PZ_DP2_ROOT/bpz/stage2/
├── output/Norder=*/Dir=*/Npix=*.hdf5
├── log/
│   ├── slurm-*.out
│   └── slurm-*.err
├── smoke/
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Rerunning the launcher is the recovery path: complete HDF5 files are validated
and skipped, while incomplete files are preserved with a suffix before retry.

Continue with [`bpz_stage3_build_hats.md`](bpz_stage3_build_hats.md).
