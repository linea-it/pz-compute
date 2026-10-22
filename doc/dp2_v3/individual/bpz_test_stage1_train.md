# DP2 BPZ test Stage 1: create the COSMOS31 test model

> **TEST ONLY:** this standalone workflow is not official DP2 BPZ and is not
> suitable for scientific production.

This stage creates a model only below `$PZ_DP2_ROOT/bpz_test/stage1/`. It uses
the common clipped training catalog but never reads or writes the official
`bpz/` tree.

## 1. Prepare the shared input

Complete the [Apollo setup](../dp2_setup_apollo.md) and the
[shared training-catalog procedure](../common/prepare_training_catalog.md).
The required input is:

```text
$PZ_DP2_ROOT/common/training/train_clipped_v3_gaap1p0.hdf5
```

## 2. Submit the test training job

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-training.sh bpz_test
```

Monitor the job, follow its logs, and inspect the resulting model with the
[Stage 1 terminal commands](inspect_runs.md#stage-1-training), using
`algorithm=bpz_test`.

[`bpz-test-train.yaml`](../config/bpz-test-train.yaml) creates a test-specific
HDFN prior with `nt_array=[7,12,12]`, matching the 31 public COSMOS templates.
The resulting artifact is:

```text
$PZ_DP2_ROOT/bpz_test/stage1/model/model_dp2_v3p1_bpz_test_cosmos31_gold.pickle
```

Its provenance flavor is `cosmos31_test`, preventing it from validating as an
official BPZ model.

## 3. Validate the test model

After the Slurm job completes successfully:

```bash
doc/dp2_v3/scripts/validate-models.py bpz_test
```

Unlike official BPZ validation, this checks only the newly created candidate:
there is no trusted published reference artifact for `bpz_test`. It verifies
the wrapper, test provenance, HDFN prior values, `[7,12,12]` partition, and six
zero-point offsets.

Continue with [`bpz_test_stage2_estimate.md`](bpz_test_stage2_estimate.md).
