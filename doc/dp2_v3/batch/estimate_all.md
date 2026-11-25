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

For DNF, the shared smoke and array launchers enable log-space Gaussian PDF
evaluation and the `nan` no-photometry policy. The latter keeps objects
without a usable magnitude–error pair in any of the six selected bands and
stores an all-`NaN` PDF. The smoke and array validators check the persisted
policy and report the counts of no-estimate rows and recovered legacy
underflows.

Failure of the smoke test stops the workflow without submitting a pilot.

## 2. Five-largest-shard pilot

The shared manifests and their per-shard metadata sidecars are created during
batch preflight. The metadata records input path, bytes, modification time,
and Parquet row count. The controller submits one five-task pilot for the
current algorithm, with maximum concurrency 5, and waits for all tasks to
finish while a 60-second live sampler records scheduler and storage state.

It then writes:

```text
$PZ_DP2_ROOT/<algorithm>/stage2/benchmark/pilot-<jobid>/
$PZ_DP2_ROOT/<algorithm>/stage2/benchmark/live-pilot-<jobid>/
```

The profiler requires five successful logical jobs and records memory,
walltime, CPU, I/O, queue wait, realized concurrency, node placement, and
overlapping cluster allocations. It joins the shard metadata to each task and
reports correlations of input size and row count with duration, `MaxRSS`, and
CPU time. It also retains compressed accounting, configuration/manifests by
checksum, repository context, and filesystem capacity. The fast Stage 2
validator then checks the
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

The historical DNF pilot predates these PDF policies. Before using batch
for DNF, review the runtime, memory, and quality counters from a
[new individual pilot](../individual/dnf_stage2_estimate.md#2-run-and-profile-the-mandatory-five-file-pilot)
with both protections enabled.

## 3. Complete production array

Only after the pilot profile and validation pass does the controller submit the
full sorted manifest. Production defaults remain algorithm-specific:

| Algorithm | Maximum concurrent tasks | Memory/task | Walltime/task |
|---|---:|---:|---:|
| FlexZBoost | 82 | 38 GiB | 00:30:00 |
| DNF | 82 | 40 GiB | 02:00:00 |
| BPZ official | 20 | 40 GiB | 24:00:00 |

Because only one production array exists at a time, these ceilings have the
same meaning and output behavior as the individual route. They cap concurrent
tasks but do not require that many slots to become available at once: Slurm
starts every task that fits and leaves the remainder pending. The controller
waits for the array parent to reach `COMPLETED / 0:0`, profiles every expected
task, and writes:

```text
$PZ_DP2_ROOT/<algorithm>/stage2/benchmark/production-<jobid>/
$PZ_DP2_ROOT/<algorithm>/stage2/benchmark/live-production-<jobid>/
```

It finally validates every expected HDF5 against the full manifest. Production
tasks reuse pilot outputs that pass the current Stage 2 checks. For DNF,
those checks also require the current stable-PDF and no-photometry policies.

## 4. Result and failure boundary

Successful Stage 2 leaves the standard individual layout:

```text
$PZ_DP2_ROOT/<algorithm>/stage2/
├── output/Norder=*/Dir=*/Npix=*.hdf5
├── log/slurm-*.{out,err}
├── smoke/{smoke-test.hdf5,READY}
├── benchmark/{pilot-<jobid>,production-<jobid>}/
├── benchmark/{live-pilot-<jobid>,live-production-<jobid>}/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Any unsuccessful array task, missing accounting record, timeout, missing
output, invalid completion marker, schema mismatch, or unexpected HDF5 stops
the batch before Stage 3. Partial but complete outputs remain available for a
reviewed recovery; the controller never silently retries scientific work.

After full validation the same algorithm continues to
[serial Stage 3](build_hats_all.md).
