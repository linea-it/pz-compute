# Lightweight Slurm performance profiling

Use [`slurm-profile`](../performance/slurm/slurm-profile) after any Slurm
production workflow. It reads Slurm accounting records through `sacct`; it does
not open scientific input or output files. The measurement cost is therefore
small compared with the production run.

The profiler accepts one array job id, one regular job id, or a file containing
multiple job ids. Array tasks are treated as logical jobs. For regular jobs,
each job id is one logical job. Resource values such as `MaxRSS`, `TotalCPU`,
`AveDiskRead`, `AveDiskWrite`, `MaxDiskRead`, and `MaxDiskWrite` are recovered
from the corresponding `.batch` step when Slurm leaves those fields empty on
the parent record.

## Output artifacts

Each invocation creates an isolated output directory containing:

| File | Contents |
|---|---|
| `summary.log` | compact human-readable production log |
| `summary.json` | machine-readable copy of all aggregate metrics |
| `sacct.tsv` | raw Slurm accounting records used by the analysis |
| `sacct.tsv.gz` | compressed raw accounting for long-term retention |
| `tasks.tsv` | one normalized row per array task or worker job |
| `tasks.tsv.gz` | compressed per-task accounting for long-term retention |
| `benchmark-context.json` | command, host, Git state, context values, file checksums, and storage capacity |
| `task-metadata.tsv` | optional retained input metadata joined to array tasks |
| `time-profile.tsv` | timestamped active/finished-job series |
| `time-profile.svg` | concurrency and cumulative-finished-job profile |
| `cluster-context-sacct.tsv` | optional raw accounting for other allocations overlapping the run |
| `cluster-context-profile.tsv` | optional external jobs/CPUs/memory time series |
| `slurm-snapshot/` | optional post-run partition, node, reservation, queue, and configuration snapshot |

The essential aggregate metrics are:

- submission-to-last-end and first-start-to-last-end wall time;
- task state and exit-code counts, including missing expected jobs;
- partition, account, QOS, requested memory, allocated CPUs, and node placement;
- duration and queue-wait minimum, mean, p50, p95, and maximum;
- submit-to-eligible and eligible-to-start wait distributions;
- mean and peak concurrency, plus their fractions of the configured target;
- time-aligned CPU and memory allocation profiles for the target jobs;
- ramp time to 50% and 90% of target, and time spent at or above 90%;
- successful jobs per hour;
- successful jobs per accumulated job-hour;
- `MaxRSS` p50, p95, and maximum;
- peak-memory/request ratio and walltime-limit utilization;
- average and maximum disk read/write accounting per logical job, with p50,
  p95, and maximum summaries;
- aggregate CPU efficiency, calculated as total CPU time divided by allocated
  CPUs times elapsed time, plus average CPUs actually used per job;
- number of nodes used and logical-job count per node.

`MaxRSS` is sampled by Slurm and may be lower than an instantaneous peak. CPU
efficiency is an aggregate scheduling metric, not a scientific-performance
measure; Slurm notes that `TotalCPU` for a step terminated by a signal may omit
child-process CPU time. Disk values come from Slurm's job-accounting plugin and
therefore remain empty when the cluster does not collect them. They describe
the average or maximum task I/O observed by Slurm, not total filesystem traffic
or storage-system throughput. The profile reports both
submission-to-last-end and first-start-to-last-end wall times. The latter
excludes the initial queue wait but, when several retry arrays are combined,
still includes gaps between attempts. These interpretations follow the official
[`sacct` accounting-field documentation](https://slurm.schedmd.com/sacct.html#SECTION_Job-Accounting-Fields).

The optional cluster context is also reconstructed from `sacct`, so it remains
lightweight and requires no polling daemon. Its window begins at the first
target-job submission and ends at the last target-job completion, covering the
initial queue wait as well as execution. It measures allocations from other
jobs whose execution intervals overlap that window; it does not measure their
instantaneous CPU/RSS consumption or Lustre load. Multi-node jobs that extend
outside the requested hostlist may have their complete allocation counted, so
treat this as scheduler-pressure evidence rather than exact node telemetry.

`--capture-slurm-snapshot` additionally records small, post-run text snapshots
from `scontrol` and `squeue`. This preserves the topology and scheduler
configuration needed to interpret a future comparison even if nodes or
partitions change. Snapshot command failures are recorded in `summary.json`
without discarding the accounting profile.

The raw accounting and normalized task tables are also written as gzip files
by default. Keep those compressed copies even when pruning a large benchmark:
they preserve the task that produced each resource peak and are normally small
compared with workflow logs.

## Reproducibility and task metadata

Use repeated `--context KEY=VALUE` options for resolved workflow settings,
`--context-file` for manifests or configurations that should be recorded by
checksum, and `--storage-path` for a post-run filesystem-capacity snapshot.
The profiler also records its command, host, Python version, working directory,
and Git commit automatically in `benchmark-context.json`.

For Slurm arrays, pass a tab-separated table keyed by `array_task_id` or
`job_id`:

```bash
performance/slurm/slurm-profile \
  --job-id "$ARRAY_JOB_ID" \
  --task-metadata-file input-files.metadata.tsv \
  --context-file input-files.metadata.tsv \
  --storage-path "$RUN_ROOT" \
  --output-dir benchmark/production
```

Additional columns are copied into `tasks.tsv` with a `metadata_` prefix.
Numeric fields receive Pearson correlations against duration, `MaxRSS`, and
total CPU time in `summary.json`. The generic helper below creates metadata
from any line-oriented file manifest; `--parquet-rows` reads only Parquet
footers:

```bash
performance/slurm/manifest-task-metadata \
  --parquet-rows input-files.txt input-files.metadata.tsv
```

## Lightweight live sampling

Post-run accounting cannot reconstruct historical pending reasons, transient
step RSS, or the minimum free filesystem capacity. Start `slurm-watch` after
submission when those measurements matter:

```bash
performance/slurm/slurm-watch \
  --job-id "$JOB_ID" \
  --interval-seconds 60 \
  --storage-path "$RUN_ROOT" \
  --context algorithm=fzboost \
  --output-dir benchmark/live-$JOB_ID
```

The watcher stops after accounting reports a terminal job. It writes:

- `scheduler-samples.tsv`, including task counts by state and pending reason;
- `step-samples.tsv`, with inexpensive metrics exposed by `sstat`;
- `storage-samples.tsv`, with total, free, and user-available filesystem bytes;
- `monitor-summary.json` and `monitor-context.json`.

The default 60-second interval is suitable for long arrays and distributed
workflows. Use 2–5 seconds only for short jobs such as model training. Storage
samples use `statvfs`; they do not traverse output trees and do not replace
project-quota monitoring when quota differs from filesystem capacity.

For adaptive workers whose IDs are not known when monitoring starts, add the
exact Slurm job name. The watcher discovers their IDs from `squeue`, includes
their live `sstat` records, and deduplicates jobs also selected by ID:

```bash
performance/slurm/slurm-watch \
  --job-id "$DRIVER_JOB_ID" \
  --job-name "$WORKER_JOB_NAME" \
  --interval-seconds 60 \
  --output-dir benchmark/live-$DRIVER_JOB_ID
```

`--job-name` may also be used by itself. In that mode the watcher waits up to
the startup timeout for the first matching job and exits after the observed
job population disappears from the queue.

## Basic usage

Profile one completed array or regular job:

```bash
python /path/to/pz-compute/performance/slurm/slurm-profile \
  --job-id "$SLURM_PRODUCTION_JOB_ID" \
  --expected-jobs "$EXPECTED_JOBS" \
  --concurrency-target "$CONCURRENCY_TARGET" \
  --label production-run \
  --output-dir benchmark/production-run \
  --fail-on-unsuccessful
```

On Apollo, add the optional post-run cluster context to distinguish low
realized concurrency from a fully available partition:

```bash
python /path/to/pz-compute/performance/slurm/slurm-profile \
  --job-id "$SLURM_PRODUCTION_JOB_ID" \
  --expected-jobs "$EXPECTED_JOBS" \
  --concurrency-target "$CONCURRENCY_TARGET" \
  --cluster-context-nodes 'apl[01-28]' \
  --capture-slurm-snapshot \
  --label production-with-cluster-context \
  --output-dir benchmark/production-with-cluster-context \
  --fail-on-unsuccessful
```

The context query uses `sacct --allusers`. If site permissions do not expose
other users' accounting, omit the option; all target-job metrics still work.
For reproducible offline analysis, retain `cluster-context-sacct.tsv` and pass
it later with `--cluster-sacct-file`.

Profile several independent jobs, such as Dask workers:

```bash
python /path/to/pz-compute/performance/slurm/slurm-profile \
  --job-id-file worker-job-ids.txt \
  --expected-jobs "$EXPECTED_JOBS" \
  --concurrency-target "$CONCURRENCY_TARGET" \
  --label distributed-production-run \
  --output-dir benchmark/distributed-production-run
```

The same command can combine a production array and retry arrays by listing
all their ids in one job-id file. In that case the profile describes every
execution attempt and the end-to-end interval includes the time between
attempts. Output validation remains responsible for proving that every input
work item has exactly one complete final product.

Use `--fail-on-unsuccessful` only when every profiled job must end as
`COMPLETED` with exit code `0:0`. Do not use it for a combined profile that
intentionally retains failed attempts or for workers that a distributed
scheduler may cancel normally while closing the cluster; their unsuccessful
state counts remain visible in `summary.log` and `summary.json`.

If Slurm accounting is briefly delayed after completion, wait until `sacct`
shows the terminal task records and run the profiler again. The profiler
overwrites only the small files in its selected benchmark directory.
