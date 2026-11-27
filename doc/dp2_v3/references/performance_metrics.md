# DP2 performance metrics

Each entry records one production run. The primary throughput metric is input
objects divided by allocated CPU-seconds, summed across tasks as
`AllocCPUS × ElapsedRaw`. Throughput per consumed CPU-second uses the sum of
Slurm `TotalCPU` across tasks. Wall time runs from the first task start to the
last task end. Mean allocated CPUs are allocated CPU-seconds divided by wall
time.

## 2026-11-23 to 2026-11-24 — FlexZBoost (FZBoost)

- **Scope:** Stage 2 production photo-z estimation, Slurm array `231501`.
  The measurement covers Stage 2 only.
- **Input dataset:** Rubin DP2 secondary Object catalog (partitioned Parquet),
  `/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset`.

| Metric | Value |
|---|---:|
| Input objects | 786,420,720 |
| Successful array tasks | 1,681 / 1,681 |
| Wall time | 40,427 s (11 h 13 min 47 s) |
| Allocated CPUs per task | 2 |
| Mean allocated CPUs | 30.23 |
| Peak allocated CPUs | 38 |
| Allocated CPU time | 1,222,096 CPU-s (339.47 CPU-h) |
| Consumed CPU time | 686,638.23 CPU-s (190.73 CPU-h) |
| CPU efficiency (consumed / allocated) | 56.19% |
| **Objects per allocated CPU-second** | **643.50** |
| Objects per consumed CPU-second | 1,145.32 |
| Allocated memory per task | 38 GiB |
| Mean / peak total allocated memory | 574.36 / 722 GiB |
| Per-task peak resident memory (Slurm `MaxRSS`), median / p95 / max | 3.35 / 21.03 / 30.90 GiB |

The object count is the sum of `input_rows` in `task-metadata.tsv` and matches
`hats_nrows` in the Stage 3 primary `pz_summary` catalog. The Slurm figures come
from `summary.json`. Both benchmark files are archived under
`not-tracked/2026-11-27/fzboost/stage2/benchmark/production-231501/`.
