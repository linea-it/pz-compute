# pz-build-hats

`pz-build-hats` builds a HATS photo-z summary catalog from existing
`pz-compute` inputs and `rail-estimate` outputs.

It is intentionally a post-processing step. The current `pz-compute`
parallelization still writes one `rail-estimate` HDF5 output per input file.
`pz-build-hats` then reads the matching input/output pairs, derives scalar
photo-z summary columns, stages Parquet, and builds a HATS collection. PDFs can
be written as a separate companion Parquet dataset, embedded directly in the
HATS catalog as a DP1-compatible nested `*_ens_interp` column, written in both
layouts for migration, or omitted. When `--use-hats-import` is enabled, the
same Dask client is used for staging and `hats-import` collection generation.

## Products

The backward-compatible default is:

```text
<hats_dir>/
<hats_dir>.pdf/
```

`<hats_dir>/` is the lightweight HATS summary product. `<hats_dir>.pdf/` is a
separate Parquet product with the full PDF histograms linked by `objectId`.
Select the storage layout explicitly with:

```text
--pdf-layout=companion  # separate <hats_dir>.pdf/ (default)
--pdf-layout=nested     # PDF embedded in HATS; no companion
--pdf-layout=both       # migration/validation only
--pdf-layout=none       # scalar HATS only
```

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

The companion PDF schema is:

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

For `nested` or `both`, the HATS schema gains the column selected by
`--pdf-column` (default `pz_ens_interp`):

```text
pz_ens_interp: struct
├── xvals: list<float32>
└── yvals: list<float32>
```

The layout follows the Rubin DP1 photo-z convention. `xvals` is repeated per
object so an LSDB partition is self-contained and can be reconstructed as a
`qp.Ensemble(qp.interp_gen, ...)`. Parquet compression handles the identical
grids efficiently. Staging and companion Parquet files are written with ZSTD;
the final HATS writer applies its own current Parquet defaults.

By default, PDF values are stored as `float32`. Use `--pdf-dtype=float64` if
you need to preserve double precision. `--no-pdf-product` remains as a
deprecated alias for `--pdf-layout=none`.

To choose a different companion destination:

```bash
--pdf-output-dir=<dir>
```

The source `rail-estimate` HDF5 files are kept by default. Once a durable
companion or completed nested HATS product and every other requested product
have been written successfully, they can be removed automatically with:

```bash
--delete-hdf5-outputs
```

This option requires a durable PDF representation. Nested-only staging is not
enough: the final HATS build must finish before deletion. All matched paths are
validated before deletion starts. A failed conversion or HATS build never
deletes the HDF5 inputs.

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

input/a/b/file.parquet
output/a/b/file.hdf5
```

Input files may be HDF5 or parquet. The input file must contain object
identifiers and coordinates. For parquet input, `pz-build-hats` reads only the
identifier and coordinate columns needed to associate each PDF with the original
object. Metadata files in partitioned parquet datasets, such as `_metadata` and
`_common_metadata`, are ignored because only `.hdf5`, `.h5`, `.parquet`, `.parq`, and `.pq` input shards are considered.

The output HDF5 must be a `rail-estimate` output with:

```text
meta/xvals
data/yvals
```

When `rail-estimate --output-columns` is used, selected values are stored as
one-dimensional datasets under `ancillary/`. `pz-build-hats` validates their
row counts and copies them into the HATS staging and, when requested, the
companion PDF parts. All matched output files must expose a compatible
ancillary schema.

When the estimate contains row-integrity metadata, `pz-build-hats` recomputes
the identifier fingerprint from the matched input shard and rejects a changed
object set or row order. A present but incomplete estimate marker is always
rejected. Use `--require-complete-marker` for production runs to also reject
older outputs that do not contain a completion marker.

Zero-row input/output pairs are valid and are checked like any other pair. They
do not add Parquet rows, while non-empty shards in the same run build every
requested product normally.

If input columns live inside an HDF5 group, pass:

```bash
--input-group=<group>
```

`--input-group` is only valid for HDF5 input files.

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
PDF output. For companion layouts, the same grid is written as
`<hats_dir>.pdf/xvals.parquet`; nested layouts carry `xvals` in every nested
row. After a successful final HATS build, the staging directory is
removed by default. Pass `--keep-staging` to retain it. `--staging-only` always
retains staging because it is the requested output of that mode. If conversion
or HATS construction fails, staging is retained for diagnosis or resumption.

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
```

The temporary `pz-summary-hats.parquet_staging/` directory is deleted after
the HATS catalog is complete. Add `--keep-staging` when it is needed for
debugging or inspection.

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

Before writing Parquet staging files, `pz-build-hats` estimates the staging
size from the `rail-estimate` output row counts. The scalar estimate uses
`96 bytes` per row; nested layouts also include the uncompressed `xvals` and
`yvals` payload. If this estimate is larger than the threshold and
`--use-hats-import` is not set, the command fails early without writing or
cleaning staging files.

When the companion PDF product is enabled, the command also prints its
estimated payload size before conversion. This estimate is informational and
does not block execution.

If the estimate passes but the real staged parquet size still exceeds the
threshold, the command stops after writing staging files and prints a message
explaining how to continue.

For large runs, use one of these paths:

```bash
--use-hats-import
--staging-only
--fast-path-size-mb=<larger_limit_for_local_testing>
```

With `--use-hats-import`, the HDF5-to-Parquet staging phase is also distributed
with Dask. Each task converts one matching input/output pair into HATS staging,
including the nested PDF column when selected, and optionally writes a
companion PDF part. The same Dask client is then reused by `hats-import`.

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
    --slurm-exclude='node[09-10]' \
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
--slurm-exclude
```

The Slurm path creates a `dask-jobqueue` `SLURMCluster`, submits
`minimum_jobs * processes` initial workers, and enables adaptive scaling up to
`maximum_jobs`. The cluster is used first for staging and then reused by
`hats-import`. `--slurm-exclude` is forwarded to the worker jobs as Slurm's
`--exclude` directive.

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
