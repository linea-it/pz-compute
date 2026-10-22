# DP2 BPZ Stage 1: create the HDFN prior model

This procedure creates only the BPZ model. The environment and prepared catalog
are shared with the other algorithms, but the submission command selects only
`bpz` and writes to its algorithm-specific model directory.

## 1. Shared environment and catalog

Complete the [Apollo setup](../dp2_setup_apollo.md), then follow the
[shared training-catalog procedure](../common/prepare_training_catalog.md).
The expected algorithm-neutral file is:

```text
$PZ_RUN_ROOT/dp2-v3/common/training/train_clipped_v3_gaap1p0.hdf5
```

In logical order, it contains `redshift`, six `{band}_gaap1p0Mag` magnitudes,
and six `{band}_gaap1p0MagErr` errors for `ugrizy`. The magnitudes are already
dereddened; do not apply SFD again.

## 2. Reproduced BPZ configuration

Training uses [`bpz-train.yaml`](../config/bpz-train.yaml), transcribed from
the official `dp2_v3p1/dp2_6band/gold` configuration. The rationale for every
training and estimation setting, plus the state confirmed in the published
pickle, is maintained in
[`bpz_science.md`](../references/bpz_science.md).

## 3. Submit BPZ only

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-training.sh bpz
```

Monitor the job, follow its logs, and inspect the resulting model with the
[Stage 1 terminal commands](inspect_runs.md#stage-1-training), using
`algorithm=bpz`.

The job writes:

```text
$PZ_DP2_ROOT/bpz/stage1/
├── model/model_dp2_v3p1_bpz_dp2_6band_gold.pickle
├── log/
│   ├── train-bpz-<jobid>.out
│   └── train-bpz-<jobid>.err
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

The launcher also adds `catalog_tag=lsst_gaap_1p0` and provenance
`dp2_v3p1/dp2_6band/gold`, matching the published artifact.

## 4. Validate

Download the trusted
[`BPZ model DP2 gold 6 bands RTN-124`](https://pzserver.linea.org.br/product/433_bpz_model_dp2_gold_6_bands_rtn124)
product to `$PZ_DP2_ROOT/bpz/stage1/model/reference/`, verify its checksum, and
validate both the reference and candidate models:

```bash
cd "$PZ_DP2_ROOT"
printf '%s  %s\n' \
  4872eacee26ae6a5d3716cccd423c7e30b611ed7216e373153058ed59b985170 \
  bpz/stage1/model/reference/model_dp2_v3p1_bpz_dp2_6band_gold.pickle | \
  sha256sum --check

cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/scripts/validate-models.py bpz
```

Only load a pickle after confirming that it came from the trusted PZ Server
product. The validator checks the prior vectors, metadata, and zero-point
offsets. It does not claim that a BPZ production run has been validated.

Continue with [`bpz_stage2_estimate.md`](bpz_stage2_estimate.md).
