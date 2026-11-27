# Apollo resource measurements

This record fixes the resource rationale for the custom DNF cModel workflow.
It is operational evidence, not part of the scientific configuration. All
jobs ran on `cpu_photoz` with one requested CPU per task and completed with
exit code `0:0`.

## Stage 1 training

| variant | job | elapsed | maximum RSS | original request |
|---|---:|---:|---:|---:|
| `griz` | 225065 | 10 s | 0.325 GiB | 8 GiB, 1 h |
| `riz` | 225066 | 10 s | 0.183 GiB | 8 GiB, 1 h |

The accepted request is one CPU, 2 GiB, and 15 minutes. Relative to the larger
measurement, this supplies more than six times the observed memory and 90
times the observed duration. The accounting report shows two allocated CPU
threads for one requested core on this SMT topology, while average use was
approximately one CPU; the workflow therefore remains single-CPU.

## Stage 2 five-shard pilots

| variant | array job | successful tasks | duration p50 / p95 / max | RSS p50 / p95 / max |
|---|---:|---:|---:|---:|
| `griz` | 225091 | 5/5 | 29m14s / 32m05s / 32m23s | 18.14 / 25.72 / 27.50 GiB |
| `riz` | 225092 | 5/5 | 25m34s / 28m47s / 28m55s | 19.11 / 26.02 / 27.48 GiB |

All ten tasks sustained approximately one CPU. Queue wait was one second, and
the five-task arrays reached their concurrency target immediately. The five
largest input shards contained 4,816,770 rows in total.

The accepted per-task production request is one CPU, 36 GiB, and one hour.
The 36-GiB request is 30.9% above the largest measured RSS. Apollo constrains
jobs to 95% of requested memory, leaving 34.2 GiB usable and a 24.3% margin
over the measured peak. One hour is 85.3% longer than the longest pilot task.

At 36 GiB, the `cpu_photoz` topology captured with the pilot provides:

- three comfortable slots on each of `apl01`–`apl16`: 48 slots;
- six slots on each of `apl17`–`apl26`: 60 slots;
- 108 discrete memory slots in total.

The production throttle is 102 tasks, or 94.4% of those slots. This retains
six discrete slots plus the unused memory inside each allocation for
coexistence and operating margin.

## Pilot photometry context

The first smoke shard was unusually sparse in several cModel bands. The five
largest pilot shards were substantially more representative. Across their
4,816,770 rows, the non-detection fractions were:

| band | non-detections | fraction |
|---|---:|---:|
| `g` | 346,066 | 7.18% |
| `r` | 281,221 | 5.84% |
| `i` | 339,060 | 7.04% |
| `z` | 398,465 | 8.27% |

Individual pilot-shard fractions ranged from 4.05% to 11.09%, rather than the
complete-band absence seen in the first smoke sample. This does not replace a
full-catalog photometry QA, but it shows that the smoke shard is not
representative of the largest production inputs.
