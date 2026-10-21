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
| `tasks.tsv` | one normalized row per array task or worker job |
| `time-profile.tsv` | timestamped active/finished-job series |
| `time-profile.svg` | concurrency and cumulative-finished-job profile |

The essential aggregate metrics are:

- submission-to-last-end and first-start-to-last-end wall time;
- task state and exit-code counts, including missing expected jobs;
- partition, account, QOS, requested memory, allocated CPUs, and node placement;
- duration and queue-wait minimum, mean, p50, p95, and maximum;
- mean and peak concurrency, plus their fractions of the configured target;
- successful jobs per hour;
- `MaxRSS` p50, p95, and maximum;
- average and maximum disk read/write accounting per logical job, with p50,
  p95, and maximum summaries;
- aggregate CPU efficiency, calculated as total CPU time divided by allocated
  CPUs times elapsed time;
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
