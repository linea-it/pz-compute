# DP2 batch Stage 3: build HATS products for all algorithms

This stage submits one persistent Slurm driver for every algorithm in the
registry. Each driver reads only its own Stage 2 HDF5 tree and writes its HATS
products, driver logs, Dask worker logs, benchmarks, and environment freeze
under the same algorithm's `stage3/` directory.

Complete the shared [Apollo setup](../dp2_setup_apollo.md) and
[batch Stage 2](estimate_all.md) first.

## 1. Load the shared environment and verify all inputs

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

inputs=$(find "$PZ_DP2_INPUT_DATASET" -type f -name '*.parquet' | wc -l)
for algorithm in fzboost bpz; do
    outputs=$(find "$PZ_DP2_ROOT/$algorithm/stage2/output" \
      -name '*.hdf5' | wc -l)
    printf '%s: inputs=%s outputs=%s\n' "$algorithm" "$inputs" "$outputs"
    test "$inputs" -eq "$outputs"
done
```

Do not continue unless both algorithms have one complete HDF5 output per input
parquet. Stage 2 smoke outputs live outside the production output trees and
are therefore not included in these counts.

## 2. Submit all HATS builds

```bash
doc/dp2_v3/scripts/submit-hats.sh all
```

`all` submits one independent Slurm driver for FlexZBoost and one for BPZ.
Each driver starts its own Dask cluster through `dask-jobqueue`; Slurm may run
or queue the two builds according to cluster capacity. The login shell can be
closed as soon as both driver job IDs have been returned.

The default request is 82 Dask worker jobs per algorithm, with 8 CPUs and
40 GiB per worker. Override the worker count for both builds before submission
when required:

```bash
export PZ_HATS_WORKERS=40
doc/dp2_v3/scripts/submit-hats.sh all
```

The command writes one job ledger per algorithm:

```text
$PZ_DP2_ROOT/fzboost/stage3/submitted-job-ids.tsv
$PZ_DP2_ROOT/bpz/stage3/submitted-job-ids.tsv
```

All artifacts remain isolated:

```text
$PZ_DP2_ROOT/<algorithm>/stage3/
├── output/
│   ├── pz-<algorithm>-gaap1p0-clipped-hats/
│   └── pz-<algorithm>-gaap1p0-clipped-hats.pdf/
├── log/
│   ├── dask-<run-tag>/
│   └── driver-<run-tag>/
├── benchmark/<run-tag>/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

The Stage 2 HDF5 files are retained. The summary product contains scalar photo-z
statistics and `i_gaap1p0Mag_sfd`; the separate PDF product stores 601-element
`float32` vectors plus its redshift grid.

## 3. Monitor all submitted drivers

```bash
for algorithm in fzboost bpz; do
    printf '\n%s\n' "$algorithm"
    cat "$PZ_DP2_ROOT/$algorithm/stage3/submitted-job-ids.tsv"
done
```

Pass every recorded production job ID to `sacct` and require `COMPLETED` with
exit code `0:0`. Driver and worker diagnostics remain inside their respective
algorithm directories.

## 4. Validate all HATS artifacts

After both drivers complete, validate both output trees with one command:

```bash
doc/dp2_v3/scripts/validate-hats.py all
```

The validator checks every registered algorithm. It requires the expected
summary and PDF schemas, a 601-point PDF grid, equal Stage 2/summary/PDF row
counts, and removal of temporary parquet staging after successful completion.

Scientific output contracts are documented in
[`fzboost_science.md`](../references/fzboost_science.md) and
[`bpz_science.md`](../references/bpz_science.md). Validated FlexZBoost resource
history is kept separately in
[`fzboost_runs.md`](../references/fzboost_runs.md); no BPZ production history
is claimed yet.
