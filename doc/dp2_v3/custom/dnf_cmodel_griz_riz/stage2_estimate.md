# Stage 2: estimate the complete DP2 Object catalog

Stage 2 estimates the official DP2 Object manifest independently with the
`griz` and `riz` models. Each estimator HDF5 retains the internal 601-bin PDFs
needed to derive the requested Rubin-style scalars in Stage 3. The promoted
ancillary schema contains exactly `DNF_ZN`; the other DNF diagnostics remain
internal to the estimator HDF5.

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
selected SFD bands, normalized PDFs, and exact promotion of `DNF_ZN`. A
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

After both arrays leave `squeue`, require all five tasks in each array to have
state `COMPLETED` and exit code `0:0`. Then validate and seal the pilot:

```bash
pilot=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/validate-stage2.py \
  manifest all --manifest "$pilot" --ready-scope pilot
```

This reads the selected source photometry and object IDs from every pilot
parquet, verifies that the SFD inputs can be materialized, and checks the
promoted `DNF_ZN`. It also samples PDFs across every output and
refuses missing, invalid, duplicate-manifest, or unexpected HDF5 files. Only
after both variants pass are checksum-based `pilot/READY` markers written.

## 4. Profile and accept the pilot resources

```bash
for variant in griz riz; do
  stage2=$PZ_DP2_CUSTOM_ROOT/$variant/stage2
  jobid=$(awk -F '\t' '$2 == variant && $3 == "pilot" {id=$4} END {print id}' \
    variant="$variant" "$stage2/submitted-job-ids.tsv")
  expected=$(wc -l < "$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt")

  performance/slurm/slurm-profile \
    --job-id "$jobid" \
    --expected-jobs "$expected" \
    --concurrency-target 5 \
    --cluster-context-nodes 'apl[01-28]' \
    --label "dnf-cmodel-$variant-stage2-pilot-$jobid" \
    --output-dir "$stage2/benchmark/pilot-$jobid" \
    --capture-slurm-snapshot \
    --fail-on-unsuccessful

  cat "$stage2/benchmark/pilot-$jobid/summary.log"
done
```

Choose production memory, time, and concurrency from the observed maximum RSS,
longest task, node topology, and desired safety margins. Record that rationale
with the run notes; do not infer that `griz` and `riz` necessarily have equal
costs.

## 5. Submit the complete catalog

Production deliberately has no implicit resource defaults. Export the values
accepted from the pilot, then submit one or both variants. If the measured
profiles differ, submit each variant separately with its own values.

```bash
export PZ_CUSTOM_DNF_MAX_CONCURRENT=<accepted-concurrency>
export PZ_CUSTOM_DNF_MEMORY=<accepted-memory>
export PZ_CUSTOM_DNF_TIME=<accepted-walltime>

doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/submit-estimates.sh all production
```

The production launcher requires valid smoke and pilot checksum contracts.
Complete pilot shards are validated and skipped when encountered by the full
array. Invalid pre-existing outputs are moved aside with an `.incomplete-*`
suffix before recomputation.

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

Profile each production array with its accepted concurrency and the full
manifest count, following the same `slurm-profile` pattern used for the pilot.
If retries are required, retain all job IDs and use a job-ID file when
profiling the combined attempts.

Continue with [`stage3_build_hats.md`](stage3_build_hats.md) only after both
`production/READY` markers exist and their checksums still validate.
