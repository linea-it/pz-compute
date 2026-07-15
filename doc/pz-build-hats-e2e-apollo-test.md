# pz-build-hats Apollo end-to-end test

This document is a linear Apollo/LIneA test for the first HATS output
implementation. It keeps small scripts, source code, conda environments, and
caches under `/scripts`, and keeps run inputs, output HDF5 files, HATS products,
PDF products, and logs under `/scratch`.

The test uses the small fixtures in `data/`, generates an `fzboost` estimator,
runs `rail-estimate` through Slurm, builds the HATS summary with `hats-import`
and a Slurm Dask cluster, and inspects both outputs.

## Login

Access Apollo from a terminal or JupyterHub terminal:

```bash
ssh loginapl01
```

Load conda or miniconda if your shell does not already do it. The exact command
depends on your Apollo account configuration.

## Shell Setup

Add the following block to `~/.bashrc` if it is not already present:

```bash
if [ -d /scripts/`whoami` ]; then
  export ALTHOME=/scripts/`whoami`/slurm-home
  export PATH=$PATH:${ALTHOME}/bin
  export LD_LIBRARY_PATH=${LD_LIBRARY_PATH:+${LD_LIBRARY_PATH}:}${ALTHOME}/lib
  export XDG_DATA_HOME=${ALTHOME}/share
  export XDG_CONFIG_HOME=${ALTHOME}/etc
  export XDG_STATE_HOME=${ALTHOME}/var
  export XDG_CACHE_HOME=${ALTHOME}/var/cache
fi
```

Reload the shell setup:

```bash
source ~/.bashrc
```

## Install Under /scripts

Define installation and run roots:

```bash
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_hats_e2e

mkdir -p "$PZ_INSTALL_ROOT" "$PZ_SRC_DIR" "$PZ_RUN_ROOT" "$SCRIPTS/bin"
mkdir -p "$PZ_INSTALL_ROOT/conda_pkgs" "$PZ_INSTALL_ROOT/pip_cache"

export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
```

Clone or update `pz-compute` under `/scripts`:

```bash
cd "$PZ_SRC_DIR"

if [ ! -d pz-compute ]; then
    git clone https://github.com/linea-it/pz-compute
fi

cd "$PZ_COMPUTE_DIR"
git status --short
```

Create and activate the conda environment:

```bash
conda create -y --prefix "$PZ_CONDA_ENV" python=3.12 pip
conda activate "$PZ_CONDA_ENV"
```

Install the base RAIL dependencies:

```bash
PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT" "$PZ_COMPUTE_DIR/rail_scripts/install-pz-rail"
```

When prompted by `install-pz-rail`, type:

```text
yes
```

Install the extra packages needed by `pz-build-hats`:

```bash
conda install -y -c conda-forge \
    pyarrow \
    tables-io \
    astropy \
    hdf5
```

Install the HATS packages with pip:

```bash
pip install lsdb hats-import hats
```

Create script links under `/scripts/$(whoami)/bin`:

```bash
ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" "$SCRIPTS/bin/rail-estimate"
ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/rail-train" "$SCRIPTS/bin/rail-train"
ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/rail-preprocess-parquet" "$SCRIPTS/bin/rail-preprocess-parquet"
ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/pz-build-hats" "$SCRIPTS/bin/pz-build-hats"

chmod +x "$SCRIPTS/bin/rail-estimate"
chmod +x "$SCRIPTS/bin/rail-train"
chmod +x "$SCRIPTS/bin/rail-preprocess-parquet"
chmod +x "$SCRIPTS/bin/pz-build-hats"
```

Create an environment loader:

```bash
cat > "$PZ_INSTALL_ROOT/env-hats-e2e.sh" <<'EOF'
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_hats_e2e
export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
export PATH=$SCRIPTS/bin:$PZ_COMPUTE_DIR/rail_scripts:$PATH
export PYTHONPATH=$PZ_COMPUTE_DIR/rail_scripts:$PZ_COMPUTE_DIR/scheduler_scripts/slurm:${PYTHONPATH:-}
export DUSTMAPS_CONFIG_FNAME=$PZ_COMPUTE_DIR/rail_scripts/dustmaps_config.json
conda activate "$PZ_CONDA_ENV"
EOF

chmod +x "$PZ_INSTALL_ROOT/env-hats-e2e.sh"
source "$PZ_INSTALL_ROOT/env-hats-e2e.sh"
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
import rail
import tables_io

print("Apollo HATS e2e environment is importable")
PY
```

## Run Directory Under /scratch

Create an isolated run directory under `/scratch`:

```bash
source /scripts/$(whoami)/ondemand/env-hats-e2e.sh

export RUN_ID=pz-build-hats-e2e-apollo
export PZ_APOLLO_RUN=$PZ_RUN_ROOT/$RUN_ID

mkdir -p "$PZ_APOLLO_RUN/input" "$PZ_APOLLO_RUN/output" "$PZ_APOLLO_RUN/log"
cd "$PZ_APOLLO_RUN"
```

Link the repository fixtures into the scratch run:

```bash
export PZ_TINY_TRAINING_HDF5="$PZ_COMPUTE_DIR/data/tiny_training_set_for_tests_des_dr2.hdf5"
export PZ_TINY_OBJECT_HDF5="$PZ_COMPUTE_DIR/data/tiny_object_catalog_for_tests_des_dr2.hdf5"

ln -sfn "$PZ_TINY_OBJECT_HDF5" input/tiny_object_catalog_for_tests_des_dr2.hdf5
```

Inspect the fixture schema:

```bash
cd "$PZ_APOLLO_RUN"
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

## Generate Estimator

Generate the estimator in the scratch run directory:

```bash
cd "$PZ_APOLLO_RUN"
rail-train \
    "$PZ_TINY_TRAINING_HDF5" \
    estimator_fzboost.pkl \
    --algorithm=fzboost
```

Confirm the estimator exists:

```bash
cd "$PZ_APOLLO_RUN"
ls -lh estimator_fzboost.pkl
```

## Run rail-estimate Through Slurm

Copy the Slurm launcher files into the scratch run:

```bash
cd "$PZ_APOLLO_RUN"
ln -sfn "$PZ_COMPUTE_DIR/scheduler_examples/slurm/rail-slurm/rail-slurm.batch" .
ln -sfn "$PZ_COMPUTE_DIR/scheduler_examples/slurm/rail-slurm/rail-slurm.py" .
cc -o slurm-shield "$PZ_COMPUTE_DIR/utils/slurm/slurm-shield.c"
```

Submit a small Slurm job. The fixture has one input file, so this test does not
need many tasks:

```bash
cd "$PZ_APOLLO_RUN"
sbatch \
    --job-name=pz-e2e-estimate \
    --partition=cpu \
    --time=00:30:00 \
    --nodes=1 \
    --ntasks=2 \
    --mem-per-cpu=2140M \
    rail-slurm.batch \
    input \
    output \
    fzboost
```

Watch the job:

```bash
squeue -u "$(whoami)"
```

After the job finishes, inspect logs and output:

```bash
cd "$PZ_APOLLO_RUN"
find log -maxdepth 3 -type f -print | sort
find output -type f -print | sort

python - <<'PY'
import h5py

path = "output/tiny_object_catalog_for_tests_des_dr2.hdf5"
with h5py.File(path, "r") as handle:
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

## Build HATS With Dask Staging and hats-import

Force the `hats-import` path by setting `--fast-path-size-mb=0`. This command
sets the Slurm Dask options that are required or useful for this e2e test. The
same Slurm Dask cluster is used for HDF5-to-parquet staging and for
`hats-import`.

Adjust `--slurm-queue`, `--slurm-account`, memory, and walltime if your Apollo
allocation requires different values.

```bash
cd "$PZ_APOLLO_RUN"
mkdir -p log/dask

pz-build-hats \
    --overwrite \
    --fast-path-size-mb=0 \
    --use-hats-import \
    --dask-cluster=slurm \
    --slurm-queue=cpu \
    --slurm-account=hpc-public \
    --slurm-cores=2 \
    --slurm-memory=8GB \
    --slurm-walltime=00:30:00 \
    --slurm-minimum-jobs=1 \
    --slurm-maximum-jobs=2 \
    --slurm-log-dir=log/dask \
    input \
    output \
    pz-summary-hats-apollo
```

This relies on these defaults:

```text
--staging-dir=<hats_dir>.parquet_staging
--pdf-output-dir=<hats_dir>.pdf
--pdf-dtype=float32
--batch-size=50000
--catalog-name=pz_summary
--slurm-processes=1
--slurm-adapt-interval=10
--slurm-scale-down-delay=180
```

The input columns are detected automatically for this fixture:

```text
object id: coadd_object_id
ra: ra
dec: dec
```

Use `--input-group=<group>` only when the input object columns are inside an
HDF5 group instead of the file root. The tiny DES DR2 fixture used here stores
the columns at the root, so `--input-group` is not needed.

If your Apollo allocation uses a different Slurm account, replace
`hpc-public`:

```bash
--slurm-account=<account>
```

Expected outputs under `/scratch`:

```text
$PZ_APOLLO_RUN/pz-summary-hats-apollo/
$PZ_APOLLO_RUN/pz-summary-hats-apollo.pdf/
$PZ_APOLLO_RUN/pz-summary-hats-apollo.parquet_staging/
$PZ_APOLLO_RUN/log/dask/
```

## Inspect Results

Inspect the HATS summary:

```bash
cd "$PZ_APOLLO_RUN"
python - <<'PY'
import lsdb

catalog = lsdb.read_hats("pz-summary-hats-apollo/pz_summary")
print(catalog.head(5))
PY
```

Inspect the full PDF parquet product:

```bash
cd "$PZ_APOLLO_RUN"
python - <<'PY'
from pathlib import Path
import pyarrow.parquet as pq

pdf_dir = Path("pz-summary-hats-apollo.pdf")
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
cd "$PZ_APOLLO_RUN"
python - <<'PY'
from pathlib import Path
import lsdb
import pyarrow.parquet as pq

summary = lsdb.read_hats("pz-summary-hats-apollo/pz_summary").compute()
pdf_rows = sum(
    pq.read_metadata(path).num_rows
    for path in Path("pz-summary-hats-apollo.pdf").glob("*pdf-part*.parquet")
)

print("summary rows:", len(summary))
print("PDF rows:", pdf_rows)
assert len(summary) == pdf_rows
PY
```

Inspect Dask worker logs:

```bash
cd "$PZ_APOLLO_RUN"
find log/dask -type f -print | sort
```

## Success Criteria

The Apollo e2e test is successful when:

- source, conda environment, package caches, and helper scripts are under
  `/scripts/$(whoami)`.
- run inputs, `rail-estimate` outputs, HATS products, PDF products, and logs
  are under `/scratch/users/$(whoami)/pz-compute-runs/$RUN_ID`.
- `rail-train` writes `estimator_fzboost.pkl`.
- the Slurm `rail-slurm.batch` job writes the expected HDF5 output.
- `pz-build-hats` logs `Starting Slurm Dask cluster for pz-build-hats`.
- `pz-build-hats` logs `Converting ... HDF5 pairs with Dask staging tasks`.
- `lsdb.read_hats("pz-summary-hats-apollo/pz_summary")` returns rows.
- `pz-summary-hats-apollo.pdf` contains PDF parquet parts and `xvals.parquet`.
- the HATS summary row count matches the PDF product row count.
