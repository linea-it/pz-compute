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

The shared environment is documented in
[`dp2_setup_apollo.md`](../dp2_setup_apollo.md). Prepare the algorithm-neutral
inputs through [`common/README.md`](../common/README.md). The individual guides
do not depend on batch instructions and every launcher accepts the named
algorithm without requiring the other model or output tree.

To prepare and dispatch every algorithm together instead, use
[`batch/README.md`](../batch/README.md).
