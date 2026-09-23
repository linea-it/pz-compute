# DP1 GAaP 1.0 FlexZBoost Stage 3: Build HATS Products

This document describes how to build HATS photo-z products after the DP1
GAaP 1.0 matched-v4 stage 2 estimation has completed.

The stage 2 output is a tree of `rail-estimate` HDF5 files:

```text
$PZ_STAGE2_RUN/output/<same-relative-path-as-input>.hdf5
```

The original DP1 parquet catalog is used as the input identity catalog:

```text
/data/cl/lsst/dp1/secondary/catalogs/skinny_collection/mag/gaap1p0/sfd/catalog/dataset
```

`pz-build-hats` matches the two trees by relative path, replacing the input
`.parquet` suffix with `.hdf5`. For example:

```text
input:  <subdirectories>/Npix=448.parquet
output: <subdirectories>/Npix=448.hdf5
```

The HDF5 output does not store `objectId`. The association is positional: row
`i` in the input parquet is matched to row `i` in `data/yvals` from the
corresponding HDF5 output. The stage 2 conversion preserves this row order.

## 0. Requirements

Run these commands on Apollo from a terminal or JupyterHub terminal.

Use a `pz-compute` checkout that includes parquet input support in
`rail_scripts/pz-build-hats`. This support is required because the DP1 stage 2
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

Start with the environment created in
`dp1_stage2_estimate_instructions_matched_v4.md`:

```bash
source /scripts/$(whoami)/ondemand/env-dp1-gaap1p0-estimate.sh
```

If that environment does not already include the HATS packages, install them:

```bash
conda install -y --prefix "$PZ_CONDA_ENV" -c conda-forge \
    pyarrow \
    hdf5 \
    h5py \
    astropy \
    distributed \
    dask-jobqueue

"$PZ_CONDA_ENV/bin/python" -m pip install lsdb hats-import hats
```

Make sure `pz-build-hats` is available:

```bash
export SCRIPTS=/scripts/$(whoami)
export PZ_COMPUTE_DIR=$SCRIPTS/pz-compute

ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/pz-build-hats" "$SCRIPTS/bin/pz-build-hats"
chmod +x "$SCRIPTS/bin/pz-build-hats"
```

Check the executable and imports:

```bash
command -v pz-build-hats

python - <<'PY'
import dask_jobqueue
import distributed
import hats
import hats_import
import h5py
import lsdb
import pyarrow

print("DP1 stage 3 HATS environment is importable")
PY
```

## 1. Set run variables

Use the production run directory created by stage 2:

```bash
source /scripts/$(whoami)/ondemand/env-dp1-gaap1p0-estimate.sh

export PZ_STAGE2_RUN=$PZ_RUN_ROOT/dp1-stage2-fzboost-gaap1p0-matched-v4
export PZ_DP1_INPUT_DATASET=/data/cl/lsst/dp1/secondary/catalogs/skinny_collection/mag/gaap1p0/sfd/catalog/dataset
export PZ_STAGE2_OUTPUT_DIR=$PZ_STAGE2_RUN/output
export PZ_HATS_DIR=$PZ_STAGE2_RUN/pz-fzboost-gaap1p0-matched-v4-hats

cd "$PZ_STAGE2_RUN"
mkdir -p log/dask-stage3
```

The pilot output tree is excluded. The stage 2 smoke test may have left
`output/smoke-test.hdf5` under the production output root; `pz-build-hats`
ignores it because it has no matching input parquet.

## 2. Validate input and output pairing

Confirm that the input and output roots exist and count their files:

```bash
cd "$PZ_STAGE2_RUN"

test -d "$PZ_DP1_INPUT_DATASET"
test -d "$PZ_STAGE2_OUTPUT_DIR"

echo "input parquets: $(find "$PZ_DP1_INPUT_DATASET" -type f -name '*.parquet' | wc -l)"
echo "output HDF5 files: $(find "$PZ_STAGE2_OUTPUT_DIR" -type f -name '*.hdf5' | wc -l)"
```

Validate that every input parquet has the expected stage 2 HDF5 output. The
script also reports extra HDF5 files, such as `smoke-test.hdf5`, but they do not
participate in the relative-path pairing:

```bash
python - <<'PY'
from pathlib import Path
import os

input_root = Path(os.environ["PZ_DP1_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])

expected = {
    path.relative_to(input_root).with_suffix(".hdf5")
    for path in input_root.glob("**/*.parquet")
}
actual = {
    path.relative_to(output_root)
    for path in output_root.glob("**/*.hdf5")
}

missing = sorted(expected - actual)
unexpected = sorted(actual - expected)

print("expected pairs:", len(expected))
print("stage 2 outputs:", len(actual))
print("missing output files:", len(missing))
for relative in missing[:20]:
    print("missing:", relative)
print("unexpected output files:", len(unexpected))
for relative in unexpected[:20]:
    print("unexpected:", relative)

if missing or not expected:
    raise SystemExit("Stage 2 input/output pairing is incomplete")
PY
```

Validate one pair in detail. This checks the positional-association assumption
and the DP1 redshift grid produced by the matched-v4 model:

```bash
python - <<'PY'
from pathlib import Path
import os

import h5py
import numpy as np
import pyarrow.parquet as pq

input_root = Path(os.environ["PZ_DP1_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])

inputs = sorted(input_root.glob("**/*.parquet"))
if not inputs:
    raise SystemExit("No input parquet files found")

input_path = inputs[0]
relative = input_path.relative_to(input_root)
output_path = output_root / relative.with_suffix(".hdf5")

input_rows = pq.read_metadata(input_path).num_rows
with h5py.File(output_path, "r") as handle:
    xvals = handle["meta/xvals"][:]
    yvals = handle["data/yvals"]
    output_rows, bins = yvals.shape
    finite = bool(np.isfinite(yvals[: min(output_rows, 1000)]).all())

print("input:", input_path)
print("output:", output_path)
print("input rows:", input_rows)
print("output rows:", output_rows)
print("PDF bins:", bins)
print("redshift range:", xvals[0], xvals[-1])
print("sampled PDF values finite:", finite)

if input_rows != output_rows:
    raise SystemExit("Input and output row counts differ")
if xvals.shape != (301,) or bins != 301:
    raise SystemExit("Expected the DP1 301-bin PDF grid")
if not np.isclose(xvals[0], 0.0) or not np.isclose(xvals[-1], 3.0):
    raise SystemExit("Expected the DP1 redshift range 0.0 to 3.0")
if not finite:
    raise SystemExit("Non-finite values found in sampled PDFs")
PY
```

## 3. Run a small staging smoke test

Before building the full products, run `pz-build-hats` on three copied
input/output pairs. This verifies parquet input support, HDF5 PDF reading,
positional matching, DP1 column discovery, and the summary schema.

The removal below affects only the stage 3 smoke directory inside the run:

```bash
cd "$PZ_STAGE2_RUN"

rm -rf -- "$PZ_STAGE2_RUN/stage3-smoke"
mkdir -p stage3-smoke/input stage3-smoke/output

python - <<'PY'
from pathlib import Path
import os
import shutil

input_root = Path(os.environ["PZ_DP1_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])
smoke_root = Path("stage3-smoke")

inputs = sorted(input_root.glob("**/*.parquet"))[:3]
if not inputs:
    raise SystemExit("No input parquet files found")

for input_path in inputs:
    relative = input_path.relative_to(input_root)
    output_path = output_root / relative.with_suffix(".hdf5")
    if not output_path.exists():
        raise SystemExit(f"Missing stage 2 output: {output_path}")

    smoke_input = smoke_root / "input" / relative
    smoke_output = smoke_root / "output" / relative.with_suffix(".hdf5")
    smoke_input.parent.mkdir(parents=True, exist_ok=True)
    smoke_output.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(input_path, smoke_input)
    shutil.copy2(output_path, smoke_output)

print("wrote smoke pairs:", len(inputs))
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
parts = sorted(
    path for path in staging.glob("*.parquet")
    if path.name != "pz_pdf_xvals.parquet"
)
if not parts:
    raise SystemExit("No smoke staging parquet parts found")

table = pq.read_table(parts[0])
xvals = pq.read_table(staging / "pz_pdf_xvals.parquet")
required = {
    "objectId", "coord_ra", "coord_dec", "zmode", "zmean", "zmedian",
    "z_p16", "z_p84",
}
missing = sorted(required - set(table.column_names))

print("summary part:", parts[0])
print(table.schema)
print("rows in first part:", table.num_rows)
print("xvals rows:", xvals.num_rows)
print(table.to_pandas().head())

if missing:
    raise SystemExit(f"Missing summary columns: {missing}")
if xvals.num_rows != 301:
    raise SystemExit(f"Expected 301 DP1 xvals, found {xvals.num_rows}")
PY
```

## 4. Build the full HATS products

Use Slurm Dask mode for the complete DP1 catalog. `--fast-path-size-mb=0`
forces the distributed `hats-import` path instead of the local in-memory LSDB
writer.

The command writes:

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
    "$PZ_DP1_INPUT_DATASET" \
    "$PZ_STAGE2_OUTPUT_DIR" \
    "$PZ_HATS_DIR"
```

The Slurm Dask workers perform two operations:

- convert each parquet/HDF5 pair into summary staging parquet and PDF parquet;
- run `hats-import` to build the final HATS collection from the summary
  staging.

The command enables adaptive scaling, so Apollo may submit additional Dask
worker jobs up to `--slurm-maximum-jobs`. Adjust the queue, account, memory,
walltime, and job limits if required by the current Apollo policy or by an
observed resource limit.

If only the lightweight scalar HATS summary is needed, add:

```bash
--no-pdf-product
```

Keep the PDF product when downstream users need the full 301-value `p(z)`
vectors. The default `--pdf-dtype=float32` substantially reduces their storage
relative to float64.

`--overwrite` replaces an existing HATS directory, staging directory, and PDF
product at the configured paths. Remove that option when an existing build
must be preserved.

## 5. Monitor the build

Watch the main `pz-build-hats` process in its terminal. From another terminal,
watch Dask worker jobs:

```bash
squeue -u "$(whoami)"
```

Inspect worker logs:

```bash
cd "$PZ_STAGE2_RUN"
find log/dask-stage3 -type f -print | sort | tail -50
grep -R "Traceback\\|Error:\\|Killed\\|OOM\\|out of memory" log/dask-stage3 || true
```

If a worker repeatedly exceeds memory, reduce `--slurm-processes` or increase
`--slurm-memory`. If the shared filesystem becomes the bottleneck, reduce
`--slurm-maximum-jobs` before retrying the build.

## 6. Inspect the HATS summary

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

Check the staged summary row count against the complete stage 2 output row
count:

```bash
python - <<'PY'
from pathlib import Path
import os

import h5py
import pyarrow.parquet as pq

input_root = Path(os.environ["PZ_DP1_INPUT_DATASET"])
output_root = Path(os.environ["PZ_STAGE2_OUTPUT_DIR"])
staging = Path(os.environ["PZ_HATS_DIR"] + ".parquet_staging")

output_rows = 0
for input_path in input_root.glob("**/*.parquet"):
    relative = input_path.relative_to(input_root)
    output_path = output_root / relative.with_suffix(".hdf5")
    with h5py.File(output_path, "r") as handle:
        output_rows += handle["data/yvals"].shape[0]

summary_parts = [
    path for path in staging.glob("*.parquet")
    if path.name != "pz_pdf_xvals.parquet"
]
summary_rows = sum(pq.read_metadata(path).num_rows for path in summary_parts)

print("stage 2 output rows:", output_rows)
print("summary staging rows:", summary_rows)
print("summary staging parts:", len(summary_parts))

if not summary_parts:
    raise SystemExit("No summary staging parts found")
if output_rows != summary_rows:
    raise SystemExit("Stage 2 and summary row counts differ")
PY
```

Validate the stored DP1 redshift grid:

```bash
python - <<'PY'
from pathlib import Path
import os

import numpy as np
import pyarrow.parquet as pq

staging = Path(os.environ["PZ_HATS_DIR"] + ".parquet_staging")
table = pq.read_table(staging / "pz_pdf_xvals.parquet")
if table.column_names != ["bin_index", "z"]:
    raise SystemExit(f"Unexpected xvals schema: {table.schema}")
xvals = table.column("z").to_numpy()

print("xvals rows:", len(xvals))
print("redshift range:", xvals[0], xvals[-1])

if len(xvals) != 301:
    raise SystemExit("Expected 301 DP1 redshift bins")
if not np.isclose(xvals[0], 0.0) or not np.isclose(xvals[-1], 3.0):
    raise SystemExit("Expected the DP1 redshift range 0.0 to 3.0")
PY
```

## 7. Inspect the PDF product

Skip this section if the full PDF product was disabled with
`--no-pdf-product`.

```bash
cd "$PZ_STAGE2_RUN"

python - <<'PY'
from pathlib import Path
import os

import pyarrow.parquet as pq

pdf_dir = Path(os.environ["PZ_HATS_DIR"] + ".pdf")
parts = sorted(pdf_dir.glob("*pdf-part*.parquet"))
if not parts:
    raise SystemExit("No PDF parquet parts found")

table = pq.read_table(parts[0])
xvals = pq.read_table(pdf_dir / "xvals.parquet")
pdf = table.column("pdf")[0].as_py()

print("PDF part:", parts[0])
print(table.schema)
print("rows in first PDF part:", table.num_rows)
print("bins in first PDF vector:", len(pdf))
print("xvals rows:", xvals.num_rows)

if len(pdf) != 301 or xvals.num_rows != 301:
    raise SystemExit("Expected 301 bins in the DP1 PDF product")
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

if summary_rows != pdf_rows:
    raise SystemExit("Summary and PDF product row counts differ")
PY
```

## 8. Expected outputs

The stage 3 run is successful when:

- `pz-build-hats` finishes without an exception;
- `$PZ_HATS_DIR/pz_summary` is readable with `lsdb.read_hats`;
- `$PZ_HATS_DIR.parquet_staging/pz_pdf_xvals.parquet` contains the 301-bin
  DP1 grid from `z = 0.0` to `z = 3.0`;
- the summary staging row count matches the total production stage 2 HDF5 row
  count;
- if enabled, `$PZ_HATS_DIR.pdf/xvals.parquet` exists and the PDF vectors have
  301 values;
- if enabled, the PDF product row count matches the summary row count;
- Dask worker logs contain no unresolved tracebacks or memory failures.

The main outputs are:

```text
$PZ_STAGE2_RUN/pz-fzboost-gaap1p0-matched-v4-hats/pz_summary/
$PZ_STAGE2_RUN/pz-fzboost-gaap1p0-matched-v4-hats.parquet_staging/
$PZ_STAGE2_RUN/pz-fzboost-gaap1p0-matched-v4-hats.pdf/
```
