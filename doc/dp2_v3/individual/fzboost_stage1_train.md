# DP2 FlexZBoost Stage 1: train the model

This is the canonical individual path for FlexZBoost. It uses the shared
catalog but keeps the model, logs, benchmarks, and job IDs under
`$PZ_DP2_ROOT/fzboost/stage1/`.

## 1. Prepare the shared catalog

Complete the [Apollo setup](../dp2_setup_apollo.md), then follow the
[shared training-catalog procedure](../common/prepare_training_catalog.md).
This creates one algorithm-neutral artifact:

```text
$PZ_DP2_ROOT/common/training/train_clipped_v3_gaap1p0.hdf5
```

It contains `redshift`, six GAaP 1.0 magnitudes, and six errors in `ugrizy`
order, with no additional extinction correction, filtering, or row reordering.

## 2. Submit FlexZBoost only

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-training.sh fzboost
```

The launcher uses [`fzboost-train.yaml`](../config/fzboost-train.yaml) and writes:

```text
$PZ_DP2_ROOT/fzboost/stage1/
├── model/
│   ├── model_dp2_v3p1_fzboost_dp2_6band_gold.raw.pickle
│   └── model_dp2_v3p1_fzboost_dp2_6band_gold.pickle
├── log/
│   ├── train-fzboost-<jobid>.out
│   └── train-fzboost-<jobid>.err
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

The final model receives `catalog_tag=lsst_gaap_1p0` and provenance
`dp2_v3p1/dp2_6band/gold`.

## 3. Validate the FlexZBoost model

Download the trusted
[`FlexZBoost model DP2 gold 6 bands RTN-124`](https://pzserver.linea.org.br/product/435_flexzboost_model_dp2_gold_6_bands_rtn124)
to `$PZ_DP2_ROOT/fzboost/stage1/model/reference/`, verify its checksum, and
validate both the reference and candidate models:

```bash
cd "$PZ_DP2_ROOT"
printf '%s  %s\n' \
  33e0fcfa29c10c4305e6de1c739a4765cc1291110d08d8c23674af8de6d8b127 \
  fzboost/stage1/model/reference/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle | \
  sha256sum --check

cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/scripts/validate-models.py fzboost
```

Only load a pickle after confirming that it came from the trusted PZ Server
product. The complete scientific rationale is documented separately in
[`fzboost_science.md`](../references/fzboost_science.md). Historical production
evidence is summarized in
[`fzboost_runs.md`](../references/fzboost_runs.md).

Continue with [`fzboost_stage2_estimate.md`](fzboost_stage2_estimate.md).
