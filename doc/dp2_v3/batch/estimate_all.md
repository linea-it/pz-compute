# Serial batch Stage 2: smoke, pilot, production, profile, and validate

For the current algorithm only, the controller runs the same Stage 2 sequence
as its individual guide. No array from another algorithm is submitted until
the current algorithm has completed Stage 3.

## 1. Smoke test

The controller runs:

```text
smoke-estimates.sh <algorithm>
```

This projects a 10,000-row sample, verifies the model and reviewed YAML, and
writes the algorithm-specific `smoke/READY` checksums. For official BPZ it also
validates the 136-template tree and warms the AB cache before any concurrent
array tasks can start.

Failure of the smoke test stops the workflow without submitting a pilot.

## 2. Five-largest-shard pilot

The shared manifests are created during batch preflight. The controller submits
one five-task pilot for the current algorithm, with maximum concurrency 5, and
waits for all tasks to finish.

It then writes:

```text
$PZ_DP2_ROOT/<algorithm>/stage2/benchmark/pilot-<jobid>/
```

The profiler requires five successful logical jobs and records memory,
walltime, CPU, I/O, queue wait, realized concurrency, node placement, and
overlapping cluster allocations. The fast Stage 2 validator then checks the
five expected HDF5 outputs against the pilot manifest. A failed pilot,
profiling error, or invalid output stops the entire batch.

This automated pilot is a regression/safety gate for already accepted
requests. The controller does not pause for an operator to inspect the profile
or alter resources. New releases and configurations that still require such a
decision must use the individual Stage 2 guide instead.

Any unsuccessful task, nonzero exit, missing task/accounting record, profiler
failure, missing output, or structural-validation error stops here and the
full catalog is not submitted. A successful pilot whose measured memory or
walltime is merely close to its configured limit still advances: interpreting
that headroom is a tuning decision that must already have been made in the
individual workflow.

## 3. Complete production array

Only after the pilot profile and validation pass does the controller submit the
full sorted manifest. Production defaults remain algorithm-specific:

| Algorithm | Maximum concurrent tasks | Memory/task | Walltime/task |
|---|---:|---:|---:|
| FlexZBoost | 82 | 40 GiB | 01:00:00 |
| DNF | 82 | 40 GiB | 02:00:00 |
| BPZ official | 20 | 40 GiB | 24:00:00 |

Because only one production array exists at a time, these ceilings have the
same meaning and output behavior as the individual route. The controller waits
for the array parent to reach `COMPLETED / 0:0`, profiles every expected task,
and writes:

```text
$PZ_DP2_ROOT/<algorithm>/stage2/benchmark/production-<jobid>/
```

It finally validates every expected HDF5 against the full manifest. Complete
pilot outputs are recognized and skipped by their corresponding production
array tasks, exactly as in the manual workflow.

## 4. Result and failure boundary

Successful Stage 2 leaves the standard individual layout:

```text
$PZ_DP2_ROOT/<algorithm>/stage2/
├── output/Norder=*/Dir=*/Npix=*.hdf5
├── log/slurm-*.{out,err}
├── smoke/{smoke-test.hdf5,READY}
├── benchmark/{pilot-<jobid>,production-<jobid>}/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Any unsuccessful array task, missing accounting record, timeout, missing
output, invalid completion marker, schema mismatch, or unexpected HDF5 stops
the batch before Stage 3. Partial but complete outputs remain available for a
reviewed recovery; the controller never silently retries scientific work.

After full validation the same algorithm continues to
[serial Stage 3](build_hats_all.md).
