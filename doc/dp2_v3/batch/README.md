# Serial production batch

> Use this route only after the current data release, scientific configuration,
> and resource requests have been validated through the individual workflows.
> For a new release or any run that may require memory, walltime, concurrency,
> or algorithm tuning after its pilots, use
> [`individual/`](../individual/README.md). The batch controller has no manual
> tuning checkpoint: a successful pilot is treated as a safety confirmation
> and production starts automatically.

The batch route is the fully automated equivalent of running the official
individual workflows by hand, one algorithm at a time. One lightweight Slurm
controller executes the default order:

```text
fzboost: Stage 1 → Stage 2 smoke → Stage 2 pilot → Stage 2 production → Stage 3
dnf:     Stage 1 → Stage 2 smoke → Stage 2 pilot → Stage 2 production → Stage 3
bpz:     Stage 1 → Stage 2 smoke → Stage 2 pilot → Stage 2 production → Stage 3
```

Every submitted child job must finish successfully, pass its scientific
validator, and produce its Slurm benchmark before the controller advances.
Algorithms and stages never run in parallel. `bpz_test` is deliberately
excluded because it is not an official production workflow.

The controller calls the same launchers, validators, and profiler commands as
the individual guides. Scientific artifacts therefore retain exactly the same
layout below `$PZ_DP2_ROOT/<algorithm>/stage{1,2,3}/`; batch mode adds only a
controller report directory below `$PZ_DP2_ROOT/batch/`.

## 1. Complete prerequisites

Complete the [Apollo setup](../dp2_setup_apollo.md) and prepare the shared
[training catalog](../common/prepare_training_catalog.md). Before submission,
place the three trusted reference models in the locations documented by the
individual Stage 1 guides and install the official BPZ 136-template data tree
described in
[`bpz_reference_data.md`](../references/bpz_reference_data.md).

Before choosing batch, complete at least one reviewed individual pilot for
each selected algorithm on the same release and encode the accepted memory,
walltime, and concurrency defaults in the versioned launchers. Batch profiling
measures and records the automated run; it does not make tuning decisions.

Each selected algorithm must start without existing Stage 2 or Stage 3
products below its target `$PZ_DP2_ROOT`. The controller always begins that
algorithm at Stage 1 and refuses to mix downstream outputs with a newly trained
model. Use a fresh production root for a complete replay.

The controller performs a fail-fast preflight before training anything. It:

- checks the shared training catalog;
- requires the active GAaP environment freeze to match the one that prepared
  the shared training catalog;
- verifies all three trusted model checksums;
- validates the official BPZ reference-data tree;
- creates the full and five-largest-shard manifests;
- requires at least 24 TiB free initially for the three retained workflows and
  rechecks an 8-TiB floor before each algorithm;
- records the repository commit, environment settings, storage state, and
  adaptive-worker configuration.

## 2. Submit the complete serial workflow

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-production-batch.sh
```

The command returns immediately after submitting the controller. The login
session can then be closed. Its output prints the controller job ID and a
unique run directory such as:

```text
$PZ_DP2_ROOT/batch/production-<UTC timestamp>/
```

The default controller allocation is one task with 2 CPUs, 8 GiB, and a
14-day walltime on one of the smaller `apl01-16` nodes. With an explicit
one-node request, the node list is an eligibility set rather than a multi-node
allocation. Keeping the 8-GiB controller off `apl17-26` also preserves the
six-slot packing of 40-GiB tasks on every large node. Each child retains the
resources documented for its individual algorithm and stage.

## 3. Monitor progress

Recover the latest controller record and follow its logs:

```bash
batch_root=$PZ_DP2_ROOT/batch
IFS=$'\t' read -r submitted controller_jobid run_tag algorithms < \
  <(tail -n 1 "$batch_root/submitted-controller-job-ids.tsv")
run_dir=$batch_root/$run_tag

squeue -j "$controller_jobid" || true
tail -F "$run_dir/controller.log" "$run_dir/controller.err"
```

From another terminal, inspect the durable status and child-job ledgers:

```bash
column -t -s $'\t' "$run_dir/status.tsv"
column -t -s $'\t' "$run_dir/jobs.tsv"
column -t -s $'\t' "$run_dir/artifacts.tsv"
cat "$run_dir/active-job.tsv" 2>/dev/null || true
```

`status.tsv` identifies the current algorithm and operation, including
training, smoke test, pilot, production, HATS validation, and each benchmark.
`jobs.tsv` records every training job, array, and Stage 3 driver job.
`artifacts.tsv` indexes every model/output tree and benchmark generated so the
final products can be located without reconstructing paths from job IDs.

## 4. Success and failure behavior

On complete success the run directory contains `SUCCESS` and `summary.md`.
Every algorithm also contains the same model, estimates, HATS products, logs,
environment freezes, submission ledgers, and benchmark directories created by
the individual route.

On the first failure the controller stops before the next operation or
algorithm. It writes `FAILED` and `failure-report.md`, identifying:

- the algorithm and exact stage or validation operation;
- the failed child job and its Slurm state, when applicable;
- the controller command and exit code;
- paths to the controller logs and durable ledgers;
- a ready-to-run `sacct` inspection command.

If the controller is interrupted while a child job is active, it requests
cancellation of that child before writing the failure report. There are no
automatic scientific retries: completed outputs remain available for a
reviewed recovery, while the report preserves the point of failure.

### Recovery after a partial failure

The controller currently has no stage-aware resume. `PZ_BATCH_ALGORITHMS` can
select which algorithms a **new** serial run will execute, but every selected
algorithm starts again at Stage 1. Do not use `dnf,bpz`, for example, as a DNF
resume when DNF already has Stage 2 outputs: retraining the model and silently
skipping old complete HDF5 files would mix provenance, so the preflight rejects
that situation.

Recover the failed algorithm with its individual guide instead:

- Stage 2 resubmission validates and skips complete HDF5 files, preserves an
  incomplete file with an `.incomplete-<job>-<task>` suffix, and retries the
  missing work. No manual deletion is normally required when the model and
  configuration are unchanged.
- Stage 3 uses a new run tag and rebuilds with `--overwrite`; prior logs and
  benchmarks remain isolated. No manual deletion is normally required.
- If Stage 1, the model, or any scientific configuration changes, do not reuse
  downstream outputs. Use a fresh `$PZ_DP2_ROOT` or perform an explicit,
  reviewed archival/cleanup before recomputing Stage 2 and Stage 3.

After DNF is recovered and completed individually, a new controller with
`PZ_BATCH_ALGORITHMS=bpz` may safely automate only the remaining BPZ workflow.

## 5. Optional operational overrides

Set overrides before calling the submission script:

```bash
export PZ_BATCH_CONTROLLER_TIME=14-00:00:00
export PZ_BATCH_JOB_TIMEOUT_SECONDS=864000
export PZ_BATCH_POLL_SECONDS=30
export PZ_BATCH_MIN_FREE_GIB=24576
export PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB=8192
export PZ_HATS_MIN_WORKERS=20
export PZ_HATS_MAX_WORKERS=80
export PZ_HATS_SCALE_DOWN_DELAY=180

doc/dp2_v3/scripts/submit-production-batch.sh
```

`PZ_BATCH_JOB_TIMEOUT_SECONDS` applies independently to each submitted child
job, including queue wait. A timeout cancels that child and produces a failure
report. `PZ_BATCH_ALGORITHMS` may select an official subset or alternate serial
order for a new run; it is not a stage-resume control. The production default
remains `fzboost,dnf,bpz`.

The stage-specific automation and resulting artifacts are detailed in:

1. [`train_all.md`](train_all.md)
2. [`estimate_all.md`](estimate_all.md)
3. [`build_hats_all.md`](build_hats_all.md)
