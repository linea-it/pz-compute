# DP2 DNF Stage 1: train the model

This is the canonical individual path for the official six-band DP2 DNF
workflow. It uses the shared clipped RTN-124 catalog and keeps every artifact
under `$PZ_DP2_ROOT/dnf/stage1/`.

## 1. Prepare the shared catalog

Complete the [Apollo setup](../dp2_setup_apollo.md), then follow the
[shared training-catalog procedure](../common/prepare_training_catalog.md).
It creates:

```text
$PZ_DP2_ROOT/common/training/train_clipped_v3_gaap1p0.hdf5
```

The table contains 554,676 rows with `redshift`, six already-dereddened GAaP
1.0 magnitudes, and six magnitude errors in `ugrizy` order. Do not remove the
501 training rows above redshift 6; they are present in the trusted reference
model.

## 2. Submit DNF only

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-training.sh dnf
```

Monitor the job, follow its logs, and inspect the resulting model with the
[Stage 1 terminal commands](inspect_runs.md#stage-1-training), using
`algorithm=dnf`.

The launcher uses [`dnf-train.yaml`](../config/dnf-train.yaml) and writes:

```text
$PZ_DP2_ROOT/dnf/stage1/
├── model/
│   ├── model_dp2_v3p1_dnf_dp2_6band_gold.raw.pickle
│   └── model_dp2_v3p1_dnf_dp2_6band_gold.pickle
├── log/
│   ├── train-dnf-<jobid>.out
│   └── train-dnf-<jobid>.err
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

The final model receives `catalog_tag=lsst_gaap_1p0`, creation class
`rail.estimation.algos.dnf.DNFInformer`, and provenance
`dp2_v3p1/dp2_6band/gold`.

## 3. Validate against the trusted model

Download the trusted
[`DNF model DP2 gold 6 bands RTN-124`](https://pzserver.linea.org.br/product/434_dnf_model_dp2_gold_6_bands_rtn124)
to `$PZ_DP2_ROOT/dnf/stage1/model/reference/`, then verify it before loading:

```bash
cd "$PZ_DP2_ROOT"
printf '%s  %s\n' \
  bd677d456dba126ef3b47814f34559a280dc3a92d58d58f598f7a21a8cd99ab4 \
  dnf/stage1/model/reference/model_dp2_v3p1_dnf_dp2_6band_gold.pickle | \
  sha256sum --check

cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/scripts/validate-models.py dnf
```

Pickle files can execute code while loading; validate the checksum and source
first. The validator checks both reference and candidate wrapper provenance,
the five persisted DNF fields, array dimensions, training-redshift range,
normalization, and fitted nearest-neighbor state.

The complete parameter rationale and trusted-pickle inspection are documented
in [`dnf_science.md`](../references/dnf_science.md).

Continue with [`dnf_stage2_estimate.md`](dnf_stage2_estimate.md).
