# pz-build-hats local end-to-end test

This document is a linear local test for the first HATS output implementation.
It uses only the small fixtures in `data/`, generates a local estimator, runs
`rail-estimate`, builds the HATS summary with `hats-import`, writes the full
PDF parquet product, and inspects both outputs.

Run the commands block by block from the repository root unless a block changes
directory explicitly.

## Environment

Create and activate a dedicated conda environment:

```bash
conda create -y -n pz-compute-hats-e2e python=3.12 pip
conda activate pz-compute-hats-e2e
```

Install the base packages:

```bash
conda install -y -c conda-forge \
    h5py \
    pyyaml \
    pandas \
    matplotlib \
    psutil \
    cython \
    mpi4py \
    numexpr \
    pyviz_comms \
    dask \
    distributed \
    dask-jobqueue \
    joblib \
    scikit-learn \
    scikit-learn-intelex \
    fitsio \
    pytdigest \
    scipy \
    docopt \
    pyxdg \
    pyarrow \
    tables-io \
    astropy \
    hdf5 \
    pip
```

Install RAIL and the HATS tooling:

```bash
pip install \
    pz-rail \
    pz-rail-bpz \
    pz-rail-flexzboost \
    pz-rail-tpz \
    pz-rail-gpz-v1 \
    pz-rail-lephare \
    flexcode \
    lsdb \
    hats-import \
    hats
```

Configure the local repository scripts:

```bash
export REPO_DIR=${REPO_DIR:-$(pwd)}
export PATH="$REPO_DIR/rail_scripts:$REPO_DIR/scheduler_scripts/slurm:$PATH"
export PYTHONPATH="$REPO_DIR/rail_scripts:$REPO_DIR/scheduler_scripts/slurm:${PYTHONPATH:-}"
export MPLCONFIGDIR=/tmp/matplotlib-pz-build-hats
export XDG_CACHE_HOME=/tmp/pz-build-hats-cache
```

Check the imports:

```bash
python - <<'PY'
import distributed
import h5py
import hats
import hats_import
import lsdb
import pyarrow
import rail
import tables_io

print("local HATS e2e environment is importable")
PY
```

## Run Directory

Create an isolated local run directory:

```bash
cd "$REPO_DIR"
export PZ_LOCAL_RUN="$REPO_DIR/local-runs/pz-build-hats-e2e-local"
mkdir -p "$PZ_LOCAL_RUN/input" "$PZ_LOCAL_RUN/output" "$PZ_LOCAL_RUN/log"
cd "$PZ_LOCAL_RUN"
```

Use the repository fixtures:

```bash
export PZ_TINY_TRAINING_HDF5="$REPO_DIR/data/tiny_training_set_for_tests_des_dr2.hdf5"
export PZ_TINY_OBJECT_HDF5="$REPO_DIR/data/tiny_object_catalog_for_tests_des_dr2.hdf5"

python - <<'PY'
import tables_io
from os import environ

for label, path in [
    ("training", environ["PZ_TINY_TRAINING_HDF5"]),
    ("object", environ["PZ_TINY_OBJECT_HDF5"]),
]:
    df = tables_io.read(path, tables_io.types.PD_DATAFRAME)
    print(label, path)
    print("shape:", df.shape)
    print("columns:", list(df.columns))
    print()
PY
```

Link the object catalog into the input directory:

```bash
cd "$PZ_LOCAL_RUN"
ln -sfn "$PZ_TINY_OBJECT_HDF5" input/tiny_object_catalog_for_tests_des_dr2.hdf5
```

## Generate Estimator

Generate a local `fzboost` estimator from the tiny training fixture:

```bash
cd "$PZ_LOCAL_RUN"
rail-train \
    "$PZ_TINY_TRAINING_HDF5" \
    estimator_fzboost.pkl \
    --algorithm=fzboost
```

Confirm the file exists:

```bash
cd "$PZ_LOCAL_RUN"
ls -lh estimator_fzboost.pkl
```

## Run rail-estimate

Run the estimator on the tiny object catalog:

```bash
cd "$PZ_LOCAL_RUN"
rail-estimate \
    input/tiny_object_catalog_for_tests_des_dr2.hdf5 \
    output/tiny_object_catalog_for_tests_des_dr2.hdf5 \
    --algorithm=fzboost \
    --calibration-file=estimator_fzboost.pkl
```

Inspect the output HDF5:

```bash
cd "$PZ_LOCAL_RUN"
python - <<'PY'
import h5py

with h5py.File("output/tiny_object_catalog_for_tests_des_dr2.hdf5", "r") as handle:
    def show(name, obj):
        if hasattr(obj, "shape"):
            print(name, obj.shape, obj.dtype)
    handle.visititems(show)
PY
```

The output must contain:

```text
meta/xvals
data/yvals
```

## Build HATS With hats-import and Local Dask

Force the `hats-import` path by setting `--fast-path-size-mb=0`. This command
sets every local Dask cluster option explicitly.

```bash
cd "$PZ_LOCAL_RUN"
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
    pz-summary-hats-local
```

Expected outputs:

```text
pz-summary-hats-local/
pz-summary-hats-local.pdf/
pz-summary-hats-local.parquet_staging/
```

## Inspect Results

Inspect the HATS summary:

```bash
cd "$PZ_LOCAL_RUN"
python - <<'PY'
import lsdb

catalog = lsdb.read_hats("pz-summary-hats-local/pz_summary")
print(catalog.head(5))
PY
```

Inspect the full PDF parquet product:

```bash
cd "$PZ_LOCAL_RUN"
python - <<'PY'
from pathlib import Path
import pyarrow.parquet as pq

pdf_dir = Path("pz-summary-hats-local.pdf")
parts = sorted(pdf_dir.glob("*pdf-part*.parquet"))
if not parts:
    raise SystemExit("No PDF parquet parts found")

table = pq.read_table(parts[0])
xvals = pq.read_table(pdf_dir / "xvals.parquet")

print("PDF part:", parts[0])
print(table.schema)
print("rows in first PDF part:", table.num_rows)
print("bins in first PDF vector:", len(table.column("pdf")[0].as_py()))
print("xvals schema:", xvals.schema)
print("xvals rows:", xvals.num_rows)
PY
```

Check that summary rows and PDF rows match:

```bash
cd "$PZ_LOCAL_RUN"
python - <<'PY'
from pathlib import Path
import lsdb
import pyarrow.parquet as pq

summary = lsdb.read_hats("pz-summary-hats-local/pz_summary").compute()
pdf_rows = sum(
    pq.read_metadata(path).num_rows
    for path in Path("pz-summary-hats-local.pdf").glob("*pdf-part*.parquet")
)

print("summary rows:", len(summary))
print("PDF rows:", pdf_rows)
assert len(summary) == pdf_rows
PY
```

## Success Criteria

The local e2e test is successful when:

- `rail-train` writes `estimator_fzboost.pkl`.
- `rail-estimate` writes an HDF5 output with `meta/xvals` and `data/yvals`.
- `pz-build-hats` logs `Starting local Dask cluster for hats-import`.
- `lsdb.read_hats("pz-summary-hats-local/pz_summary")` returns rows.
- `pz-summary-hats-local.pdf` contains PDF parquet parts and `xvals.parquet`.
- the HATS summary row count matches the PDF product row count.
