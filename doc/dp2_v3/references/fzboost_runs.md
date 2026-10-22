# FlexZBoost run record for DP2

This note records technical run evidence and resource rationale only. The
scientific model choices are documented in
[`fzboost_science.md`](fzboost_science.md). Current commands and directory
layout live under `../individual/`, `../batch/`, and `../scripts/`.

## Status and evidence boundary

FlexZBoost has an established DP2 production workflow, and the v3 launchers
carry its validated shape forward. The detailed legacy command recipes remain
in:

- [`doc/dp2_v2/dp2_stage1_train_instructions_clipped.md`](../../dp2_v2/dp2_stage1_train_instructions_clipped.md);
- [`doc/dp2_v2/dp2_stage2_estimate_instructions_clipped.md`](../../dp2_v2/dp2_stage2_estimate_instructions_clipped.md);
- [`doc/dp2_v2/dp2_stage3_build_hats.md`](../../dp2_v2/dp2_stage3_build_hats.md).

Those recipes are not copied into v3. The v3 scripts change orchestration and
artifact organization; they do not constitute a new completed production run.
When v3 is executed, append the job IDs, environment freeze, benchmark summary,
input/output counts, and validation result here.

## 2026-10-22 secondary-catalog Stage 2 pilot

Slurm array job `217085` ran FlexZBoost over the five largest shards selected
from the partitioned secondary Object catalog. It used account
`hpc-pipelines`, partition `cpu_pipelines`, five concurrent tasks, two logical
CPUs and 40 GiB per task, and a 12-hour pilot limit. All five tasks completed
with exit code `0:0`.

| task | elapsed | maximum RSS | total CPU |
|---|---:|---:|---:|
| `217085_0` | 12 min 09 s | 29.09 GiB | 13 min 32.770 s |
| `217085_1` | 12 min 01 s | 5.28 GiB | 13 min 24.141 s |
| `217085_2` | 11 min 31 s | 4.94 GiB | 12 min 47.537 s |
| `217085_3` | 11 min 38 s | 28.52 GiB | 12 min 58.547 s |
| `217085_4` | 11 min 42 s | 21.99 GiB | 13 min 02.286 s |

Elapsed time ranged from 11 min 31 s to 12 min 09 s, with a median of
11 min 42 s. Maximum RSS ranged from 4.94 to 29.09 GiB, with a median of
21.99 GiB. Aggregate CPU efficiency was approximately 55.7% relative to the
two allocated logical CPUs per task.

The measured 29.09 GiB peak supports a homogeneous 37 GiB memory request,
leaving 7.91 GiB or approximately 27.2% above the observed maximum. The Stage
2 FlexZBoost task limit is reduced from the 12-hour pilot request to one hour,
which leaves nearly five times the observed maximum runtime. The capacity
calculation below raises the canonical throttle to 97 tasks on the
`cpu_photoz` production partition. Long-lived Stage 3 driver and Dask-worker
limits are not changed by this Stage 2 evidence.

## 2026-10-21 FlexZBoost production run

This run used the legacy DP2/FlexZBoost orchestration documented in
`doc/dp2_v2/`. It provides measured evidence for the defaults carried into v3,
but it is not itself a v3 production validation.

The sources for this section are the operator discussion retained from the
LineA Slack thread and the generated `not-tracked/summary_stage1.json`,
`summary_stage2.json`, and `summary_stage3.json` profiler artifacts.
Infrastructure follow-up was assigned to ticket 476. Profiler timestamps are
from Slurm accounting; message timestamps are identified explicitly where they
are still used. The JSON files are local evidence and are not versioned with
this documentation. The exact inputs used for this record can be identified by
their SHA-256 digests:

| profiler artifact | SHA-256 |
|---|---|
| `not-tracked/summary_stage1.json` | `18aba63cfa1550551c17aba8c3ff9f6761c3d79e0759ba56ce700b2768142703` |
| `not-tracked/summary_stage2.json` | `52f9500bed080b0b65af7e931a816689a2702c644516facdefbd42baafbc532e` |
| `not-tracked/summary_stage3.json` | `9aea60a47ba9801bc30d33232bff0b6be37b48b5a0874f011c4845042aebfe09` |

### Stage 1 measured profile

Stage 1 job `212626` ran on `apl24` from 10:05:03 to 10:07:40, completing in
157 seconds with no queue wait. Its measured maximum RSS was 15.335 GiB. CPU
efficiency was 7.21%: 1,109.926 CPU-seconds were used out of 15,386 allocated
CPU-seconds. The job completed successfully, with one expected and one observed
logical job.

This result shows that the 98-CPU, 231-GiB request was highly conservative for
this training run. It validates completion, but a smaller request should be
tested in a future pilot before changing the production default; peak RSS alone
does not describe transient I/O or parallel scaling behavior.

### Stage 2 pilot and resource behavior

The pilot used the five largest Object shards. Peak memory was approximately
20–30 GiB per task, with the largest close to 30 GiB. The production request of
40 GiB per task therefore included roughly 10 GiB of margin over the largest
observed pilot task. The pilot artifacts were removed after validation, so the
individual pilot job IDs and complete `sacct` report are no longer available.

Production used a maximum of 82 concurrent tasks. With the cluster's
whole-core allocation, Slurm allocated two logical CPUs per task, or 164
logical CPUs at full concurrency. That was about 9% of the 1,832 logical CPUs
available on `apl01` through `apl25`. The 82-task cap was determined by the
number of 40 GiB jobs that fit in node memory, not by aggregate CPU capacity.
Consequently, low CPU utilization during Stage 2 was expected.

The fixed 40 GiB request also explains the gap between reserved and consumed
memory: smaller shards used substantially less memory, while every array task
reserved enough for the largest shards. A future optimization could classify
shards by size and submit separate memory classes, but those class boundaries
must be calibrated with retained pilots before changing production behavior.

The successful production summary identifies array job `214803`. All 2,174
expected tasks completed, with no missing or unsuccessful task. Slurm recorded:

| metric | observed value |
|---|---:|
| submission/start | 13:20:22 |
| last task end | 15:33:47 |
| submission to completion | 8,005 s (2 h 13 min 25 s) |
| peak / mean concurrency | 82 / 76.64 |
| mean concurrency relative to target | 93.47% |
| task duration, median / mean | 296 s / 282.21 s |
| task duration, p95 / maximum | 626.4 s / 1,021 s |
| maximum RSS, median / mean | 2.666 GiB / 4.784 GiB |
| maximum RSS, p95 / maximum | 16.750 GiB / 33.852 GiB |
| CPU efficiency | 55.86% |
| successful-task throughput | 977.69 tasks/hour |
| nodes used | all 25 nodes, `apl01`–`apl25` |

The production maximum exceeded the approximate 30 GiB pilot observation but
remained below the 40 GiB reservation. The median and mean RSS confirm that the
homogeneous request substantially over-reserved memory for most shards. Mean
submit-to-start wait was about 3,301 seconds and the maximum was 7,340 seconds,
while eligible-to-start wait was at most one second. This is consistent with
tasks waiting behind the 82-task array throttle rather than scheduler delay
after becoming eligible.

### Stage 2 storage failure and recovery

The first production attempt included Slurm array job `212628` and targeted
2,174 Object shards. It stopped with `EDQUOT`/`Disk quota exceeded` while
writing Stage 2 HDF5 files. At failure time:

- 1,074 of 2,174 HDF5 outputs were complete and valid;
- complete Stage 2 output occupied approximately 1.6 TiB;
- partial files occupied approximately 0.37 TiB;
- `/scratch/users/app.photoz` used approximately 2.1 TiB;
- the project-backed scratch allocation reported no available space.

The failure was caused by storage capacity, not by CPU or task-memory pressure.
Although user-level quota commands showed no explicit user limit, the scratch
directory was governed by a project quota. Infrastructure temporarily raised
that allocation from 1 TB to 10 TB, reporting about 8 TB available after the
change. The incomplete run was then cleaned and Stage 2 was restarted.

The successful restart was array job `214803`. Slurm records its first start at
13:20:22 and last end at 15:33:47; the operator announced it as running at
13:22 and reported all 2,174 tasks successful at 15:41. Job `212628` remains
the failed first attempt and must not be cited as the successful production
array.

Before the restart, extrapolation from the 1,074 complete files and the
786,420,720 catalog rows gave these capacity estimates:

| artifact | estimated size |
|---|---:|
| complete Stage 2 HDF5 tree | 3.45 TiB |
| Stage 3 float32 PDF parquet product | up to 1.74 TiB |
| Stage 3 staging plus HATS summary | 0.15–0.25 TiB |
| pre-existing data outside this run | approximately 0.5 TiB |

Because Stage 3 temporarily coexists with the retained HDF5 tree, PDF parquet,
staging, and final HATS catalog, the estimated peak was close to 6 TiB. The
operational request was therefore 8 TiB of available space, approximately
8.8 TB in decimal units. These are pre-run projections; no final
post-production disk-usage measurement was retained in the supplied notes.

### Stage 3 completion and aggregate resources

Stage 3 was announced as running at 16:26 and completed successfully at 16:48.
The profiler covers 82 Dask worker jobs, IDs `216977` through `217058`. Their
Slurm allocation ran from 16:25:25 through 16:33:24, a span of 479 seconds.
The difference from the message interval includes driver work, validation,
reporting delay, or other time outside the worker allocation; the Stage 3
driver timing remains the authoritative end-to-end measurement.

The configuration allocated up to 82 workers with 8 logical CPUs each, or 656
CPUs at full allocation, approximately 36% of the 1,832 CPUs on
`apl01`–`apl25`. Nodes `apl26`–`apl28` remained excluded. The observed worker
profile was:

| metric | observed value |
|---|---:|
| peak / mean concurrency | 82 / 81.97 |
| mean concurrency relative to target | 99.96% |
| worker duration | 478–479 s |
| maximum RSS, median / mean | 26.552 GiB / 27.564 GiB |
| maximum RSS, p95 / maximum | 37.387 GiB / 37.993 GiB |
| CPU efficiency | 21.77% |
| eligible-to-start wait, mean / maximum | 0.18 s / 1 s |
| nodes used | all 25 nodes, `apl01`–`apl25` |

Unlike Stage 2, Stage 3 used nearly the full 40 GiB reservation at the upper
tail: its maximum was only about 2 GiB below the request. Reducing Stage 3
memory based on mean usage would therefore be unsafe without another pilot.

All 82 worker records ended in `CANCELLED`, so the generic profiler reports
zero successful workers. This is consistent with Dask cancelling healthy
workers while closing the cluster and is not, by itself, evidence that the
HATS build failed. Conversely, worker cancellation alone cannot prove success.
The success criteria remain a zero driver exit code, clean worker logs, and
validated HATS/PDF outputs. The operator reported successful completion, but
the supplied artifacts still do not include the driver job ID, driver timing,
final disk use, or HATS integrity-validator output.

### Conclusions supported by this run

- Stage 2 was memory-placement limited rather than CPU limited.
- A homogeneous 40 GiB reservation safely covered the largest pilot shards but
  over-reserved memory for many smaller shards; production RSS ranged up to
  33.852 GiB, with a median of only 2.666 GiB.
- Scratch capacity was a production-critical resource; approximately 1 TB was
  insufficient, and a multi-terabyte preflight check is required.
- The Stage 3 configuration created the largest aggregate CPU request of the
  three stages, while the Stage 1 configuration was the most intensive on a
  single node.
- Stage 3 had the largest observed per-job memory pressure: p95 was 37.387 GiB
  and the maximum was 37.993 GiB, compared with 16.750 GiB and 33.852 GiB for
  Stage 2.
- CPU efficiency was 7.21% in Stage 1, 55.86% in Stage 2, and 21.77% across
  Stage 3 workers; these values support revisiting CPU sizing, but only through
  controlled pilots.

## Stage 1 training profile carried into v3

The established Apollo configuration trains on one `apl[17-25]` node with 98
logical CPUs, 231 GiB, and a three-hour limit. The allocation was chosen to use
approximately 95% of the schedulable CPU and memory on the larger Apollo nodes
while respecting whole-core allocation. BLAS/OpenMP threads are held at one to
avoid nested oversubscription under the multi-output XGBoost fit.

The retained technical acceptance criteria are:

- the job exits successfully and produces both raw and wrapped model pickles;
- the environment freeze is stored beside the model;
- the wrapped candidate passes `validate-models.py fzboost` against the trusted
  PZ Server reference;
- binary identity and identical predictions are not required across library
  versions, but the persisted scientific state must match.

## Stage 2 production profile carried into v3

The established runner processes one Object parquet per Slurm array task. A
37 GiB, one-hour task request and a maximum concurrency of 97 are the v3
defaults. The concurrency value is capacity-derived from schedulable memory
after the 4 GiB per-node system reservation:

```text
apl01-16: floor((124080 - 4096) / 37888) = 3 tasks/node
apl17-25: floor((253132 - 4096) / 37888) = 6 tasks/node

theoretical capacity = 16 * 3 + 9 * 6 = 102 tasks
round(0.95 * 102) = 97 concurrent tasks
```

This is a scheduling rationale, not a substitute for a current pilot. The five
largest shards must complete with exit code `0:0`, valid HDF5 markers, and no
memory errors before using the production default. Future changes must use
observed `MaxRSS` and `Elapsed` rather than treating 37 GiB, one hour, or 97 as
scientific constants. The current values incorporate the secondary-catalog
pilot recorded above.

One schema-validation shard recorded by the legacy workflow was
`object_6310_lsst_cells_v2_LSSTCam_runs_DRP_DP2_v30_0_8_DM-55060_stage3_20260606T114559Z.parq`,
with 41,940 rows, 1,224 columns, and all 16 required fields. This validates the
expected input shape for that shard only; it is not a full production
completion record.

## Stage 3 profile carried into v3

The HATS build uses Slurm-backed Dask workers. The current starting request is
82 workers, each with 8 CPUs, 40 GiB, and a 12-hour limit. Stage 2 HDF5 files
are retained by default. A successful run must produce both the scalar HATS
summary and PDF parquet product, preserve the 601-point grid, match Stage 2 row
counts, and remove temporary staging.

## Record required after the next v3 production run

Do not mark a v3 run validated without recording:

- repository commit and environment freeze;
- training, estimation-array, retry, and HATS-driver job IDs;
- `sacct` state, exit code, elapsed time, and peak memory;
- input, HDF5, HATS-summary, and PDF row/file counts;
- output from `validate-models.py fzboost` and `validate-hats.py fzboost`;
- any deviation from the default resource requests and the evidence supporting it.
