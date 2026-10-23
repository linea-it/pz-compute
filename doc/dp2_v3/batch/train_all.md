# DP2 batch Stage 1: prepare once, train FlexZBoost, BPZ, and DNF

This stage uses one clipped RTN-124 training table for all three algorithms and
writes each model below its own `stage1/model/` directory. Run the common
[Apollo setup](../dp2_setup_apollo.md) first.

## 1. Prepare the shared catalog

Follow the algorithm-neutral
[shared training-catalog procedure](../common/prepare_training_catalog.md).
Run it once, then require the resulting artifact before submitting the batch:

```bash
test -f "$PZ_DP2_ROOT/common/training/train_clipped_v3_gaap1p0.hdf5"
```

## 2. Reviewed algorithm parameters

The executable settings are [`fzboost-train.yaml`](../config/fzboost-train.yaml),
[`bpz-train.yaml`](../config/bpz-train.yaml), and
[`dnf-train.yaml`](../config/dnf-train.yaml). Their complete scientific
provenance and parameter-by-parameter rationale are kept separately in
[`fzboost_science.md`](../references/fzboost_science.md) and
[`bpz_science.md`](../references/bpz_science.md), and
[`dnf_science.md`](../references/dnf_science.md).

## 3. Submit all three models

From the repository checkout:

```bash
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-training.sh all
```

The jobs remain in Slurm after logout. `all` submits three independent jobs;
it does not introduce dependencies between them. Each job ID is appended to
the matching
`$PZ_DP2_ROOT/<algorithm>/stage1/submitted-job-ids.tsv`.

For a single algorithm, use its named guide under
[`individual/README.md`](../individual/README.md).

For FlexZBoost the supplied resource request retains the previously validated
single-node Apollo configuration. BPZ's informer only materializes the fixed
prior, while DNF builds a nearest-neighbor index; both start with the smaller
one-CPU, 8-GiB request. Inspect `sacct` after each job and tune future requests
from observed `MaxRSS` and `Elapsed`.

## 4. Validate all model artifacts

Download all three trusted PZ Server references:

- [`FlexZBoost model DP2 gold 6 bands RTN-124`](https://pzserver.linea.org.br/product/435_flexzboost_model_dp2_gold_6_bands_rtn124)
  to `$PZ_DP2_ROOT/fzboost/stage1/model/reference/`;
- [`BPZ model DP2 gold 6 bands RTN-124`](https://pzserver.linea.org.br/product/433_bpz_model_dp2_gold_6_bands_rtn124)
  to `$PZ_DP2_ROOT/bpz/stage1/model/reference/`.
- [`DNF model DP2 gold 6 bands RTN-124`](https://pzserver.linea.org.br/product/434_dnf_model_dp2_gold_6_bands_rtn124)
  to `$PZ_DP2_ROOT/dnf/stage1/model/reference/`.

Confirm the reference checksums before loading them:

```bash
cd "$PZ_DP2_ROOT"
printf '%s  %s\n' \
  33e0fcfa29c10c4305e6de1c739a4765cc1291110d08d8c23674af8de6d8b127 \
  fzboost/stage1/model/reference/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle \
  4872eacee26ae6a5d3716cccd423c7e30b611ed7216e373153058ed59b985170 \
  bpz/stage1/model/reference/model_dp2_v3p1_bpz_dp2_6band_gold.pickle \
  bd677d456dba126ef3b47814f34559a280dc3a92d58d58f598f7a21a8cd99ab4 \
  dnf/stage1/model/reference/model_dp2_v3p1_dnf_dp2_6band_gold.pickle | \
  sha256sum --check
```

Pickle files can execute code while loading, so run the following command only
after verifying that all three references came from the trusted PZ Server
products:

```bash
cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/scripts/validate-models.py all
```

The single `all` command validates the reference and newly trained artifact for
all three algorithms. It checks shared wrapper metadata plus the persisted
FlexZBoost basis/regression state, BPZ HDFN prior/zero-point state, and DNF
training arrays/nearest-neighbor state.

Continue with [batch Stage 2](estimate_all.md).
