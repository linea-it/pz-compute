# Apollo capacity and photo-z resource utilization

**Status as of October 23, 2026**

This resource-focused analysis complements the broader
[Photo-z Processing Report: DP1 and DP2](photoz_execution_report_2026-10-22.md),
which documents the scientific products, inputs, execution outcomes, and
remaining BPZ work.

## Executive answer

The largest successful photo-z production used **all 25 Apollo nodes available to the `hpc-photoz` account in the `cpu_photoz` partition**. It did not use all 28 physical nodes advertised for Apollo because `apl26-28` were reserved for Jupyter and other LIneA pipelines and were outside the production node set.

It also did not attempt to keep every CPU thread or every byte of RAM busy. This was a deliberate consequence of matching the allocation to the workload:

- Stage 2 runs one estimator process per input Parquet shard. FlexZBoost used about one logical CPU per active task, while the observed per-task memory had a 2.67 GiB median and a 33.85 GiB maximum. A uniform 40 GiB envelope was required to accommodate the largest shards safely. The current command exposes no corresponding intra-shard scaling simply by requesting more CPUs; that would require a measured RAIL/pz-compute implementation change.
- The 25 nodes can accommodate 86 whole 40 GiB task slots. The production cap of 82 tasks occupied **95.35% of those discrete slots**, leaving four slots as operational headroom. Because memory must fit on individual nodes, this is not the same as allocating 95% of all RAM bytes: 82 tasks reserved 3.20 TiB, or 80.7% of Slurm-schedulable memory.
- Stage 3 also used 82 simultaneous Dask workers and all 25 nodes. Each worker needed close to its 40 GiB limit. The measured CPU efficiency is consistent with a mixed workload containing computation, reading, serialization, writing, scheduler coordination, and barriers, rather than a continuously CPU-bound calculation.
- Stage 1 was conservatively overprovisioned. Its successful DP2 job allocated 98 logical CPUs and 231 GiB but averaged about 7.1 CPUs and reached 15.33 GiB. This allocation should be reduced after a controlled scaling benchmark.

The defensible conclusion is therefore not that the workflow used “the entire cluster” in every dimension. It used the **entire eligible node set**, nearly all safe memory-sized task slots in the distributed stages, and only the CPU parallelism that the current applications could exploit. The measurements below make both the effective use and the remaining optimization opportunity explicit.

## 1. Three different meanings of cluster capacity

### 1.1 Published Apollo capacity

The [LIneA Apollo documentation](https://docs.linea.org.br/processamento/apollo/index.html) describes:

- 28 compute nodes;
- 1,072 physical cores;
- 2,144 logical CPUs with Hyper-Threading enabled;
- 16 `XL170r` nodes (`apl01-16`) with 56 logical CPUs and 128 GB RAM each;
- 12 `XL220n` nodes (`apl17-28`) with 104 logical CPUs and 256 GB RAM each.

Summing the per-node RAM figures gives 5.12 TB decimal. The consolidated table on the same page instead reports 1.5 TB plus 3 TB and mixes values that appear to represent logical CPUs in its first hardware row and physical cores in its second. For that reason, this report uses the headline CPU totals for nominal capacity and the values returned by Slurm for operational memory calculations.

### 1.2 Capacity eligible for photo-z production

The public documentation lists the standard Apollo partitions on `apl01-25` and says that `apl26-28` are reserved for Jupyter and other LIneA pipelines. The production-specific `cpu_photoz` partition exposed the same 25-node topology to `hpc-photoz` during these runs.

| Resource | Nominal Apollo | Eligible in `cpu_photoz` | Eligible fraction |
|---|---:|---:|---:|
| Nodes | 28 | 25 (`apl01-25`) | 89.3% |
| Physical cores | 1,072 | 916 | 85.4% |
| Logical CPUs | 2,144 | 1,832 | 85.4% |
| Slurm `RealMemory` | 4.790 TiB across 28 nodes | 4.066 TiB across 25 nodes | 84.9% |
| Memory schedulable to jobs after `MemSpecLimit` | Not used as a nominal published metric | 3.968 TiB across 25 nodes | — |

The operational values came from the Slurm topology inspected during the October 2026 production setup:

| Node group | Nodes | Logical CPUs/node | `RealMemory`/node | Reserved by Slurm/node | Schedulable memory/node |
|---|---:|---:|---:|---:|---:|
| `apl01-16` | 16 | 56 | 124,080 MiB | 4,096 MiB | 119,984 MiB |
| `apl17-25` | 9 | 104 | 253,132 MiB | 4,096 MiB | 249,036 MiB |
| **Total** | **25** | **1,832** | **4,263,468 MiB** | **102,400 MiB** | **4,161,068 MiB (3.968 TiB)** |

“Eligible” means that Slurm could place photo-z jobs on these nodes; it does not imply that the resources are always free from other jobs. In the successful DP2 production, however, the accounting records show work on all 25 eligible nodes in both distributed stages.

It is also distinct from Linux `FreeMem`, which is an instantaneous operating-system value and is not the capacity Slurm promises to a job. The relevant planning quantities are the partition's eligible nodes, Slurm `RealMemory`, system reservation, current allocations, and each job's requested TRES.

### 1.3 Discrete capacity for 40 GiB jobs

Slurm places each job on one node, so unused memory on different nodes cannot be pooled. With a 40 GiB request:

```text
apl01-16: floor(119984 MiB / 40960 MiB) = 2 jobs/node
apl17-25: floor(249036 MiB / 40960 MiB) = 6 jobs/node
cluster:  16 * 2 + 9 * 6 = 86 simultaneous jobs
production cap: round(0.95 * 86) = 82 jobs
```

The cap therefore used 82/86, or **95.35% of the discrete task capacity**. At its peak it reserved 3,280 GiB (3.203 TiB), equal to **80.7% of the 3.968 TiB schedulable memory**. Of the remaining 783.5 GiB, 160 GiB corresponds to the four intentionally unused slots and approximately 623.5 GiB is node-local fragmentation that cannot hold another complete 40 GiB task. On every small node, for example, two tasks leave about 37.2 GiB free—substantial RAM, but less than one safe task allocation.

## 2. Resources used by successful runs

This section covers the completed DP1 and DP2 FlexZBoost products retained in the successful-execution archive. DNF and BPZ Test pilots are useful for algorithm-specific sizing, but they are not counted as completed catalog production. Failed, out-of-memory, storage-limited, and operator-cancelled production attempts are likewise excluded from utilization totals.

### 2.1 DP2 FlexZBoost: the representative production run

DP2 is the best measurement of production-scale behavior. It processed 786,420,720 objects, all 2,174 Stage 2 tasks completed, and the final Stage 3 product passed its completion checks.

| Stage | Nodes reached | Peak allocation | Measured CPU use | Measured memory use | Elapsed |
|---|---:|---:|---:|---:|---:|
| Stage 1: train, job `212626` | 1 | 98 logical CPUs; 231 GiB | 1,109.9 CPU-s; 7.1 average CPUs; 7.2% allocation efficiency | 15.33 GiB peak RSS | 2 min 37 s |
| Stage 2: estimate, array `214803` | 25 | 82 tasks; 164 logical CPUs; up to 3.203 TiB reserved | 685,498.5 CPU-s (190.42 CPU-h); 85.6 average CPUs; 55.9% allocation efficiency | Per-task RSS: 2.67 GiB median, 16.75 GiB p95, 33.85 GiB maximum | 2 h 13 min 25 s |
| Stage 3: build HATS, workers `216977-217058` | 25 | 82 workers; 656 logical CPUs; up to 3.203 TiB reserved | 68,384.5 CPU-s (19.00 CPU-h); 142.8 average CPUs; 21.8% allocation efficiency | Per-worker RSS: 26.55 GiB median, 37.39 GiB p95, 37.99 GiB maximum | 8 min 36 s driver wall time |

Across the three measured DP2 stages, Slurm recorded **approximately 209.72 CPU-hours used** against 432.38 allocated CPU-hours. This aggregate is dominated by Stage 2. It should not be interpreted as a simultaneous percentage of the cluster because the stages ran at different times and with different job shapes.

CPU use as a fraction of the 1,832 logical CPUs eligible for photo-z was:

| Stage | Peak CPUs allocated | Average CPUs allocated | Average CPUs actually used |
|---|---:|---:|---:|
| Stage 1 | 98 (5.35%) | 98 (5.35%) | 7.1 (0.39%) |
| Stage 2 | 164 (8.95%) | 153.3 (8.37%) | 85.6 (4.67%) |
| Stage 3 | 656 (35.81%) | 655.8 (35.80%) | 142.8 (7.79%) |

The Stage 3 workers appear as `CANCELLED` in Slurm because Dask terminated the temporary workers after the driver finished. The driver returned zero, logged completion, and the final catalog contains the expected 786,420,720 objects; this is therefore treated as a successful production run, not an application failure.

### 2.2 What “actual memory used” can and cannot mean here

Slurm retained `MaxRSS` for each task or worker, not a time-aligned cluster-wide RSS series. Consequently:

- the per-job median, p95, and maximum above are measured values;
- the 3.203 TiB figure is peak **reserved capacity**, not measured resident memory;
- summing every job's `MaxRSS` would combine peaks that may have occurred at different times and is not a valid instantaneous total;
- an exact cluster-wide peak of resident memory cannot be reconstructed from the retained accounting.

For Stage 3, where all 82 workers overlapped for almost the entire worker interval, the sum of individual worker peaks is 2.207 TiB, or 55.6% of schedulable cluster memory. This is a conservative upper bound obtained by summing per-worker maxima that need not have occurred simultaneously; it is not a measured cluster-wide peak. No equivalent estimate is defensible for Stage 2 because 2,174 tasks ran in successive waves and their individual peaks were not synchronized.

### 2.3 DP1 FlexZBoost

DP1 was much smaller and is less representative of full-cluster behavior:

| Stage | Allocation or concurrency | Measured use | Elapsed |
|---|---:|---:|---:|
| Stage 1: train, job `217102` | 16 logical CPUs; 32 GiB | 331.9 CPU-s; 3.42 average CPUs; 2.47 GiB peak RSS | 1 min 37 s |
| Stage 2: estimate, array `217103` | 29 tasks; 40 GiB/task | CPU and RSS accounting was not retained | 3 min 30 s overall |
| Stage 3: build HATS | 16 workers configured; 8 CPUs and 40 GiB/worker | Only driver CPU time was retained; worker CPU/RSS totals are unavailable | 40 s driver wall time |

These gaps are reported as unavailable instead of being filled with assumptions. DP1 established functional correctness and reproducibility; DP2 supplies the credible utilization baseline.

## 3. Why every CPU and every byte of memory were not used

### Stage 2: one process per shard and a memory-limited packing problem

The Stage 2 array exposes parallelism across Parquet shards. Inside each task, `rail-estimate` executes one estimator process. Slurm accounted two logical CPUs per task, while production consumed an average of 1.12 logical CPUs per active task. Requesting four, eight, or more CPUs for the same process would increase the allocation but has no demonstrated mechanism to reduce runtime.

Memory, rather than CPU count, determined how many tasks could safely coexist. The production maximum of 33.85 GiB validates a 40 GiB envelope for the largest observed shard, but the 2.67 GiB median shows that a single homogeneous request over-reserves most shards. Slurm arrays cannot change the memory request independently for each task, so the safe uniform request traded packing efficiency for avoiding out-of-memory failures.

This explains the apparently paradoxical result: all 25 nodes were active and 95.35% of the safe task slots were occupied, while only 8.95% of logical CPUs were allocated at peak. The workflow was memory-shaped and process-limited, not CPU-capacity-limited.

### Stage 3: memory-heavy workers and non-CPU phases

Stage 3 ran one Dask process per worker with eight allocated CPUs and 40 GiB. The p95 and maximum RSS values of 37.39 and 37.99 GiB show that the memory reservation was tight and justified. The workers nevertheless averaged about 1.74 logical CPUs of actual CPU time each.

The available evidence is consistent with a mixed workload: reading HDF5 and catalog Parquet, transforming data, serializing partitions, writing HATS/Parquet, coordinating through the Dask scheduler, and waiting at phase boundaries. This interpretation is an inference from the workload and accounting, not a direct phase-by-phase profiler result. Increasing CPU allocation per worker would not address these waits, while adding more 40 GiB workers was constrained by per-node memory placement.

### Stage 1: conservative first-production sizing

Unlike the distributed stages, Stage 1 was plainly oversized. The DP2 training process used only 7.2% of allocated CPU time and 15.33 GiB of a 231 GiB reservation. This shape was a conservative full-node allocation used for the first controlled production, not an optimized endpoint. Its short duration limited the operational cost, but future runs should request substantially less after verifying runtime and reproducibility at smaller CPU counts.

### Storage was an independent production limit

An earlier Stage 2 attempt stopped because its scratch quota was exhausted. The complete HDF5 estimate set required approximately 3.45 TiB, and the workflow required an 8 TiB usable allocation once PDFs, HATS products, staging, and margin were included. More CPU concurrency would have increased the output rate without solving this capacity constraint. Apollo's [storage documentation](https://docs.linea.org.br/armazenamento/index.html) also emphasizes that `/scratch` is temporary, unbacked Lustre storage and that large metadata workloads and many files require care.

## 4. Improvements for future production

The current configuration was safe and completed production, but it is not the final efficiency ceiling. The following changes should be prioritized:

1. **Create memory classes for Stage 2.** Predict memory from shard size or row count, then submit small, medium, and large arrays with separate `--mem` and concurrency limits. This directly attacks the difference between the 2.67 GiB median and 33.85 GiB maximum.
2. **Benchmark CPU scaling before increasing CPU requests.** Run the same large shards with 1, 2, 4, and 8 physical cores for each algorithm. Keep additional CPUs only when elapsed time shows useful speedup.
3. **Expose controlled intra-shard parallelism.** If RAIL estimators can process independent chunks safely, add bounded multiprocessing or estimator-native threading. Without this software change, allocating more CPUs per Stage 2 task is mostly cosmetic.
4. **Split unusually large shards or lower internal chunk sizes.** Reducing peak memory would permit more workers per node and reduce the homogeneous 40 GiB penalty.
5. **Retune Stage 3 worker shape.** Compare 2, 4, and 8 CPUs per worker at fixed memory, and compare one versus multiple worker processes per node. Measure total wall time, CPU efficiency, scheduler overhead, and Lustre behavior together.
6. **Reduce Stage 1 conservatively.** Repeat training with smaller memory and CPU allocations while checking model equivalence and wall time. The current DP2 measurements leave substantial room.
7. **Collect time-aligned node telemetry.** Add lightweight periodic cgroup or `sstat` sampling for aggregate RSS and CPU. `sacct MaxRSS` alone cannot answer the exact cluster-wide peak-memory question.
8. **Archive a topology snapshot with each production.** Retain `sinfo`, `scontrol show partition`, and relevant `scontrol show node` output so future reports distinguish advertised, eligible, free, allocated, and used resources without relying on operator transcripts.
9. **Keep algorithm-specific sizing.** FlexZBoost, DNF, BPZ, and HATS construction have different CPU and memory behavior. A single cluster-wide job shape should not be treated as an efficiency target.

## 5. Recommended concise response to management

> Apollo has 28 nodes, but 25 nodes were available to the photo-z production account; the other three were assigned to Jupyter and LIneA pipelines. The DP2 production used all 25 eligible nodes. We ran 82 simultaneous jobs, which is 95.35% of the safe 40 GiB job slots that fit on those nodes. We did not allocate all CPU threads because the estimator currently runs one process per catalog shard and is constrained first by per-task memory, not by CPU availability. We also did not attempt to fill every RAM byte because memory is allocated in whole per-node job slots and shard memory varies from 2.67 GiB at the median to 33.85 GiB at the maximum. Stage 3 similarly needed close to 40 GiB per worker but included I/O and coordination phases that do not saturate CPUs. The run completed all 786.42 million objects successfully; the next efficiency gains are memory-classed arrays, CPU-scaling benchmarks, smaller chunks, and better time-aligned telemetry.

## 6. Evidence and calculation notes

Primary local evidence:

- DP1 and DP2 Slurm summaries under `not-tracked/pz-compute-succesful-execution-logs/`;
- Stage 2 task-level accounting for array `214803`;
- Stage 3 task-level accounting for workers `216977-217058` and the successful driver log;
- the operational chronology in `work_summary.txt`;
- the resource derivations retained in `doc/dp2_v2/`.

Public references:

- [LIneA Apollo cluster documentation](https://docs.linea.org.br/processamento/apollo/index.html), accessed October 23, 2026;
- [LIneA storage documentation](https://docs.linea.org.br/armazenamento/index.html), accessed October 23, 2026.

Unit conventions: Slurm memory values reported in MiB were converted using 1 GiB = 1,024 MiB and 1 TiB = 1,024 GiB. CPU utilization uses `TotalCPU / (elapsed time * allocated logical CPUs)`. Average CPUs actually used equal aggregate `TotalCPU / stage wall time`; this is CPU-time consumption, not a count of continuously busy physical cores.

The eligible topology should be captured again before each production because partitions and reservations can change:

```bash
sinfo -p cpu_photoz -N -o '%N %t CPUs=%c MemoryMB=%m FreeMB=%e'
scontrol show partition cpu_photoz
scontrol show node 'apl[01-25]'
```
