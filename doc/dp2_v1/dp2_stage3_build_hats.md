# DP2 PSF FlexZBoost Stage 3: Build HATS Products

This document describes how to build HATS photo-z products after the DP2 PSF
stage 2 estimation has completed.

The stage 2 output is a tree of `rail-estimate` HDF5 files:

```text
$PZ_STAGE2_RUN/output/Norder=*/Dir=*/Npix=*.hdf5
```

The original DP2 parquet catalog is used as the input identity catalog:

```text
/data/cl/lsst/dp2/secondary/catalogs/skinny_collection/mag/psf/sfd/catalog/dataset
```

`pz-build-hats` matches the two trees by relative path:

```text
input:  Norder=3/Dir=0/Npix=448.parquet
output: Norder=3/Dir=0/Npix=448.hdf5
```

The HDF5 output does not store `objectId`. The association is positional:
row `i` in the input parquet is matched to row `i` in `data/yvals` from the
corresponding HDF5 output.

## 0. Requirements

Run these commands on Apollo from a terminal or JupyterHub terminal.

Use a `pz-compute` checkout that includes parquet input support in
`rail_scripts/pz-build-hats`. This support is required because the DP2 stage 2
workflow keeps the original catalog as parquet and writes only the photo-z PDFs
as HDF5.

The Python environment must include:

```text
pyarrow
h5py
dask_jobqueue
distributed
lsdb
hats
hats_import
```

If the stage 2 environment does not already include the HATS packages, install
them:

```bash
conda install -y -c conda-forge \
    pyarrow \
    hdf5 \
    h5py \
    astropy \
    distributed \
    dask-jobqueue

pip install lsdb hats-import hats
```

Make sure `pz-build-hats` is available:

```bash
export SCRIPTS=/scripts/$(whoami)
export PZ_COMPUTE_DIR=$SCRIPTS/pz-compute

ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/pz-build-hats" "$SCRIPTS/bin/pz-build-hats"
chmod +x "$SCRIPTS/bin/pz-build-hats"
```

Check imports:

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
source /scripts/$(whoami)/ondemand/env-dp2-psf-estimate.sh

export PZ_STAGE2_RUN=$PZ_RUN_ROOT/dp2-stage2-fzboost-psf-clipped
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/skinny_collection/mag/psf/sfd/catalog/dataset
export PZ_STAGE2_OUTPUT_DIR=$PZ_STAGE2_RUN/output
export PZ_HATS_DIR=$PZ_STAGE2_RUN/pz-fzboost-psf-clipped-hats

cd "$PZ_STAGE2_RUN"
mkdir -p log/dask-stage3
```

For the full-training-set model, use the corresponding stage 2 run directory
and HATS output name:

```bash
export PZ_STAGE2_RUN=$PZ_RUN_ROOT/dp2-stage2-fzboost-psf
export PZ_STAGE2_OUTPUT_DIR=$PZ_STAGE2_RUN/output
export PZ_HATS_DIR=$PZ_STAGE2_RUN/pz-fzboost-psf-full-hats
```

## 2. Validate Input and Output Pairing

Confirm that the number of input parquet files matches the number of stage 2
HDF5 outputs:

```bash
cd "$PZ_STAGE2_RUN"

echo "input parquets: $(find "$PZ_DP2_INPUT_DATASET" -name '*.parquet' | wc -l)"
echo "output HDF5 files: $(find "$PZ_STAGE2_OUTPUT_DIR" -name '*.hdf5' | wc -l)"
```

Validate that every input parquet has the expected output HDF5:

```bash
python - <<'PY'
from pathlib import Path
import os

input_root = Path(os.environ["PZ_DP2_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])

missing = []
for input_path in sorted(input_root.glob("**/*.parquet")):
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

input_path = sorted(input_root.glob("**/*.parquet"))[0]
relative = input_path.relative_to(input_root)
output_path = output_root / relative.with_suffix(".hdf5")

input_rows = pq.read_metadata(input_path).num_rows
with h5py.File(output_path, "r") as handle:
    output_rows = handle["data/yvals"].shape[0]
    bins = handle["data/yvals"].shape[1]

print("input:", input_path)
print("output:", output_path)
print("input rows:", input_rows)
print("output rows:", output_rows)
print("pdf bins:", bins)
assert input_rows == output_rows
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

for input_path in sorted(input_root.glob("**/*.parquet"))[:3]:
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

print("summary part:", parts[0])
print(table.schema)
print("rows in first part:", table.num_rows)
print("xvals rows:", xvals.num_rows)
print(table.to_pandas().head())
PY
```

## 4. Build the Full HATS Products

Use the Slurm Dask mode for the full DP2 run. `--fast-path-size-mb=0` forces the
distributed `hats-import` path instead of the local in-memory LSDB writer.

This command writes:

```text
$PZ_HATS_DIR/
$PZ_HATS_DIR.pdf/
$PZ_HATS_DIR.parquet_staging/
```

The summary HATS product contains scalar estimates:

```text
objectId, coord_ra, coord_dec, zmode, zmean, zmedian, z_p16, z_p84
```

The separate PDF parquet product contains:

```text
objectId, coord_ra, coord_dec, pdf
```

Run:

```bash
cd "$PZ_STAGE2_RUN"
mkdir -p log/dask-stage3

pz-build-hats \
    --overwrite \
    --fast-path-size-mb=0 \
    --use-hats-import \
    --dask-cluster=slurm \
    --slurm-queue=cpu \
    --slurm-account=hpc-public \
    --slurm-cores=8 \
    --slurm-processes=1 \
    --slurm-memory=32GB \
    --slurm-walltime=12:00:00 \
    --slurm-minimum-jobs=2 \
    --slurm-maximum-jobs=16 \
    --slurm-log-dir=log/dask-stage3 \
    "$PZ_DP2_INPUT_DATASET" \
    "$PZ_STAGE2_OUTPUT_DIR" \
    "$PZ_HATS_DIR"
```

The Slurm Dask workers perform two operations:

- convert each parquet/HDF5 pair into summary parquet staging and PDF parquet;
- run `hats-import` to build the final HATS collection from the summary staging.

The command enables adaptive scaling, so Apollo may submit additional Dask
worker jobs up to `--slurm-maximum-jobs`.

If only the lightweight scalar HATS summary is needed, disable the separate
full PDF parquet product:

```bash
--no-pdf-product
```

Keep the PDF product when downstream users need the full `p(z)` vectors.

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

Read the final HATS summary with LSDB:

```bash
cd "$PZ_STAGE2_RUN"

python - <<'PY'
import os
import lsdb

hats_dir = os.environ["PZ_HATS_DIR"]
catalog = lsdb.read_hats(f"{hats_dir}/pz_summary")
sample = catalog.head(5)

print(sample)
print("columns:", list(sample.columns))
PY
```

Check the staged summary row count against the stage 2 output row count:

```bash
python - <<'PY'
from pathlib import Path
import os
import h5py
import pyarrow.parquet as pq

output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])
staging = Path(os.environ["PZ_HATS_DIR"] + ".parquet_staging")

output_rows = 0
for path in output_root.glob("**/*.hdf5"):
    with h5py.File(path, "r") as handle:
        output_rows += handle["data/yvals"].shape[0]

summary_rows = 0
for path in staging.glob("*.parquet"):
    if path.name == "pz_pdf_xvals.parquet":
        continue
    summary_rows += pq.read_metadata(path).num_rows

print("stage 2 output rows:", output_rows)
print("summary staging rows:", summary_rows)
assert output_rows == summary_rows
PY
```

## 7. Inspect the PDF Product

Skip this section if the full PDF product was disabled with
`--no-pdf-product`.

```bash
cd "$PZ_STAGE2_RUN"

python - <<'PY'
from pathlib import Path
import os
import pyarrow.parquet as pq

pdf_dir = Path(os.environ["PZ_HATS_DIR"] + ".pdf")
parts = sorted(path for path in pdf_dir.glob("*pdf-part*.parquet"))
if not parts:
    raise SystemExit("No PDF parquet parts found")

table = pq.read_table(parts[0])
xvals = pq.read_table(pdf_dir / "xvals.parquet")

print("PDF part:", parts[0])
print(table.schema)
print("rows in first PDF part:", table.num_rows)
print("bins in first PDF vector:", len(table.column("pdf")[0].as_py()))
print("xvals rows:", xvals.num_rows)
PY
```

Check that the summary staging and full PDF product have the same row count:

```bash
python - <<'PY'
from pathlib import Path
import os
import pyarrow.parquet as pq

staging = Path(os.environ["PZ_HATS_DIR"] + ".parquet_staging")
pdf_dir = Path(os.environ["PZ_HATS_DIR"] + ".pdf")

summary_rows = sum(
    pq.read_metadata(path).num_rows
    for path in staging.glob("*.parquet")
    if path.name != "pz_pdf_xvals.parquet"
)
pdf_rows = sum(
    pq.read_metadata(path).num_rows
    for path in pdf_dir.glob("*pdf-part*.parquet")
)

print("summary rows:", summary_rows)
print("PDF rows:", pdf_rows)
assert summary_rows == pdf_rows
PY
```

## 8. Expected Outputs

The stage 3 run is successful when:

- `pz-build-hats` finishes without an exception;
- `$PZ_HATS_DIR/pz_summary` is readable with `lsdb.read_hats`;
- `$PZ_HATS_DIR.parquet_staging/pz_pdf_xvals.parquet` exists;
- the summary staging row count matches the total stage 2 HDF5 row count;
- if enabled, `$PZ_HATS_DIR.pdf/xvals.parquet` exists;
- if enabled, the PDF product row count matches the summary row count;
- Dask worker logs do not contain unresolved tracebacks or memory failures.
