# Stage 1: train the cModel `griz` and `riz` models

Stage 1 projects the reviewed cModel columns from the clipped RTN-124
parquet without changing its rows, write separate `griz` and `riz` HDF5
training tables, train one DNF model per variant, and validate their feature
counts and provenance.

Implementation must preserve the official procedure documented in
[`../../individual/dnf_stage1_train.md`](../../individual/dnf_stage1_train.md).
Custom artifacts belong below `$PZ_DP2_CUSTOM_ROOT`, never below the official
`$PZ_DP2_ROOT/dnf/stage1` tree.

## Prepare the two training projections

Complete the official [Apollo setup](../../dp2_setup_apollo.md) and the source
download/checksum step in the
[shared training procedure](../../common/prepare_training_catalog.md). Then
create the custom projections:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
cd "$PZ_COMPUTE_DIR"

custom_training=$PZ_DP2_CUSTOM_ROOT/common/training

doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/prepare-training-catalog.py \
  "$PZ_DP2_ROOT/common/training/train_clipped_v3.parquet" \
  "$custom_training"
```

The preparer verifies the trusted source checksum, complete row/redshift
contract, legacy SFD correction, and cModel magnitude-error transformation. It
refuses to overwrite either output and writes:

```text
$PZ_DP2_CUSTOM_ROOT/common/training/
├── train_clipped_v3_cmodel_griz.hdf5  # 554,676 rows; 9 columns
└── train_clipped_v3_cmodel_riz.hdf5   # 554,676 rows; 7 columns
```

## Submit the two training jobs

With the same environment active, submit both independent variants:

```bash
cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/submit-training.sh all
```

Use `griz` or `riz` instead of `all` to submit only one variant. Each job asks
for one logical CPU, 8 GiB, and one hour on `cpu_photoz`, matching the official
DNF training shape. It explicitly selects the cModel columns and the requested
band list; it does not modify or invoke the official Stage 1 launcher.

The canonical models are:

```text
$PZ_DP2_CUSTOM_ROOT/
├── griz/stage1/model/
│   ├── model_dp2_v3p1_custom_dnf_cmodel_griz_gold.raw.pickle
│   └── model_dp2_v3p1_custom_dnf_cmodel_griz_gold.pickle
└── riz/stage1/model/
    ├── model_dp2_v3p1_custom_dnf_cmodel_riz_gold.raw.pickle
    └── model_dp2_v3p1_custom_dnf_cmodel_riz_gold.pickle
```

The final wrapper uses creation class
`rail.estimation.algos.dnf.DNFInformer`, catalog tag `lsst_cmodel`, version 0,
selection `gold`, project `dp2_v3p1_custom`, and flavor
`dnf_cmodel_<variant>`. The launcher refuses to overwrite either raw or final
models.

Monitor both submitted IDs with:

```bash
for variant in griz riz; do
  ledger=$PZ_DP2_CUSTOM_ROOT/$variant/stage1/submitted-job-ids.tsv
  jobid=$(tail -n 1 "$ledger" | cut -f3)
  squeue --jobs="$jobid"
done
```

## Validate the completed models

Only load pickle files produced by this controlled workflow. After both jobs
reach `COMPLETED`, run:

```bash
cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/custom/dnf_cmodel_griz_riz/scripts/validate-models.py all
```

The validator compares every persisted training value with the corresponding
prepared table after the documented non-detection replacement. It also checks
the wrapper metadata, 554,676-row redshift contract, four versus three input
features, magnitude norms, KNN parameters, and fitted neighbor state.

## Profile the Apollo jobs

Record the first completed resource measurements separately for each variant:

```bash
for variant in griz riz; do
  stage1=$PZ_DP2_CUSTOM_ROOT/$variant/stage1
  jobid=$(tail -n 1 "$stage1/submitted-job-ids.tsv" | cut -f3)
  test -n "$jobid"

  performance/slurm/slurm-profile \
    --job-id "$jobid" \
    --expected-jobs 1 \
    --concurrency-target 1 \
    --cluster-context-nodes 'apl[01-28]' \
    --label "dnf-cmodel-$variant-stage1-$jobid" \
    --output-dir "$stage1/benchmark/training-$jobid" \
    --capture-slurm-snapshot \
    --fail-on-unsuccessful

  cat "$stage1/benchmark/training-$jobid/summary.log"
done
```

Keep the requested one-CPU, 8-GiB, one-hour shape for reproducibility unless
the measured profiles demonstrate that it is insufficient. Continue with
[`stage2_estimate.md`](stage2_estimate.md) only after validation succeeds.

Verified locally:

- the RTN-124 source contains the required cModel magnitude/error columns;
- the training magnitudes are already SFD-corrected;
- `--bands=griz` trains a four-feature DNF model;
- `--bands=riz` trains a three-feature DNF model;
- DNF non-detections are replaced without relying on pandas chained assignment.

Apollo timing, peak-memory, and node-placement measurements are intentionally
left as runtime evidence rather than predicted values.
