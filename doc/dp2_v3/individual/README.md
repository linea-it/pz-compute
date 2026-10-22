# Individual runs

Use this directory to run and monitor one algorithm in isolation. Every
filename includes the algorithm name and contains only the decisions and
commands relevant to that algorithm.

## FlexZBoost

1. [`fzboost_stage1_train.md`](fzboost_stage1_train.md): reproduce the
   reference model.
2. [`fzboost_stage2_estimate.md`](fzboost_stage2_estimate.md): smoke test,
   pilot, and production estimation over the DP2 catalogs.
3. [`fzboost_stage3_build_hats.md`](fzboost_stage3_build_hats.md): build HATS
   products while keeping Dask logs under the FlexZBoost directory.

## BPZ

1. [`bpz_stage1_train.md`](bpz_stage1_train.md): create and validate the HDFN
   prior used by DP2.
2. [`bpz_stage2_estimate.md`](bpz_stage2_estimate.md): warm the BPZ cache,
   smoke test, pilot, and run production estimation over the DP2 catalogs.
3. [`bpz_stage3_build_hats.md`](bpz_stage3_build_hats.md): build HATS products
   while keeping Dask logs under the BPZ directory.

## DNF

1. [`dnf_stage1_train.md`](dnf_stage1_train.md): reproduce and validate the
   six-band DP2 nearest-neighbor model.
2. [`dnf_stage2_estimate.md`](dnf_stage2_estimate.md): smoke test, pilot, and
   production estimation over the DP2 catalogs.
3. [`dnf_stage3_build_hats.md`](dnf_stage3_build_hats.md): build and validate
   the DNF HATS products.

## BPZ test (standalone, non-production)

1. [`bpz_test_stage1_train.md`](bpz_test_stage1_train.md): create and validate
   a separate COSMOS31-compatible test model.
2. [`bpz_test_stage2_estimate.md`](bpz_test_stage2_estimate.md): smoke test,
   pilot, and estimate below the independent `bpz_test/` tree.
3. [`bpz_test_stage3_build_hats.md`](bpz_test_stage3_build_hats.md): build and
   validate HATS products that remain explicitly marked as test artifacts.

`bpz_test` is never included in `all`; the batch route contains only official
BPZ, DNF, and FlexZBoost.

The shared environment is documented in
[`dp2_setup_apollo.md`](../dp2_setup_apollo.md). Prepare the algorithm-neutral
inputs through [`common/README.md`](../common/README.md). The individual guides
do not depend on batch instructions and every launcher accepts the named
algorithm without requiring the other model or output tree.

To prepare and dispatch every algorithm together instead, use
[`batch/README.md`](../batch/README.md).
