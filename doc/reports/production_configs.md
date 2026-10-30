# Photo-z requested resource configuration history

This document is the chronological record of cluster and Slurm resources
requested for production rounds. It records configuration, not measured
utilization; observed queueing, runtime, and resource use belong in the
execution and utilization reports. Where an older value was not retained, it
is explicitly marked as such.

On Apollo, one requested CPU can be accounted as two allocated logical CPUs
because Slurm schedules complete physical cores (`CR_CORE_MEMORY`).

## Production round — 2026-10-22

This round covers the DP1/DP2 FlexZBoost production completed around October 22
and the first DP2 v3 algorithm pilots and retries recorded on that date.

### Cluster allocation

| Setting | Value |
|---|---|
| Primary Slurm partition | `cpu_photoz` |
| Primary Slurm account | `hpc-photoz` |
| QoS | not retained |
| Eligible nodes | `apl01-25` |
| Explicitly excluded nodes | `apl26-28` |
| Logical CPUs | 1,832 |
| Slurm `RealMemory` | 4,263,468 MiB |
| Per-node system memory reservation | 4,096 MiB |
| Schedulable memory | 4,161,068 MiB (3.968 TiB) |
| Placement | `select/cons_tres`, `CR_CORE_MEMORY`, no oversubscription |

| Nodes | Logical CPUs/node | `RealMemory`/node | Schedulable memory/node |
|---|---:|---:|---:|
| `apl01-16` | 56 | 124,080 MiB | 119,984 MiB |
| `apl17-25` | 104 | 253,132 MiB | 249,036 MiB |

At 40 GiB per task or worker, the nominal discrete capacity was 86 simultaneous
allocations. The 82-task production ceiling represented 95.35% of that
capacity.

### Stage 1: training requests

| Workload | Partition / account | CPUs/job | Memory/job | Wall time | Node scope |
|---|---|---:|---:|---:|---|
| DP1 FlexZBoost production | `cpu_photoz` / `hpc-photoz` | 16 | 32 GiB | 03:00:00 | `apl01-25` |
| DP2 FlexZBoost production | `cpu_photoz` / `hpc-photoz` | 98 | 231 GiB | 03:00:00 | one node in `apl17-25` |

### Stage 2: estimation requests

Each array task processed one input Parquet shard.

| Workload | Run/job | Partition / account | Array tasks | Concurrency ceiling | CPUs/task requested → allocated/expected | Memory/task | Wall time/task |
|---|---|---|---:|---:|---:|---:|---:|
| DP1 FlexZBoost production | retained production run | `cpu_photoz` / `hpc-photoz` | 29 | 100 configured; 29 effective | 1 → 2 | 40 GiB | 12:00:00 |
| DP2 FlexZBoost production | `214803` | `cpu_photoz` / `hpc-photoz` | 2,174 | 82 | 1 → 2 | 40 GiB | 12:00:00 |
| DP2 v3 FlexZBoost pilot | `217085` | `cpu_pipelines` / `hpc-pipelines` | not retained | 5 | 1 → 2 | 40 GiB | 12:00:00 |
| DP2 v3 DNF pilot | `217097` | `cpu_photoz` / `hpc-photoz` | not retained | 5 | 1 → 2 | 40 GiB | 24:00:00 |
| DP2 v3 BPZ test pilot | `217091` | `cpu_photoz` / `hpc-photoz` | not retained | 5 | 1 → 2 | 40 GiB | 24:00:00 |
| DP2 v3 BPZ full attempt | `217148` | `cpu_photoz` / `hpc-photoz` | full catalog | not retained | 1 → 2 | 24 GiB | not retained |
| DP2 v3 BPZ retry | `217765` | `cpu_photoz` / `hpc-photoz` | incomplete | not retained | 1 → 2 | 26 GiB | not retained |
| DP2 v3 BPZ third attempt | job ID not retained; cancelled | `cpu_photoz` / `hpc-photoz` | full catalog | 105 | 1 → 2 | 32 GiB | 02:00:00 |

The BPZ attempts document the requested-resource progression that followed the
24 GiB and 26 GiB out-of-memory failures. BPZ test is an engineering workflow,
not an official production product.

### Stage 3: HATS requests

| Workload | Driver placement/request | Worker CPUs | Worker memory | Worker wall time | Worker policy | Scale-down delay |
|---|---|---:|---:|---:|---|---:|
| DP1 FlexZBoost | login process on `loginapl01`; no Slurm driver allocation | 8 | 40 GiB | 12:00:00 | 16 fixed workers | 180 s |
| DP2 FlexZBoost | login process; no retained Slurm driver allocation | 8 | 40 GiB | 12:00:00 | 82 fixed workers | 180 s |

### Storage preflight

| Setting | Value |
|---|---|
| Filesystem | shared Lustre `/scratch` |
| Project allocation during production | temporarily increased from 1 TiB to 10 TiB |
| Approximate usable capacity recorded for the round | 8 TiB |
| Operational requirement | reserve approximately 8 TiB for one full DP2 workflow |
| Inode snapshot | not retained |

## Production round — 2026-10-30

This is the configuration prepared for DP2 v3 individual production, with one
algorithm run at a time on a cluster that may be shared with other users.

### Cluster allocation

| Setting | Value |
|---|---|
| Primary Slurm partition | `cpu_photoz` |
| Primary Slurm account | `hpc-photoz` |
| QoS | `photoz` |
| Eligible nodes | `apl01-26` |
| Explicitly excluded nodes | `apl27-28` |
| Logical CPUs | 1,936 |
| Slurm `RealMemory` | 4,516,600 MiB |
| Per-node system memory reservation | 4,096 MiB |
| Schedulable memory | 4,410,104 MiB (4.206 TiB) |
| Placement | `select/cons_tres`, `CR_CORE_MEMORY`, no oversubscription |

| Nodes | Logical CPUs/node | `RealMemory`/node | Schedulable memory/node |
|---|---:|---:|---:|
| `apl01-16` | 56 | 124,080 MiB | 119,984 MiB |
| `apl17-26` | 104 | 253,132 MiB | 249,036 MiB |

At 40 GiB per task or worker, the nominal discrete capacity is 92 simultaneous
allocations. Stage 2 keeps an 82-task ceiling and Stage 3 an 80-worker ceiling
so existing jobs on the shared nodes can coexist and queued work can start as
capacity becomes available.

### Stage 1: training requests

| Workload | Partition / account | CPUs/job | Memory/job | Wall time | Node scope |
|---|---|---:|---:|---:|---|
| FlexZBoost | `cpu_photoz` / `hpc-photoz` | 98 | 231 GiB | 03:00:00 | one node in `apl17-26` |
| BPZ | `cpu_photoz` / `hpc-photoz` | 1 | 8 GiB | 01:00:00 | `apl01-26` |
| DNF | `cpu_photoz` / `hpc-photoz` | 1 | 8 GiB | 01:00:00 | `apl01-26` |
| BPZ test | `cpu_photoz` / `hpc-photoz` | 1 | 8 GiB | 01:00:00 | `apl01-26` |

### Stage 2: estimation requests

Each array task processes one input Parquet shard.

| Workload | Run/job | Partition / account | Array tasks | Concurrency ceiling | CPUs/task requested → allocated/expected | Memory/task | Wall time/task |
|---|---|---|---:|---:|---:|---:|---:|
| FlexZBoost | next individual production | `cpu_photoz` / `hpc-photoz` | input-dependent | 82 | 1 → 2 | 40 GiB | 01:00:00 |
| DNF | next individual production | `cpu_photoz` / `hpc-photoz` | input-dependent | 82 | 1 → 2 | 40 GiB | 02:00:00 |
| BPZ | next individual production | `cpu_photoz` / `hpc-photoz` | input-dependent | 20 | 1 → 2 | 40 GiB | 24:00:00 |
| BPZ test | next engineering run | `cpu_photoz` / `hpc-photoz` | input-dependent | 105 | 1 → 2 | 32 GiB | 02:00:00 |

BPZ test remains an engineering workflow and is not an official production
product. Only one algorithm is intended to run through production at a time.

### Stage 3: HATS requests

| Workload | Driver placement/request | Worker CPUs | Worker memory | Worker wall time | Worker policy | Scale-down delay |
|---|---|---:|---:|---:|---|---:|
| Each individual algorithm | Slurm driver: 2 CPUs, 8 GiB, 2 days | 8 | 40 GiB | 12:00:00 | adaptive, minimum 20 and maximum 80 | 180 s, configurable |

The adaptive floor is 25% of the maximum. `PZ_HATS_MIN_WORKERS`,
`PZ_HATS_MAX_WORKERS`, and `PZ_HATS_SCALE_DOWN_DELAY` can override these values
per submission.

### Storage preflight

| Setting | Value |
|---|---|
| DP2 v3 root | `/scratch/users/app.photoz/pz-compute-runs/dp2-v3` |
| Filesystem | shared Lustre `/scratch`, 40 TiB total |
| Space snapshot | 4.4 TiB used; 36 TiB available; 11% used |
| Inode snapshot | 283,000 of 9.6 million used; 3% used |
| User usage/quota | `app.photoz`: 4.321 TiB used; no explicit hard quota |
| Group usage/quota | `photoz`: 4.547 TiB used; default settings, no explicit hard quota |
| Operational rule | recheck space and inodes before every stage because storage is shared and time-varying |

## Evidence

The October 22 entries were reconstructed from the retained launchers and the
following reports:

- [`photoz_execution_report_2026-10-22.md`](photoz_execution_report_2026-10-22.md)
- [`apollo_resource_utilization_2026-10-23.md`](apollo_resource_utilization_2026-10-23.md)
- [`dp2_v3/references/fzboost_runs.md`](../dp2_v3/references/fzboost_runs.md)
- [`dp2_v3/references/dnf_runs.md`](../dp2_v3/references/dnf_runs.md)
- [`dp2_v3/references/bpz_test_runs.md`](../dp2_v3/references/bpz_test_runs.md)
- [`work_summary.txt`](../../work_summary.txt)

The October 30 entries reflect the current DP2 v3 launchers plus the cluster
and Lustre snapshots collected as `app.photoz`. Scientific parameters remain
under [`doc/dp2_v3/config/`](../dp2_v3/config/); this history is limited to
requested execution resources.
