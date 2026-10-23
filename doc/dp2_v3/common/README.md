# Shared prerequisites

These procedures create inputs shared by the individual and batch routes. They
do not train, estimate, or build HATS products for any algorithm.

Run each procedure once per DP2 run root:

1. [`prepare_training_catalog.md`](prepare_training_catalog.md): validate and
   convert the clipped RTN-124 training catalog used by Stage 1.
2. [`prepare_estimation_manifests.md`](prepare_estimation_manifests.md): create
   the full and five-largest-shard manifests used by Stage 2.

All individual algorithms may reuse these immutable inputs. Reusing them does
not submit or otherwise depend on another algorithm.
