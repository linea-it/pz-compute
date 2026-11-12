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
| Dask workers | adaptive 1–80 jobs |
| Each worker | 2 CPUs, 40 GiB, 12 hours |
| Worker scale-down delay | 180 seconds |

Only one adaptive cluster exists at a time. It starts with one requested job
and can scale to 80 as capacity becomes available, without competing with DNF,
BPZ, or FlexZBoost workers created by this batch workflow. There is no
`wait_for_workers` barrier: hats-import can begin with the first worker that
Slurm starts, while further worker jobs remain independently pending.
Each job contains one worker process with two threads, limiting it to two
concurrent tasks within the shared 40 GiB allocation. This protects the
memory-intensive hats-import reduction from the OOM failures observed with
eight concurrent threads.

## 2. Validation before profiling

When the driver reaches `COMPLETED / 0:0`, the controller runs
`validate-hats.py <algorithm>`. The validator requires matching Stage 2 and
HATS row counts, the common scalar schema, the algorithm-specific
`<algorithm>_ens_interp` nested column, 601-element `float32` grids and PDFs,
successful `qp.Ensemble` reconstruction for a bounded sample, and no leftover
Parquet staging or duplicate companion PDF tree.

Stage 3 uses `--pdf-layout=nested`. The temporary Parquet staging is deleted
automatically only after the HATS build succeeds. Stage 2 HDF5 outputs are
retained through validation and profiling; the batch does not create the old
`<hats_dir>.pdf/` product, so the validated HATS collection is the only final
copy of the PDFs.

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
├── worker-job-name.txt
└── run-context.log
```

The driver profile must be successful and retains its Slurm allocation and
end-to-end context. Every Dask worker receives a unique run-specific Slurm job
name. Worker IDs are recovered from accounting by that name and unioned with
the isolated worker logs, so jobs cancelled while still pending are retained.
They are then profiled together with concurrency target 80 and external cluster
context over `apl01-28`. Driver and worker profiles also retain lightweight
Slurm topology/configuration snapshots.

Adaptive Dask may cancel healthy workers during scale-down or cluster closure,
so worker terminal state alone is not the success criterion. The authoritative
combination is:

- completed driver with zero exit marker;
- clean driver and worker diagnostics;
- successful lightweight HATS and nested-PDF validation;
- retained `driver-resource-usage.log`;
- generated driver and worker resource profiles.

## 4. Algorithm transition

Only after all Stage 3 checks and profiles finish does the controller mark the
algorithm complete and return to Stage 1 for the next name in the serial order.
After BPZ completes, the controller writes the final batch `summary.md` and
`SUCCESS` marker.

Any driver failure, timeout, HATS validation error, missing worker log IDs, or
profiling failure produces the batch failure report and stops the sequence.
