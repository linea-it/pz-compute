# Project-specific scripts

This directory contains only orchestration and validation specific to the
DP2 DNF cModel `griz`/`riz` delivery. It must not contain private copies of
generic repository functionality.

Generic capabilities such as configurable band lists, selected-band SFD
materialization, DNF ancillary extraction, PDF quantiles, and scalar-only HATS
construction belong in the shared `rail_scripts/` implementation with
backward-compatible defaults and tests. The scripts here opt into
those capabilities explicitly and isolate paths, names, provenance, and Slurm
submissions for the two custom variants.

## Available

- `prepare-training-catalog.py`: verifies the trusted clipped RTN-124 checksum,
  row contract, cModel magnitude errors, and legacy SFD correction before
  writing independent row-preserving `griz` and `riz` HDF5 tables. It refuses
  to overwrite existing outputs.
- `variant-config.sh`: resolves the bands, configuration, training table,
  artifact root, and canonical model name for one variant.
- `submit-training.sh`: submits `griz`, `riz`, or both Stage 1 jobs into the
  dedicated custom run root and records their job IDs and frozen environment.
- `run-one-train.sbatch`: executes one DNF training job with a single CPU and
  explicit cModel columns, then invokes the provenance wrapper.
- `wrap-model.py`: writes the final RAIL `Model` atomically with the custom
  project, flavor, selection, catalog tag, and creation class.
- `validate-models.py`: compares the fitted arrays with the exact prepared
  inputs and verifies the wrapper, feature count, normalization, redshift
  contract, and fitted nearest-neighbor state.
- `smoke-estimates.sh`: creates a projected Object sample and requires both
  variants to pass model, photometry, PDF, row-order, and `DNF_ZN` checks.
- `submit-estimates.sh`: submits the mandatory five-shard pilot or the full
  Stage 2 arrays, requiring smoke checksums and an accepted pilot before
  production.
- `run-one-estimate.sbatch`: estimates one manifest shard with explicit cModel
  columns, selected bands, stable in-memory-validated PDFs, persisted quality
  counters, and promoted `DNF_ZN`; complete outputs are validated and skipped
  on retry.
- `validate-stage2.py`: validates individual pairs or full manifests against
  their source parquet files and can seal successful pilot or production runs
  with checksum-based `READY` markers.
- `submit-hats.sh`: submits independent scalar-only Stage 3 drivers after
  verifying the Stage 2 production checksum contracts and destination safety.
- `run-one-hats.sbatch`: builds one HATS collection with no nested or companion
  PDF product, records driver/worker context, and invokes final validation.
- `validate-hats.py`: enforces the exact 11-column schema and `float64` science
  policy, scans every scalar row, compares `DNF_ZN` aggregates with Stage 2,
  rejects PDF artifacts, and writes publication validation records.
