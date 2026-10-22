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

The 20.53 GiB maximum supports a homogeneous 26 GiB trial request, leaving
5.47 GiB or approximately 26.6% above the observed pilot peak. The two-hour
limit is more than twice the 53-minute-31-second maximum on the five largest
files.

## 2026-10-22 full-catalog 24 GiB attempt

Full-catalog array job `217148` showed that the earlier 24 GiB request was not
sufficient outside the five-file pilot. The retained error-log scan identifies
at least 15 array tasks terminated by Slurm with an `oom_kill` event. Because a
killed process cannot report the memory it would have required to finish, this
evidence rejects 24 GiB but does not prove that 26 GiB is sufficient.

The new 26 GiB value is therefore a retry setting derived from the requested
25--30% pilot margin, not a completed-production measurement. The failed tasks
must finish and the final accounting and HDF5 validation must pass before this
request is considered validated.

## Stage 2 capacity calculation

The production `cpu_photoz` allocation exposes 25 Apollo nodes and excludes
`apl26-28`:

- 16 nodes `apl01-16`, each with 56 effective CPUs, `RealMemory=124080 MiB`,
  and `MemSpecLimit=4096 MiB`;
- 9 nodes `apl17-25`, each with 104 effective CPUs, `RealMemory=253132 MiB`,
  and `MemSpecLimit=4096 MiB`.

With a 26 GiB request (`26624 MiB`), memory remains the limiting resource:

```text
apl01-16: floor((124080 - 4096) / 26624) = 4 tasks/node
apl17-25: floor((253132 - 4096) / 26624) = 9 tasks/node

theoretical capacity = 16 * 4 + 9 * 9 = 145 tasks
round(0.95 * 145) = 138 concurrent tasks
```

At full concurrency Slurm allocates 276 logical CPUs, about 15% of the 1,832
available on `apl01-25`. The 138-task throttle therefore targets approximately
95% of the discrete per-node memory capacity while retaining a 5% scheduling
margin. It does not claim that BPZ test uses 95% of aggregate CPU capacity.

The current v3 retry settings are consequently:

```text
maximum concurrency: 138 tasks
memory per task:      26 GiB (provisional retry value)
walltime per task:    02:00:00
```

A production-sized BPZ test run must still record its job ID, success count,
runtime distribution, memory distribution, output validation, and storage use
before these values are treated as established beyond the pilot.
