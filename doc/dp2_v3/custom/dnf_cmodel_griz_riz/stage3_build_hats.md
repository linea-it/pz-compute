# Stage 3: build scalar-only HATS products

Stage 3 builds one independent HATS collection per variant. Internal Stage 2
PDFs are read to derive the reviewed Rubin-style scalar summaries, but no PDF
column or companion PDF product is published. This is an explicit custom
`--pdf-layout=none` path and does not change the official nested-PDF workflow.

## 1. Final schema and numeric policy

Each collection contains exactly 11 top-level columns in this order:

```text
objectId
coord_ra
coord_dec
dnf_z_mean
dnf_z_median
dnf_z_mode
dnf_z_err68_low
dnf_z_err68_high
dnf_z_err95_low
dnf_z_err95_high
DNF_ZN
```

The eight scientific columns are retained as `float64`. Scalar-only storage is
small enough that reducing their precision is unnecessary. `objectId` and the
coordinate types follow the DP2 Object input. The 68% interval is the
16th/84th percentile pair and the 95% interval is the 2.5th/97.5th pair.

## 2. Submit both HATS builds

Load the dedicated Stage 3 environment and the same runtime roots used by the
previous stages:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/submit-hats.sh all
```

The launcher verifies both Stage 2 `production/READY` checksum contracts and
all destinations before submitting either driver. It refuses to overwrite a
HATS catalog, staging directory, PDF-named product, validation record, or
completion marker.

The conservative initial worker shape matches the proven official HATS
allocation: one initial worker, adaptive scaling to 80, two CPUs, 40 GiB, and
12 hours per worker. Scalar-only construction is expected to be lighter, so
profile the first run before changing these defaults. Available overrides are:

```text
PZ_HATS_MIN_WORKERS
PZ_HATS_MAX_WORKERS
PZ_HATS_SCALE_DOWN_DELAY
PZ_HATS_WORKER_CORES
PZ_HATS_WORKER_MEMORY
PZ_HATS_WORKER_TIME
PZ_HATS_MARGIN_ARCSEC
```

The resulting destinations are:

```text
$PZ_DP2_CUSTOM_ROOT/griz/stage3/output/pz-dnf-cmodel-griz-scalar-hats/
$PZ_DP2_CUSTOM_ROOT/riz/stage3/output/pz-dnf-cmodel-riz-scalar-hats/
```

## 3. Monitor and validate

The ledger fields are timestamp, variant, driver job ID, and unique run tag:

```bash
driver_logs=()

for variant in griz riz; do
  stage3=$PZ_DP2_CUSTOM_ROOT/$variant/stage3
  IFS=$'\t' read -r submitted recorded_variant jobid run_tag < \
    <(tail -n 1 "$stage3/submitted-job-ids.tsv")
  test "$recorded_variant" = "$variant"
  squeue --jobs="$jobid"
  driver_logs+=("$stage3/log/driver-$run_tag/driver.log")
done

tail -F "${driver_logs[@]}"
```

Start both general watchers in parallel from a separate terminal. Selecting
each driver by ID and its adaptive workers by their run-specific Slurm name
captures both populations even though worker IDs do not exist at submission
time:

```bash
watch_pids=()

for variant in griz riz; do
  stage3=$PZ_DP2_CUSTOM_ROOT/$variant/stage3
  IFS=$'\t' read -r submitted recorded_variant jobid run_tag < \
    <(tail -n 1 "$stage3/submitted-job-ids.tsv")
  test "$recorded_variant" = "$variant"
  worker_job_name=pz3c-${variant}-${run_tag}

  performance/slurm/slurm-watch \
    --job-id "$jobid" \
    --job-name "$worker_job_name" \
    --interval-seconds 60 \
    --storage-path "$PZ_DP2_CUSTOM_ROOT" \
    --context algorithm=dnf \
    --context "custom_variant=$variant" \
    --context stage=3 \
    --output-dir "$stage3/benchmark/$run_tag/live" &

  watch_pids+=("$!")
done

wait "${watch_pids[@]}"
```

The driver runs final validation automatically and returns nonzero if it
fails. After completion, require its explicit exit marker and optionally rerun
the validator:

```bash
for variant in griz riz; do
  stage3=$PZ_DP2_CUSTOM_ROOT/$variant/stage3
  run_tag=$(tail -n 1 "$stage3/submitted-job-ids.tsv" | cut -f4)
  test "$(cat "$stage3/log/driver-$run_tag/driver-exit-code.txt")" -eq 0
done

doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/validate-hats.py all
```

The validator:

- requires the exact ordered 11-column schema and no nested columns;
- requires `float64` for all eight scientific values;
- scans every HATS row for finite values and valid coordinates;
- requires `0 <= z <= 6` for all seven PDF-derived summaries;
- requires `z95_low <= z68_low <= median <= z68_high <= z95_high`;
- independently recomputes a bounded cross-check of all seven summaries from
  the Stage 2 PDFs and matches them by `objectId`;
- compares row counts and full `DNF_ZN` aggregates with Stage 2;
- revalidates the Stage 2 production checksum contract;
- rejects leftover staging and any PDF-named sibling product;
- verifies the configured default margin catalog.

Successful driver validation writes:

```text
$PZ_DP2_CUSTOM_ROOT/<variant>/stage3/production/
├── VALIDATION.json
└── READY
```

`VALIDATION.json` is the machine-readable publication record. `READY` seals
that record together with the Stage 2 contract and exact builder, runner, and
validator implementations.

## 4. Profile driver and workers

For each variant, profile the authoritative driver and recover every adaptive
Dask worker ID using the shared helper:

```bash
for variant in griz riz; do
  stage3=$PZ_DP2_CUSTOM_ROOT/$variant/stage3
  IFS=$'\t' read -r submitted recorded_variant jobid run_tag < \
    <(tail -n 1 "$stage3/submitted-job-ids.tsv")
  test "$recorded_variant" = "$variant"
  benchmark=$stage3/benchmark/$run_tag
  worker_logs=$stage3/log/dask-$run_tag
  run_context=$benchmark/run-context.log
  worker_name=$benchmark/worker-job-name.txt

  performance/slurm/slurm-profile \
    --job-id "$jobid" \
    --expected-jobs 1 \
    --concurrency-target 1 \
    --label "dnf-cmodel-$variant-stage3-driver-$jobid" \
    --output-dir "$benchmark/driver" \
    --context algorithm=dnf \
    --context "custom_variant=$variant" \
    --context stage=3 \
    --context role=driver \
    --context-file "$run_context" \
    --context-file "$worker_name" \
    --storage-path "$PZ_DP2_CUSTOM_ROOT" \
    --capture-slurm-snapshot \
    --fail-on-unsuccessful

  doc/dp2_v3/scripts/collect-hats-worker-job-ids.sh \
    "$benchmark" "$worker_logs"
  worker_count=$(wc -l < "$benchmark/worker-job-ids.txt")

  performance/slurm/slurm-profile \
    --job-id-file "$benchmark/worker-job-ids.txt" \
    --expected-jobs "$worker_count" \
    --concurrency-target="${PZ_HATS_MAX_WORKERS:-80}" \
    --cluster-context-nodes 'apl[01-28]' \
    --label "dnf-cmodel-$variant-stage3-workers-$run_tag" \
    --output-dir "$benchmark/workers" \
    --context algorithm=dnf \
    --context "custom_variant=$variant" \
    --context stage=3 \
    --context role=worker \
    --context-file "$run_context" \
    --context-file "$worker_name" \
    --storage-path "$PZ_DP2_CUSTOM_ROOT" \
    --capture-slurm-snapshot
done
```

Adaptive workers may be cancelled during scale-down, so do not use
`--fail-on-unsuccessful` for the worker union. Success is determined by the
driver exit code, clean validation, `VALIDATION.json`, and `READY`.
The profiler also retains compressed accounting/task tables and a
`benchmark-context.json`; keep those artifacts with the publication record.

## 5. Publication provenance

Publish only after both variants validate. For each PZ Server or LIneA LSDB
entry, retain together:

- the HATS destination and variant;
- project `dp2_v3p1_custom` and flavor `dnf_cmodel_<variant>`;
- DNF/ANF `selection_mode=1`, cModel photometry, and ordered bands;
- the Stage 1 model name and provenance;
- row count, exact columns, `float64` policy, and `pdf_layout=none` from
  `VALIDATION.json`;
- Stage 1, Stage 2, and Stage 3 job ledgers and benchmark summaries;
- environment freezes, Stage 3 `run-context.log`, repository commit, and all
  three stages' checksum contracts.

Suggested product labels are `DP2 custom DNF cModel griz scalar photo-z` and
`DP2 custom DNF cModel riz scalar photo-z`. State explicitly in the product
description that PDFs were used internally but are not part of the published
collection.
