# DP2 GAaP 1.0 FlexZBoost Stage 3: Build HATS Products

This document describes how to build the HATS photo-z products after the DP2
GAaP 1.0 stage 2 estimation has completed.

The stage 2 output is a tree of `rail-estimate` HDF5 files:

```text
$PZ_STAGE2_RUN/output/object_*.hdf5
```

The original DP2 parquet catalog is used as the input identity catalog:

```text
/data/cl/lsst/dp2/primary/catalogs/object
```

`pz-build-hats` matches the two trees by relative path:

```text
input:  object_6309_...parq
output: object_6309_...hdf5
```

The HDF5 output stores the PDFs plus `ancillary/i_gaap1p0Mag_sfd`. This is the
dereddened GAaP 1.0 magnitude retained by Stage 2, not its uncertainty. The
association with `objectId` remains positional: row `i` in the input parquet is
matched to row `i` in both output datasets. The Stage 2 row-identity fingerprint
is checked against the input `objectId` values before conversion.

## 0. Load the common Apollo environment

Complete the one-time [Apollo/LineA setup](dp2_setup_apollo.md) before this
stage. It creates a dedicated HATS environment without modifying the frozen
Stage 1/Stage 2 environment.

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
cd "$PZ_COMPUTE_DIR"
```

Confirm that the Stage 3 environment is active:

```bash
python - <<'PY'
import dask_jobqueue
import distributed
import hats
import hats_import
import h5py
import lsdb
import pyarrow

print("DP2 stage 3 HATS environment is importable")
PY
```

## 1. Set Run Variables

Start from the stage 2 run directory. For the clipped RTN-124 run:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh

export PZ_STAGE2_RUN=$PZ_RUN_ROOT/dp2-stage2-fzboost-gaap1p0-clipped
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/primary/catalogs/object
export PZ_STAGE2_OUTPUT_DIR=$PZ_STAGE2_RUN/output
export PZ_HATS_DIR=$PZ_STAGE2_RUN/pz-fzboost-gaap1p0-clipped-hats

cd "$PZ_STAGE2_RUN"
mkdir -p log/dask-stage3
```

## 2. Validate Input and Output Pairing

Confirm that the number of input shards matches the number of production Stage
2 outputs. The Stage 2 smoke test is kept in a separate directory and must not
be copied into this production output tree:

```bash
cd "$PZ_STAGE2_RUN"

echo "input parquets: $(find "$PZ_DP2_INPUT_DATASET" -name '*.parq' | wc -l)"
echo "production HDF5 files: $(find "$PZ_STAGE2_OUTPUT_DIR" -name '*.hdf5' | wc -l)"
```

Validate that every input parquet has the expected output HDF5:

```bash
python - <<'PY'
from pathlib import Path
import os

input_root = Path(os.environ["PZ_DP2_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])

missing = []
for input_path in sorted(input_root.glob("**/*.parq")):
    relative = input_path.relative_to(input_root)
    output_path = output_root / relative.with_suffix(".hdf5")
    if not output_path.exists():
        missing.append(str(relative))

print("missing output files:", len(missing))
for relative in missing[:20]:
    print(relative)

if missing:
    raise SystemExit("Stage 2 outputs are incomplete")
PY
```

Validate one row-count match. This checks the key assumption used to associate
`objectId` with PDFs:

```bash
python - <<'PY'
from pathlib import Path
import os
import h5py
import pyarrow.parquet as pq

input_root = Path(os.environ["PZ_DP2_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])

input_path = sorted(input_root.glob("**/*.parq"))[0]
relative = input_path.relative_to(input_root)
output_path = output_root / relative.with_suffix(".hdf5")

input_rows = pq.read_metadata(input_path).num_rows
with h5py.File(output_path, "r") as handle:
    output_rows = handle["data/yvals"].shape[0]
    bins = handle["data/yvals"].shape[1]
    retained_rows = handle["ancillary/i_gaap1p0Mag_sfd"].shape[0]
    ancillary_columns = sorted(handle["ancillary"].keys())

print("input:", input_path)
print("output:", output_path)
print("input rows:", input_rows)
print("output rows:", output_rows)
print("pdf bins:", bins)
assert input_rows == output_rows
assert retained_rows == output_rows
assert bins == 601
assert ancillary_columns == ["i_gaap1p0Mag_sfd"]
PY
```

## 3. Run a Small Staging Smoke Test

Before building the full HATS product, run `pz-build-hats` on a small copied
subset. This verifies parquet input support, HDF5 PDF reading, positional
matching, and output schemas.

```bash
cd "$PZ_STAGE2_RUN"

rm -rf stage3-smoke
mkdir -p stage3-smoke/input stage3-smoke/output

python - <<'PY'
from pathlib import Path
import os
import shutil

input_root = Path(os.environ["PZ_DP2_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])
smoke_root = Path("stage3-smoke")

for input_path in sorted(input_root.glob("**/*.parq"))[:3]:
    relative = input_path.relative_to(input_root)
    output_path = output_root / relative.with_suffix(".hdf5")

    smoke_input = smoke_root / "input" / relative
    smoke_output = smoke_root / "output" / relative.with_suffix(".hdf5")
    smoke_input.parent.mkdir(parents=True, exist_ok=True)
    smoke_output.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(input_path, smoke_input)
    shutil.copy2(output_path, smoke_output)

print("wrote smoke subset:", smoke_root)
PY

pz-build-hats \
    --overwrite \
    --staging-only \
    --require-complete-marker \
    stage3-smoke/input \
    stage3-smoke/output \
    stage3-smoke/pz-summary-hats
```

Inspect the smoke staging output:

```bash
python - <<'PY'
from pathlib import Path
import pyarrow.parquet as pq

staging = Path("stage3-smoke/pz-summary-hats.parquet_staging")
parts = sorted(path for path in staging.glob("*.parquet")
               if path.name != "pz_pdf_xvals.parquet")
if not parts:
    raise SystemExit("No smoke staging parquet parts found")

table = pq.read_table(parts[0])
xvals = pq.read_table(staging / "pz_pdf_xvals.parquet")
pdf_dir = Path("stage3-smoke/pz-summary-hats.pdf")
pdf_parts = sorted(pdf_dir.glob("*pdf-part*.parquet"))
if not pdf_parts:
    raise SystemExit("No smoke PDF parquet parts found")
pdf_table = pq.read_table(pdf_parts[0])
pdf_xvals = pq.read_table(pdf_dir / "xvals.parquet")

expected_summary_columns = [
    "objectId", "coord_ra", "coord_dec",
    "zmode", "zmean", "zmedian", "z_p16", "z_p84",
    "i_gaap1p0Mag_sfd",
]
expected_pdf_columns = [
    "objectId", "coord_ra", "coord_dec", "i_gaap1p0Mag_sfd", "pdf",
]

print("summary part:", parts[0])
print(table.schema)
assert table.column_names == expected_summary_columns
assert xvals.column_names == ["bin_index", "z"]
assert xvals.num_rows == 601
assert pdf_table.column_names == expected_pdf_columns
assert pdf_table.schema.field("pdf").type.list_size == 601
assert pdf_xvals.column_names == ["bin_index", "z"]
assert pdf_xvals.num_rows == 601
print("rows in first part:", table.num_rows)
print("xvals rows:", xvals.num_rows)
print(table.to_pandas().head())
PY
```

## 4. Build the Full HATS Products

Use the Slurm Dask mode for the full DP2 run. `--fast-path-size-mb=0` forces the
distributed `hats-import` path instead of the local in-memory LSDB writer.

This command writes the two persistent products:

```text
$PZ_HATS_DIR/
$PZ_HATS_DIR.pdf/
```

The intermediate `$PZ_HATS_DIR.parquet_staging/` tree is removed automatically
after the final HATS catalog is built successfully. Stage 2 HDF5 files are kept
by default.

The summary HATS product contains scalar estimates:

```text
objectId, coord_ra, coord_dec, zmode, zmean, zmedian, z_p16, z_p84, i_gaap1p0Mag_sfd
```

The separate PDF parquet product contains:

```text
objectId, coord_ra, coord_dec, i_gaap1p0Mag_sfd, pdf
```

The `pdf` field is a fixed-size vector with 601 values ordered according to
`$PZ_HATS_DIR.pdf/xvals.parquet`. The command below stores these values as
`float32`; use `--pdf-dtype=float64` only if the increased storage cost is
required by a downstream analysis.

Each Slurm Dask job requests 8 cores and 40 GB, or 5 GB per core. The
`cpu_photoz` partition, submitted under the `hpc-photoz` account, exposes all
28 Apollo compute nodes:

- 16 nodes `apl[01-16]`, each with 56 cores and 128 GB RAM;
- 12 nodes `apl[17-28]`, each with 104 cores and 256 GB RAM.

Memory, rather than CPU count, limits the number of these jobs that fit on each
node:

```text
apl[01-16]: min(floor(56 / 8), floor(128 GB / 40 GB)) = min(7, 3) = 3 jobs/node
apl[17-28]: min(floor(104 / 8), floor(256 GB / 40 GB)) = min(13, 6) = 6 jobs/node

total theoretical capacity = 16 * 3 + 12 * 6 = 120 Slurm jobs
round(0.95 * 120) = 114 Slurm jobs
```

Set both the minimum and maximum to 114 so that Dask requests this fixed number
of jobs instead of scaling below the 95% target. Slurm may leave some jobs
pending when nodes are occupied by other workloads, but the Stage 3
configuration itself continues to request 114 jobs.

Run:

```bash
cd "$PZ_STAGE2_RUN"
mkdir -p log/dask-stage3

pz-build-hats \
    --overwrite \
    --require-complete-marker \
    --pdf-dtype=float32 \
    --fast-path-size-mb=0 \
    --use-hats-import \
    --dask-cluster=slurm \
    --slurm-queue=cpu_photoz \
    --slurm-account=hpc-photoz \
    --slurm-cores=8 \
    --slurm-processes=1 \
    --slurm-memory=40GB \
    --slurm-walltime=12:00:00 \
    --slurm-minimum-jobs=114 \
    --slurm-maximum-jobs=114 \
    --slurm-log-dir=log/dask-stage3 \
    "$PZ_DP2_INPUT_DATASET" \
    "$PZ_STAGE2_OUTPUT_DIR" \
    "$PZ_HATS_DIR"
```

The Slurm Dask workers perform two operations:

- convert each parquet/HDF5 pair into summary parquet staging and PDF parquet;
- run `hats-import` to build the final HATS collection from the summary staging.

The command uses the adaptive-scaling interface with an equal minimum and
maximum, fixing the request at 114 Slurm worker jobs for the duration of the
build.

If only the lightweight scalar HATS summary is needed, disable the separate
full PDF parquet product:

```bash
--no-pdf-product
```

Keep the PDF product when downstream users need the full `p(z)` vectors.

To keep the parquet staging for diagnostics, add:

```bash
--keep-staging
```

To delete the stage 2 HDF5 files only after the PDF parquet and final HATS
products complete successfully, add:

```bash
--delete-hdf5-outputs
```

Do not use the deletion option when the HDF5 representation must be delivered
or retained.

## 5. Monitor the Build

Watch the main `pz-build-hats` process in the terminal where it is running.
Watch Dask worker jobs from another terminal:

```bash
squeue -u "$(whoami)"
```

Inspect worker logs:

```bash
cd "$PZ_STAGE2_RUN"
find log/dask-stage3 -type f -print | sort | tail -50
grep -R "Traceback\\|Error:\\|Killed\\|OOM\\|out of memory" log/dask-stage3 || true
```

## 6. Inspect the HATS Summary

Read the final HATS summary and compare its metadata row count with the retained
stage 2 HDF5 outputs:

```bash
cd "$PZ_STAGE2_RUN"

python - <<'PY'
from pathlib import Path
import os
import h5py
import lsdb

hats_dir = os.environ["PZ_HATS_DIR"]
input_root = Path(os.environ["PZ_DP2_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])
catalog = lsdb.read_hats(f"{hats_dir}/pz_summary")
sample = catalog.head(5)

expected_summary_columns = [
    "objectId", "coord_ra", "coord_dec",
    "zmode", "zmean", "zmedian", "z_p16", "z_p84",
    "i_gaap1p0Mag_sfd",
]
assert list(catalog.columns) == expected_summary_columns
output_rows = 0
for input_path in input_root.glob("**/*.parq"):
    relative = input_path.relative_to(input_root)
    output_path = output_root / relative.with_suffix(".hdf5")
    with h5py.File(output_path, "r") as handle:
        output_rows += handle["data/yvals"].shape[0]

summary_rows = len(catalog)
staging = Path(hats_dir + ".parquet_staging")
print(sample)
print("columns:", list(sample.columns))
print("stage 2 output rows:", output_rows)
print("HATS summary rows:", summary_rows)
assert output_rows == summary_rows
assert not staging.exists(), f"temporary staging was not removed: {staging}"
PY
```

This check assumes the default behavior of retaining HDF5 outputs. When
`--delete-hdf5-outputs` is selected, perform the scientific validation on a
pilot run first and rely on the successful conversion checks for the full run.

## 7. Inspect the PDF Product

Skip this section if the full PDF product was disabled with
`--no-pdf-product`.

```bash
cd "$PZ_STAGE2_RUN"

python - <<'PY'
from pathlib import Path
import os
import h5py
import pyarrow.parquet as pq

input_root = Path(os.environ["PZ_DP2_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])
pdf_dir = Path(os.environ["PZ_HATS_DIR"] + ".pdf")
parts = sorted(path for path in pdf_dir.glob("*pdf-part*.parquet"))
if not parts:
    raise SystemExit("No PDF parquet parts found")

table = pq.read_table(parts[0])
xvals = pq.read_table(pdf_dir / "xvals.parquet")
expected_pdf_columns = [
    "objectId", "coord_ra", "coord_dec", "i_gaap1p0Mag_sfd", "pdf",
]
output_rows = 0
for input_path in input_root.glob("**/*.parq"):
    relative = input_path.relative_to(input_root)
    output_path = output_root / relative.with_suffix(".hdf5")
    with h5py.File(output_path, "r") as handle:
        output_rows += handle["data/yvals"].shape[0]
pdf_rows = sum(pq.read_metadata(path).num_rows for path in parts)

print("PDF part:", parts[0])
print(table.schema)
assert table.column_names == expected_pdf_columns
print("rows in first PDF part:", table.num_rows)
print("bins in first PDF vector:", len(table.column("pdf")[0].as_py()))
print("xvals rows:", xvals.num_rows)
print("stage 2 output rows:", output_rows)
print("PDF rows:", pdf_rows)
assert len(table.column("pdf")[0].as_py()) == 601
assert xvals.column_names == ["bin_index", "z"]
assert xvals.num_rows == 601
assert output_rows == pdf_rows
PY
```

## 8. Build a reduced local test product

Use this path with the one- or two-shard output generated by the local section
of Stage 2. It does not require `/data`, `/scripts`, `/scratch`, or Slurm.

Load the local Stage 3 environment and point it at the reduced Stage 2 run:

```bash
source /path/to/pz-dp2-work/software/env-dp2-stage3-hats.sh

export PZ_STAGE2_RUN=$PZ_RUN_ROOT/dp2-stage2-fzboost-gaap1p0-local-test
export PZ_DP2_INPUT_DATASET=$PZ_STAGE2_RUN/input
export PZ_STAGE2_OUTPUT_DIR=$PZ_STAGE2_RUN/output
export PZ_HATS_DIR=$PZ_STAGE2_RUN/pz-fzboost-gaap1p0-local-test-hats

cd "$PZ_STAGE2_RUN"
```

Build both products with a small local Dask cluster. Setting the fast-path
threshold to zero ensures that this test exercises the same distributed
`hats-import` path used on Apollo, with local workers replacing Slurm workers:

```bash
pz-build-hats \
    --overwrite \
    --require-complete-marker \
    --pdf-dtype=float32 \
    --fast-path-size-mb=0 \
    --use-hats-import \
    --dask-cluster=local \
    --local-n-workers=2 \
    --local-threads-per-worker=2 \
    --local-memory-limit=4GB \
    "$PZ_DP2_INPUT_DATASET" \
    "$PZ_STAGE2_OUTPUT_DIR" \
    "$PZ_HATS_DIR"
```

Machines with less than 8 GB available for the workers should use one worker
or a smaller per-worker limit. Validate the two local products:

```bash
"$PZ_PY" - <<'PY'
from pathlib import Path
import os

import lsdb
import pyarrow.parquet as pq

hats_dir = Path(os.environ["PZ_HATS_DIR"])
summary = lsdb.read_hats(str(hats_dir / "pz_summary"))
expected_summary = [
    "objectId", "coord_ra", "coord_dec",
    "zmode", "zmean", "zmedian", "z_p16", "z_p84",
    "i_gaap1p0Mag_sfd",
]
assert list(summary.columns) == expected_summary

pdf_dir = Path(str(hats_dir) + ".pdf")
parts = sorted(pdf_dir.glob("*pdf-part*.parquet"))
if not parts:
    raise SystemExit("No local PDF parquet parts found")
table = pq.read_table(parts[0])
assert table.column_names == [
    "objectId", "coord_ra", "coord_dec", "i_gaap1p0Mag_sfd", "pdf",
]
assert table.schema.field("pdf").type.list_size == 601

xvals = pq.read_table(pdf_dir / "xvals.parquet")
assert xvals.column_names == ["bin_index", "z"]
assert xvals.num_rows == 601
assert len(summary) == sum(pq.read_metadata(path).num_rows for path in parts)

print("local HATS rows:", len(summary))
print("local products are valid")
PY
```

## 9. Expected Outputs

The stage 3 run is successful when:

- `pz-build-hats` finishes without an exception;
- the HATS summary has exactly `objectId`, `coord_ra`, `coord_dec`, `zmode`,
  `zmean`, `zmedian`, `z_p16`, `z_p84`, and `i_gaap1p0Mag_sfd`;
- each PDF parquet has exactly `objectId`, `coord_ra`, `coord_dec`,
  `i_gaap1p0Mag_sfd`, and `pdf`;
- each `pdf` has 601 values and `$PZ_HATS_DIR.pdf/xvals.parquet` maps those
  values to the 601-point redshift grid;
- `$PZ_HATS_DIR/pz_summary` is readable with `lsdb.read_hats`;
- the HATS metadata row count matches the total stage 2 HDF5 row count;
- `$PZ_HATS_DIR.parquet_staging` is absent after the successful final build;
- if enabled, `$PZ_HATS_DIR.pdf/xvals.parquet` exists;
- if enabled, the PDF product row count matches the stage 2 HDF5 row count;
- stage 2 HDF5 files remain unless `--delete-hdf5-outputs` was selected;
- Dask worker logs do not contain unresolved tracebacks or memory failures.
