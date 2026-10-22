# DNF run record for DP2

This note records operational evidence for the official six-band DNF workflow.
The scientific model and estimator choices are documented separately in
[`dnf_science.md`](dnf_science.md).

## 2026-10-22 secondary-catalog Stage 2 pilot

Slurm array job `217097` ran DNF over the five largest shards selected from the
partitioned secondary Object catalog. It used five concurrent tasks, two
allocated logical CPUs, 40 GiB, and the provisional 24-hour limit per task.
All five tasks completed with exit code `0:0`.

| task | elapsed | total CPU | maximum RSS |
|---|---:|---:|---:|
| `217097_0` | 56 min 26 s | 56 min 07.635 s | 19.44 GiB |
| `217097_1` | 51 min 13 s | 50 min 57.482 s | 28.57 GiB |
| `217097_2` | 40 min 58 s | 40 min 42.815 s | 14.82 GiB |
| `217097_3` | 47 min 27 s | 47 min 11.630 s | 19.36 GiB |
| `217097_4` | 40 min 22 s | 40 min 06.161 s | 18.12 GiB |

Aggregate CPU time was 14,105.723 seconds over 14,186 elapsed task-seconds,
or 0.994 logical CPU used per running task. Slurm allocated two logical CPUs
because Apollo schedules a whole physical core. This pilot does not support
requesting more CPUs per task; throughput should come from independent array
tasks.

The 28.57 GiB maximum supports a homogeneous 34 GiB request, leaving 5.43 GiB
or approximately 19.0% above the observed peak. The two-hour walltime is kept
separate from that memory-margin policy and provides operational tolerance
over the 56-minute-26-second pilot maximum.

## Stage 2 capacity calculation

The production `cpu_photoz` allocation exposes 25 Apollo nodes and excludes
`apl26-28`:

- 16 nodes `apl01-16`, each with 56 effective CPUs, `RealMemory=124080 MiB`,
  and `MemSpecLimit=4096 MiB`;
- 9 nodes `apl17-25`, each with 104 effective CPUs, `RealMemory=253132 MiB`,
  and `MemSpecLimit=4096 MiB`.

With a 34 GiB request (`34816 MiB`), memory remains the limiting resource:

```text
apl01-16: floor((124080 - 4096) / 34816) = 3 tasks/node
apl17-25: floor((253132 - 4096) / 34816) = 7 tasks/node

theoretical capacity = 16 * 3 + 9 * 7 = 111 tasks
round(0.95 * 111) = 105 concurrent tasks
```

At full concurrency Slurm allocates 210 logical CPUs, about 11% of the 1,832
available on `apl01-25`. The 105-task throttle targets approximately 95% of
the discrete per-node memory capacity while retaining a 5% scheduling margin;
it does not claim 95% aggregate CPU use.

The v3 defaults derived from this pilot are:

```text
maximum concurrency: 105 tasks
memory per task:      34 GiB
walltime per task:    02:00:00
```

A full DNF run must still record its job ID, success count, runtime and memory
distributions, output validation, and storage use before these values are
treated as production evidence beyond the pilot.
