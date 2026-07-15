# pz-build-hats

`pz-build-hats` builds a HATS photo-z summary catalog from existing
`pz-compute` inputs and `rail-estimate` outputs.

It is intentionally a post-processing step. The current `pz-compute`
parallelization still writes one `rail-estimate` HDF5 output per input file.
`pz-build-hats` then reads the matching input/output pairs, derives scalar
photo-z summary columns from the output PDFs, writes a separate full PDF
parquet product, stages a tabular parquet summary, and builds a HATS collection
from that staging. When `--use-hats-import` is enabled, the same Dask client is
used for both HDF5-to-parquet staging and `hats-import` collection generation.

## Products

This implementation creates two products:

```text
<hats_dir>/
<hats_dir>.pdf/
```

`<hats_dir>/` is the lightweight HATS summary product. `<hats_dir>.pdf/` is a
separate parquet product with the full PDF histograms linked by `objectId`.

The HATS summary schema is:

```text
objectId
coord_ra
coord_dec
zmode
zmean
zmedian
z_p16
z_p84
```

The full PDF product schema is:

```text
objectId
coord_ra
coord_dec
pdf
```

The `pdf` column is a fixed-size list containing one `p(z)` vector per object.
The matching redshift grid is written to:

```text
<hats_dir>.pdf/xvals.parquet
```

By default, PDF values are stored as `float32`. Use `--pdf-dtype=float64` if
you need to preserve double precision. To disable the full PDF product:

```bash
--no-pdf-product
```

To choose a different destination:

```bash
--pdf-output-dir=<dir>
```

The output columns are normalized to `objectId`, `coord_ra`, and `coord_dec`.
Input column aliases are detected automatically:

```text
objectId, object_id, coadd_object_id, id
coord_ra, ra
coord_dec, dec
```

You can override detection with:

```bash
--id-column=<name>
--ra-column=<name>
--dec-column=<name>
```

## Inputs

The command expects matching relative paths under the input and output
directories:

```text
input/a/b/file.hdf5
output/a/b/file.hdf5
```

The input HDF5 must contain object identifiers and coordinates. The output HDF5
must be a `rail-estimate` output with:

```text
meta/xvals
data/yvals
```

If input columns live inside an HDF5 group, pass:

```bash
--input-group=<group>
```

## Staging

The command always writes parquet staging files before building HATS:

```text
<hats_dir>.parquet_staging/
```

The staging contains one or more summary parquet parts plus:

```text
pz_pdf_xvals.parquet
```

`pz_pdf_xvals.parquet` records the redshift grid used by the `rail-estimate`
PDF output. The same grid is also written to the full PDF product as
`xvals.parquet`.

## Basic Usage

From a local run directory containing `input/` and `output/`:

```bash
pz-build-hats \
    --overwrite \
    input \
    output \
    pz-summary-hats
```

This writes:

```text
pz-summary-hats/
pz-summary-hats.pdf/
pz-summary-hats.parquet_staging/
```

Inspect the generated HATS catalog:

```bash
python - <<'PY'
import lsdb

catalog = lsdb.read_hats("pz-summary-hats/pz_summary")
print(catalog.head(5))
PY
```

## Fast Path

By default, staged outputs up to `100 MB` are converted to HATS with the LSDB
in-memory writer:

```bash
--fast-path-size-mb=100
```

This is the default path for local smoke tests and small fixtures.

Before writing parquet staging files, `pz-build-hats` estimates the summary
staging size from the `rail-estimate` output row counts. The estimate currently
uses `96 bytes` per output row. If this estimate is larger than the threshold
and `--use-hats-import` is not set, the command fails early without writing or
cleaning staging files.

When the PDF product is enabled, the command also prints an estimated PDF
payload size before conversion. This estimate is informational and does not
block execution.

If the estimate passes but the real staged parquet size still exceeds the
threshold, the command stops after writing staging files and prints a message
explaining how to continue.

For large runs, use one of these paths:

```bash
--use-hats-import
--staging-only
--fast-path-size-mb=<larger_limit_for_local_testing>
```

With `--use-hats-import`, the HDF5-to-parquet staging phase is also distributed
with Dask. Each Dask task converts one matching input/output HDF5 pair into
summary parquet and, unless disabled, full PDF parquet. The same Dask client is
then reused by `hats-import`.

## Dask Staging and hats-import With Local Dask

Force the Dask path locally by setting the fast-path threshold to zero:

```bash
pz-build-hats \
    --overwrite \
    --fast-path-size-mb=0 \
    --use-hats-import \
    --dask-cluster=local \
    --local-n-workers=1 \
    --local-threads-per-worker=2 \
    --local-memory-limit=6GB \
    input \
    output \
    pz-summary-hats-import
```

The default local Dask fallback is:

```text
1 worker
2 threads per worker
6GB memory limit
thread-based workers
```

Pass `--local-processes` if you need separate worker processes.

## Dask Staging and hats-import With Slurm Dask

For LIneA Slurm validation, pass the Slurm Dask resources explicitly:

```bash
pz-build-hats \
    --overwrite \
    --use-hats-import \
    --dask-cluster=slurm \
    --slurm-queue=cpu \
    --slurm-cores=32 \
    --slurm-processes=1 \
    --slurm-memory=120GB \
    --slurm-walltime=04:00:00 \
    --slurm-minimum-jobs=1 \
    --slurm-maximum-jobs=8 \
    --slurm-log-dir=log/dask \
    input \
    output \
    pz-summary-hats
```

Required Slurm options are:

```text
--slurm-cores
--slurm-memory
--slurm-walltime
--slurm-minimum-jobs
--slurm-maximum-jobs
```

Optional Slurm options include:

```text
--slurm-queue
--slurm-account
--slurm-processes
--slurm-adapt-interval
--slurm-scale-down-delay
--slurm-log-dir
```

The Slurm path creates a `dask-jobqueue` `SLURMCluster`, submits
`minimum_jobs * processes` initial workers, and enables adaptive scaling up to
`maximum_jobs`. The cluster is used first for staging and then reused by
`hats-import`.

## Existing Dask Scheduler

If you start a Dask scheduler yourself, connect to it instead of creating a
cluster. The scheduler is used for both staging and `hats-import`:

```bash
pz-build-hats \
    --overwrite \
    --use-hats-import \
    --dask-scheduler=tcp://scheduler-host:8786 \
    input \
    output \
    pz-summary-hats
```

`--dask-scheduler` is mutually exclusive with creating a local or Slurm cluster.

## Smoke Test

After following `doc/local-development-setup.md`, run:

```bash
cd "$PZ_LOCAL_RUN"

pz-build-hats \
    --overwrite \
    input \
    output \
    pz-summary-hats

pz-build-hats \
    --overwrite \
    --fast-path-size-mb=0 \
    --use-hats-import \
    --dask-cluster=local \
    --local-n-workers=1 \
    --local-threads-per-worker=2 \
    --local-memory-limit=6GB \
    input \
    output \
    pz-summary-hats-import
```

Both commands should produce HATS collections readable by LSDB.
