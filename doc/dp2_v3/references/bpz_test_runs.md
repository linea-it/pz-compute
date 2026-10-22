# BPZ test run record

This note records operational evidence for the standalone, non-production
`bpz_test` workflow. Its scientific limitations remain defined in
[`bpz_test_science.md`](bpz_test_science.md). Measurements here must not be
used to size or validate the official 136-template BPZ workflow.

## 2026-10-22 secondary-catalog Stage 2 pilot

Slurm array job `217091` ran BPZ test over the five largest shards selected
from the partitioned secondary Object catalog. It used five concurrent tasks,
two allocated logical CPUs, 40 GiB, and the provisional 24-hour limit per
task. All five tasks completed with exit code `0:0`.

| task | elapsed | total CPU | maximum RSS |
|---|---:|---:|---:|
| `217091_0` | 53 min 31 s | 53 min 08.663 s | 10.04 GiB |
| `217091_1` | 52 min 32 s | 52 min 09.747 s | 10.14 GiB |
| `217091_2` | 49 min 49 s | 49 min 27.710 s | 20.29 GiB |
| `217091_3` | 50 min 49 s | 50 min 28.340 s | 20.53 GiB |
| `217091_4` | 49 min 47 s | 49 min 25.436 s | 18.36 GiB |

Aggregate CPU time was 15,279.896 seconds over 15,388 elapsed task-seconds,
or 0.993 logical CPU used per running task. Slurm allocated two logical CPUs
because Apollo schedules a whole physical core. More CPUs per task are not
supported by this evidence; throughput should come from independent array
tasks.

The 20.53 GiB maximum supports a homogeneous 28 GiB request, leaving 7.47 GiB
or approximately 36% above the observed peak. The two-hour limit is more than
twice the 53-minute-31-second maximum on the five largest files.

## Stage 2 capacity calculation

The production `cpu_photoz` allocation exposes 25 Apollo nodes and excludes
`apl26-28`:

- 16 nodes `apl01-16`, each with 56 effective CPUs, `RealMemory=124080 MiB`,
  and `MemSpecLimit=4096 MiB`;
- 9 nodes `apl17-25`, each with 104 effective CPUs, `RealMemory=253132 MiB`,
  and `MemSpecLimit=4096 MiB`.

With a 28 GiB request (`28672 MiB`), memory remains the limiting resource:

```text
apl01-16: floor((124080 - 4096) / 28672) = 4 tasks/node
apl17-25: floor((253132 - 4096) / 28672) = 8 tasks/node

theoretical capacity = 16 * 4 + 9 * 8 = 136 tasks
round(0.95 * 136) = 129 concurrent tasks
```

At full concurrency Slurm allocates 258 logical CPUs, about 14% of the 1,832
available on `apl01-25`. The 129-task throttle therefore targets approximately
95% of the discrete per-node memory capacity while retaining a 5% scheduling
margin. It does not claim that BPZ test uses 95% of aggregate CPU capacity.

The v3 defaults derived from this pilot are consequently:

```text
maximum concurrency: 129 tasks
memory per task:      28 GiB
walltime per task:    02:00:00
```

A production-sized BPZ test run must still record its job ID, success count,
runtime distribution, memory distribution, output validation, and storage use
before these values are treated as established beyond the pilot.
