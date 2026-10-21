# Batch runs

Use this directory to prepare shared inputs and submit every supported
algorithm together. Batch guides always operate on the complete algorithm
registry; use `individual/` when selecting only one algorithm.

Algorithm-neutral input preparation is maintained in
[`common/`](../common/README.md) and reused here without duplication.

1. [`train_all.md`](train_all.md): prepare the catalog once, submit every
   training job, and validate every model.
2. [`estimate_all.md`](estimate_all.md): run smoke tests and pilots, then
   submit one Slurm array per algorithm over every DP2 shard.
3. [`build_hats_all.md`](build_hats_all.md): submit one Stage 3 driver per
   algorithm and validate every completed HATS product.

The batch entry points consistently use `all`:

```bash
# Stage 1: submit all training jobs; validate after both jobs complete.
doc/dp2_v3/scripts/submit-training.sh all
doc/dp2_v3/scripts/validate-models.py all

# Stage 2: smoke-test all algorithms, then submit all production arrays.
doc/dp2_v3/scripts/smoke-estimates.sh all
doc/dp2_v3/scripts/submit-estimates.sh all

# Stage 3: submit all HATS drivers; validate after both jobs complete.
doc/dp2_v3/scripts/submit-hats.sh all
doc/dp2_v3/scripts/validate-hats.py all
```

Follow the stage guides for prerequisites, pilot runs, and the required waits
between submission and validation commands.

For a single algorithm, use the named guides in
[`individual/README.md`](../individual/README.md).
