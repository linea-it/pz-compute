# Serial batch Stage 1: train, profile, and validate each model

The production controller runs Stage 1 separately for `fzboost`, `dnf`, and
`bpz`, in that order. It never invokes `submit-training.sh all`; each named
submission must complete before its benchmark and validator run and before the
workflow advances.

Start the workflow with the single command documented in
[`README.md`](README.md). This page describes what the controller performs for
each algorithm.

## Shared prerequisite

All three algorithms use the catalog prepared by the
[shared training procedure](../common/prepare_training_catalog.md):

```text
$PZ_DP2_ROOT/common/training/train_clipped_v3_gaap1p0.hdf5
```

The preflight verifies the trusted FlexZBoost, DNF, and BPZ reference-model
checksums before any candidate training begins. This preserves the same pickle
safety boundary as the individual guides.

## Per-algorithm execution

For each algorithm the controller performs the equivalent of:

```text
submit-training.sh <algorithm>
→ wait for COMPLETED / 0:0
→ generate the Stage 1 Slurm benchmark
→ validate-models.py <algorithm>
```

FlexZBoost requests 16 logical CPUs, 24 GiB, and 30 minutes. This retains
headroom over the measured 7.55 average CPUs, 15.34-GiB historical memory
peak, and 146-second production runtime without reserving most of a node. DNF
and BPZ each request one task, one CPU, 8 GiB, and one hour. No Stage 1
submission sets a node list: Slurm may select any node eligible for
`cpu_photoz`, while every resource shape remains small enough to fit an older
node. The next stage does not start merely
because the Slurm job ended: the profile must be written and the
candidate/reference structural validation must also pass.

The resulting layout is identical to an individual run:

```text
$PZ_DP2_ROOT/<algorithm>/stage1/
├── model/
├── log/
├── benchmark/live-<jobid>/
├── benchmark/training-<jobid>/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

The live benchmark samples scheduler state, pending reasons, step CPU/memory/I/O,
and filesystem headroom every three seconds. The completed-job benchmark
contains queue wait, elapsed time, CPU and memory use, node placement,
allocation profiles, compressed raw tables, the training-configuration
checksum, repository context, and overlapping allocations over `apl01-28`.

## Failure boundary

A failed training job, missing benchmark accounting, checksum problem, or
model-validation error stops the complete batch at that algorithm. The
controller does not submit its Stage 2 or any later algorithm. The batch
failure report records the algorithm, operation, child job ID, Slurm state,
and inspection command.

After successful model validation the same algorithm continues immediately to
the [serial Stage 2 procedure](estimate_all.md).
