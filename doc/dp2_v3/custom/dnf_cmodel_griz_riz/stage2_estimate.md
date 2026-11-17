# Stage 2: estimate the complete DP2 Object catalog

Stage 2 estimates the official DP2 Object manifest independently with the
`griz` and `riz` models. Each estimator HDF5 retains the internal 601-bin PDFs
needed to derive the requested Rubin-style scalars in Stage 3. The promoted
ancillary schema contains exactly `DNF_ZN`; the other DNF diagnostics remain
internal to the estimator HDF5. This workflow explicitly enables stable
log-space evaluation of the same fitted DNF Gaussian. Every PDF is checked
while its estimator chunk is still in memory, and objective quality counters
are stored under `pz_compute/dnf_pdf_quality` without a full-file validation
reread.

This project reuses the algorithm-neutral manifests described in
[`../../common/prepare_estimation_manifests.md`](../../common/prepare_estimation_manifests.md),
but all estimates, logs, markers, and benchmarks remain below
`$PZ_DP2_CUSTOM_ROOT/<variant>/stage2`. The official six-band launcher is not
modified or invoked.

## 1. Load the environment and identify the Object catalog

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"
```

Both variants use `selection_mode=1` (ANF), the reviewed DP2 SFD coefficients,
the original magnitude limits for their selected bands, and the corresponding
Stage 1 model. Input cModel magnitudes and errors are generated from fluxes
when the Object parquet does not already contain them.

## 2. Run the mandatory smoke test

```bash
PZ_SMOKE_ROWS=10000 \
  doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/smoke-estimates.sh all
```

The smoke path projects the first 10,000 rows, validates both Stage 1 models,
runs both estimates, and verifies the source photometry, row fingerprint,
selected SFD bands, reviewed PDF method, complete quality counters, sampled
normalized PDFs, and exact promotion of `DNF_ZN`. A
successful run writes a checksum contract to each variant's
`stage2/smoke/READY`. Smoke outputs and markers are never overwritten
silently.

## 3. Submit the mandatory five-shard pilot

The launcher refreshes the shared sorted manifests and selects the five
largest parquet shards for the pilot:

```bash
doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/submit-estimates.sh all pilot
```

The initial conservative shape is five concurrent single-CPU tasks, 40 GiB,
and two hours per task. These are starting limits inherited from the official
DNF measurements, not accepted custom-production measurements. Optional pilot
overrides are `PZ_CUSTOM_PILOT_MAX_CONCURRENT`, `PZ_CUSTOM_PILOT_MEMORY`, and
`PZ_CUSTOM_PILOT_TIME`.

The submission ledger has four tab-separated fields: timestamp, variant,
scope, and array job ID. Monitor each latest pilot with:

```bash
for variant in griz riz; do
  ledger=$PZ_DP2_CUSTOM_ROOT/$variant/stage2/submitted-job-ids.tsv
  jobid=$(awk -F '\t' '$3 == "pilot" {id=$4} END {print id}' "$ledger")
  test -n "$jobid"
  squeue --jobs="$jobid"
done
```

To retain pending reasons, transient step memory/I/O, and filesystem headroom,
start both generic watchers in parallel and wait for both pilot arrays:

```bash
watch_pids=()

for variant in griz riz; do
  stage2=$PZ_DP2_CUSTOM_ROOT/$variant/stage2
  ledger=$stage2/submitted-job-ids.tsv
  jobid=$(awk -F '\t' \
    '$2 == variant && $3 == "pilot" {id=$4} END {print id}' \
    variant="$variant" "$ledger")
  test -n "$jobid"

  performance/slurm/slurm-watch \
    --job-id "$jobid" \
    --interval-seconds 60 \
    --storage-path "$PZ_DP2_CUSTOM_ROOT" \
    --context algorithm=dnf \
    --context "custom_variant=$variant" \
    --context stage=2 \
    --context scope=pilot \
    --output-dir "$stage2/benchmark/live-pilot-$jobid" &

  watch_pids+=("$!")
done

wait "${watch_pids[@]}"
```

After both watchers return, require all five tasks in each array to have state
`COMPLETED` and exit code `0:0`. Then validate and seal the pilot:

```bash
pilot=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/validate-stage2.py \
  manifest all --manifest "$pilot" --ready-scope pilot
```

This reads the selected source photometry and object IDs from every pilot
parquet, verifies that the SFD inputs can be materialized, and checks the
promoted `DNF_ZN`. It requires exact in-memory PDF counters covering every row
and zero numerical failures, then samples PDFs across every output as a cheap
written-artifact check. It
refuses missing, invalid, duplicate-manifest, or unexpected HDF5 files. Only
after both variants pass are checksum-based `pilot/READY` markers written.

## 4. Profile and accept the pilot resources

```bash
for variant in griz riz; do
  stage2=$PZ_DP2_CUSTOM_ROOT/$variant/stage2
  jobid=$(awk -F '\t' '$2 == variant && $3 == "pilot" {id=$4} END {print id}' \
    variant="$variant" "$stage2/submitted-job-ids.tsv")
  manifest=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
  metadata=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.metadata.tsv
  config=doc/dp2_v3/custom/dnf_cmodel_griz_riz/config/dnf-$variant-estimate.yaml
  expected=$(wc -l < "$manifest")

  performance/slurm/slurm-profile \
    --job-id "$jobid" \
    --expected-jobs "$expected" \
    --concurrency-target 5 \
    --cluster-context-nodes 'apl[01-28]' \
    --label "dnf-cmodel-$variant-stage2-pilot-$jobid" \
    --output-dir "$stage2/benchmark/pilot-$jobid" \
    --task-metadata-file "$metadata" \
    --context algorithm=dnf \
    --context "custom_variant=$variant" \
    --context stage=2 \
    --context scope=pilot \
    --context-file "$manifest" \
    --context-file "$metadata" \
    --context-file "$config" \
    --storage-path "$PZ_DP2_CUSTOM_ROOT" \
    --capture-slurm-snapshot \
    --fail-on-unsuccessful

  cat "$stage2/benchmark/pilot-$jobid/summary.log"
done
```

Choose production memory, time, and concurrency from the observed maximum RSS,
longest task, node topology, and desired safety margins. Record that rationale
with the run notes. The accepted measurements and resource calculation for
jobs `225091` and `225092` are recorded in
[`resource_measurements.md`](resource_measurements.md).

## 5. Submit the complete catalog

The accepted defaults for both variants are one CPU, 36 GiB, one hour, and at
most 102 concurrent tasks. Submit one or both variants directly:

```bash
doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/submit-estimates.sh all production
```

Generic overrides are `PZ_CUSTOM_DNF_MAX_CONCURRENT`,
`PZ_CUSTOM_DNF_MEMORY`, and `PZ_CUSTOM_DNF_TIME`. Variant-specific
`PZ_CUSTOM_GRIZ_*` or `PZ_CUSTOM_RIZ_*` values take precedence when later
measurements justify different resources.

The production launcher requires valid smoke and pilot checksum contracts.
Complete pilot shards are validated and skipped when encountered by the full
array. Invalid pre-existing outputs are moved aside with an `.incomplete-*`
suffix before recomputation.

Immediately after submission, start one live monitor per variant. The commands
run both monitors in parallel and keep this terminal occupied until both
production arrays reach a terminal accounting state:

```bash
watch_pids=()

for variant in griz riz; do
  stage2=$PZ_DP2_CUSTOM_ROOT/$variant/stage2
  ledger=$stage2/submitted-job-ids.tsv
  jobid=$(awk -F '\t' \
    '$2 == variant && $3 == "production" {id=$4} END {print id}' \
    variant="$variant" "$ledger")
  test -n "$jobid"

  performance/slurm/slurm-watch \
    --job-id "$jobid" \
    --interval-seconds 60 \
    --storage-path "$PZ_DP2_CUSTOM_ROOT" \
    --context algorithm=dnf \
    --context "custom_variant=$variant" \
    --context stage=2 \
    --context scope=production \
    --output-dir "$stage2/benchmark/live-production-$jobid" &

  watch_pids+=("$!")
done

wait "${watch_pids[@]}"
```

Keep the terminal or persistent session open while the monitors run. This
live record is optional for the scientific outputs, but it is required to
retain transient pending reasons, step resource/I/O measurements, and
filesystem headroom that cannot be reconstructed from final accounting.

From another terminal, summarize every array task already visible in Slurm
accounting. The command discovers the latest production IDs for both variants
and exits nonzero after printing any terminal task that did not complete
successfully:

```bash
jobids=$(
  for variant in griz riz; do
    ledger=$PZ_DP2_CUSTOM_ROOT/$variant/stage2/submitted-job-ids.tsv
    awk -F '\t' \
      '$2 == variant && $3 == "production" {id=$4} END {print id}' \
      variant="$variant" "$ledger"
  done | paste -sd, -
)
test -n "$jobids"

sacct --jobs="$jobids" --parsable2 --noheader \
  --format=JobIDRaw,State,ExitCode,Elapsed,MaxRSS |
awk -F '|' '
  $1 ~ /^[0-9]+_[0-9]+$/ {
    split($1, parts, "_")
    job = parts[1]
    state = $2
    sub(/ .*/, "", state)
    sub(/\+.*/, "", state)

    total[job]++
    states[job, state]++

    if (state !~ /^(COMPLETED|RUNNING|PENDING|CONFIGURING|COMPLETING)$/) {
      bad++
      print "terminal non-success task:", $0 > "/dev/stderr"
    }
  }

  END {
    for (job in total) {
      print "\n=== Job array:", job, "==="
      print "array tasks seen by sacct:", total[job]

      for (key in states) {
        split(key, parts, SUBSEP)
        if (parts[1] == job)
          print parts[2], states[key]
      }
    }

    if (bad) exit 1
  }
'
```

An array that is still entirely pending may not yet have task records in
`sacct`; use `squeue --jobs="$jobids"` alongside this summary. Do not run the
production validator while any task is failed or still active.

## 6. Validate and seal production

Once every array task has completed successfully:

```bash
doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/validate-stage2.py \
  manifest all --ready-scope production
```

The resulting layout is:

```text
$PZ_DP2_CUSTOM_ROOT/<variant>/stage2/
├── output/Norder=*/Dir=*/Npix=*.hdf5
├── smoke/
│   ├── smoke-test.hdf5
│   └── READY
├── pilot/READY
├── production/READY
├── log/slurm-*.{out,err}
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Profile each production array with its accepted concurrency, full manifest,
and per-shard metadata:

```bash
for variant in griz riz; do
  stage2=$PZ_DP2_CUSTOM_ROOT/$variant/stage2
  jobid=$(awk -F '\t' '$2 == variant && $3 == "production" {id=$4} END {print id}' \
    variant="$variant" "$stage2/submitted-job-ids.tsv")
  manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
  metadata=$PZ_DP2_ROOT/common/manifests/input-parquet-files.metadata.tsv
  config=doc/dp2_v3/custom/dnf_cmodel_griz_riz/config/dnf-$variant-estimate.yaml
  expected=$(wc -l < "$manifest")

  performance/slurm/slurm-profile \
    --job-id "$jobid" \
    --expected-jobs "$expected" \
    --concurrency-target 102 \
    --cluster-context-nodes 'apl[01-28]' \
    --label "dnf-cmodel-$variant-stage2-production-$jobid" \
    --output-dir "$stage2/benchmark/production-$jobid" \
    --task-metadata-file "$metadata" \
    --context algorithm=dnf \
    --context "custom_variant=$variant" \
    --context stage=2 \
    --context scope=production \
    --context-file "$manifest" \
    --context-file "$metadata" \
    --context-file "$config" \
    --storage-path "$PZ_DP2_CUSTOM_ROOT" \
    --capture-slurm-snapshot \
    --fail-on-unsuccessful

  cat "$stage2/benchmark/production-$jobid/summary.log"
done
```

Use the resolved concurrency instead of `102` when an override was active.
If retries are required, retain all job IDs and use a job-ID file when
profiling the combined attempts.

Continue with [`stage3_build_hats.md`](stage3_build_hats.md) only after both
`production/READY` markers exist and their checksums still validate.
