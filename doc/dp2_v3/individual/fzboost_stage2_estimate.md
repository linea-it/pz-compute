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
complete shard into the smoke output.

## 2. Pilot and submit production

Create the full and five-largest-shard manifests using the
[shared manifest procedure](../common/prepare_estimation_manifests.md), then run:

```bash
PZ_INPUT_MANIFEST=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt \
PZ_FZBOOST_MAX_CONCURRENT=5 \
  doc/dp2_v3/scripts/submit-estimates.sh fzboost
```

After checking `MaxRSS` and `Elapsed`, submit the complete catalog:

```bash
doc/dp2_v3/scripts/submit-estimates.sh fzboost
```

## 3. Output layout

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
