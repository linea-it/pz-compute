# Serial batch Stage 3: build, validate, and profile HATS

Stage 3 runs only after the current algorithm's complete Stage 2 tree has
passed validation. The controller submits one persistent HATS driver and waits
for it to finish before validating products, profiling resources, and moving
to the next algorithm.

## 1. Driver and adaptive workers

The controller invokes `submit-hats.sh <algorithm>`, not `all`. The standard
configuration is:

| Component | Resources |
|---|---|
| Driver | 1 node, 1 task, 2 CPUs, 8 GiB, 2 days |
| Dask workers | adaptive 20–80 jobs |
| Each worker | 8 CPUs, 40 GiB, 12 hours |
| Worker scale-down delay | 180 seconds |

Only one adaptive cluster exists at a time. It can therefore scale within the
same 20–80 range as the corresponding individual run without competing with
DNF, BPZ, or FlexZBoost workers created by this batch workflow.

## 2. Validation before profiling

When the driver reaches `COMPLETED / 0:0`, the controller runs
`validate-hats.py <algorithm>`. The validator requires matching Stage 2,
summary-HATS, and PDF row counts; common schemas; the 601-bin redshift grid;
and no leftover Parquet staging after successful completion.

A completed Slurm driver is not sufficient by itself. Validation failure stops
the batch and prevents the next algorithm from starting.

## 3. Driver and worker benchmarks

After validation, the controller writes two independent profiles below the
driver's unique run tag:

```text
$PZ_DP2_ROOT/<algorithm>/stage3/benchmark/<run-tag>/
├── driver/
├── workers/
├── worker-job-ids.txt
└── run-context.log
```

The driver profile must be successful and retains its Slurm allocation and
end-to-end context. Worker IDs are recovered from the isolated Dask log
directory, then profiled together with concurrency target 80 and external
cluster context over `apl01-26`.

Adaptive Dask may cancel healthy workers during scale-down or cluster closure,
so worker terminal state alone is not the success criterion. The authoritative
combination is:

- completed driver with zero exit marker;
- clean driver and worker diagnostics;
- successful scientific HATS validation;
- retained `driver-resource-usage.log`;
- generated driver and worker resource profiles.

## 4. Algorithm transition

Only after all Stage 3 checks and profiles finish does the controller mark the
algorithm complete and return to Stage 1 for the next name in the serial order.
After BPZ completes, the controller writes the final batch `summary.md` and
`SUCCESS` marker.

Any driver failure, timeout, HATS validation error, missing worker log IDs, or
profiling failure produces the batch failure report and stops the sequence.
