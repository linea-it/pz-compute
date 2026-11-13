# Local development setup

This document describes a local setup for developing and inspecting
`pz-compute` without access to LIneA Slurm. The goal is not to reproduce the
cluster exactly. The goal is to run the same `rail-estimate` scripts, generate
small HDF5 outputs, inspect them, and optionally exercise the local dispatcher
with a small Slurm mock before final validation on the cluster.

## Recommended workflow

Use two local test layers:

1. Run `rail-estimate` directly on one small input file.
2. Run a small multi-file directory through `pz-compute.batch` using mocked
   `srun` and `scontrol`.

For development of new output products or post-processing steps, first produce
normal per-file RAIL outputs, then convert or merge those outputs in a separate
local step. This keeps the current process-per-input parallelization intact.

## Environment

Create a local conda environment:

```bash
conda create -n pz-compute-local python=3.12 pip
conda activate pz-compute-local
```

Install the packages used by the current scripts:

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

The `hdf5` conda package provides command-line inspection tools such as
`h5dump`. On Ubuntu/Debian outside conda, the equivalent system package is:

```bash
sudo apt install hdf5-tools
```

Install RAIL and packages useful for local distributed/post-processing work:

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

From the repository root, configure the repository paths:

```bash
export REPO_DIR=${REPO_DIR:-$(pwd)}
export PATH="$REPO_DIR/rail_scripts:$REPO_DIR/scheduler_scripts/slurm:$PATH"
export PYTHONPATH="$REPO_DIR/rail_scripts:$REPO_DIR/scheduler_scripts/slurm:${PYTHONPATH:-}"
```

Check imports:

```bash
python - <<'PY'
import dask.dataframe as dd
import distributed
import h5py
import hats
import lsdb
import pandas
import pyarrow
import tables_io

print("local pz-compute development environment is importable")
PY
```

## Direct rail-estimate smoke test

Create a local run directory:

```bash
cd "$REPO_DIR"
export PZ_LOCAL_RUN="$REPO_DIR/local-runs/smoke-001"
mkdir -p "$PZ_LOCAL_RUN/input" "$PZ_LOCAL_RUN/output" "$PZ_LOCAL_RUN/log"
cd "$PZ_LOCAL_RUN"
```

Use the tiny DES DR2-like fixtures in `data/`. These files are better local
development inputs than the generic RAIL examples because they include
coordinates and an object identifier:

- `data/tiny_training_set_for_tests_des_dr2.hdf5`: training set with
  `coadd_object_id`, `ra`, `dec`, magnitudes, magnitude errors, and `redshift`.
- `data/tiny_object_catalog_for_tests_des_dr2.hdf5`: object catalog with
  `coadd_object_id`, `ra`, `dec`, magnitudes, and magnitude errors.

```bash
cd "$PZ_LOCAL_RUN"
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

Link the object catalog into `input/`:

```bash
cd "$PZ_LOCAL_RUN"
ln -sfn "$PZ_TINY_OBJECT_HDF5" input/tiny_object_catalog_for_tests_des_dr2.hdf5
```

Generate a local estimator:

```bash
cd "$PZ_LOCAL_RUN"
rail-train \
    "$PZ_TINY_TRAINING_HDF5" \
    estimator_fzboost.pkl \
    --algorithm=fzboost
```

Run a single estimate:

```bash
cd "$PZ_LOCAL_RUN"
rail-estimate \
    input/tiny_object_catalog_for_tests_des_dr2.hdf5 \
    output/tiny_object_catalog_for_tests_des_dr2.hdf5 \
    --algorithm=fzboost \
    --calibration-file=estimator_fzboost.pkl
```

Inspect the output:

```bash
cd "$PZ_LOCAL_RUN"
h5dump -H output/tiny_object_catalog_for_tests_des_dr2.hdf5
```

Or from Python:

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

This is the first thing to use when designing a converter, because it shows the
real output groups, datasets, shapes, and dtypes produced by RAIL.

## Local directory run without Slurm

Before mocking Slurm, a plain shell loop is often enough to debug data handling:

```bash
cd "$PZ_LOCAL_RUN"
mkdir -p loop-output loop-log

find input -type f | sort | while read -r input_file; do
    rel="${input_file#input/}"
    output_file="loop-output/${rel}"
    mkdir -p "$(dirname "$output_file")"
    mkdir -p "$(dirname "loop-log/${rel}.out")"

    rail-estimate \
        "$input_file" \
        "$output_file" \
        --algorithm=fzboost \
        --calibration-file=estimator_fzboost.pkl \
        > "loop-log/${rel}.out" \
        2> "loop-log/${rel}.err"
done
```

This does not exercise retry logic or task dispatching, but it produces the same
kind of per-input output files that a post-processing step should consume.

## Optional local Slurm mock

Use this only on Linux. It exercises `pz-compute.batch` locally by providing
minimal `srun` and `scontrol` replacements.

Create mock Slurm commands:

```bash
cd "$PZ_LOCAL_RUN"
mkdir -p mock-slurm/bin

cat > mock-slurm/bin/scontrol <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "show" ] && [ "$2" = "hostnames" ]; then
    hostname
else
    echo "unsupported mock scontrol command: $*" >&2
    exit 1
fi
EOF

cat > mock-slurm/bin/srun <<'EOF'
#!/usr/bin/env bash
stdout=
stderr=

while [ "$#" -gt 0 ]; do
    case "$1" in
        --output)
            stdout="$2"
            shift 2
            ;;
        --error)
            stderr="$2"
            shift 2
            ;;
        -w|-n|-N|-c)
            shift 2
            ;;
        --cpu-bind=*)
            shift
            ;;
        --*)
            shift
            ;;
        -*)
            shift
            ;;
        *)
            break
            ;;
    esac
done

if [ -n "$stdout" ]; then
    mkdir -p "$(dirname "$stdout")"
fi
if [ -n "$stderr" ]; then
    mkdir -p "$(dirname "$stderr")"
fi

if [ "$(basename "${1:-}")" = "pz-compute.run" ]; then
    shift 4
fi

if [ -n "$stdout" ] && [ -n "$stderr" ]; then
    "$@" > "$stdout" 2> "$stderr"
elif [ -n "$stdout" ]; then
    "$@" > "$stdout"
elif [ -n "$stderr" ]; then
    "$@" 2> "$stderr"
else
    "$@"
fi
EOF

chmod +x mock-slurm/bin/scontrol mock-slurm/bin/srun
```

Run the dispatcher locally:

```bash
cd "$PZ_LOCAL_RUN"
mkdir -p slurm-output

export PATH="$PWD/mock-slurm/bin:$REPO_DIR/rail_scripts:$REPO_DIR/scheduler_scripts/slurm:$PATH"
export PYTHONPATH="$REPO_DIR/rail_scripts:$REPO_DIR/scheduler_scripts/slurm:${PYTHONPATH:-}"
export SLURM_NTASKS=2
export SLURM_TASKS_PER_NODE=2
export SLURM_JOB_CPUS_PER_NODE="$(nproc)"

pz-compute.batch \
    input \
    slurm-output \
    --algorithm=fzboost \
    --calibration-file=estimator_fzboost.pkl
```

This path is useful for checking that:

- `pz-compute.batch` discovers inputs recursively.
- outputs mirror the input directory layout.
- per-task logs are created under `log/`.
- failures are visible in task logs.

It is not a substitute for Slurm validation. Final CPU affinity, `srun`
behavior, and filesystem performance must still be tested at LIneA.

## Post-processing development target

For new post-processing support, first write a converter that accepts the
existing local output layout:

```text
input/
output/, loop-output/, or slurm-output/
loop-log/ or log/
```

The converter should:

1. Read each output HDF5 file.
2. Read the corresponding input HDF5 file, using the same relative path, to get
   `ra`, `dec`, and an object identifier.
3. Verify that input and output row counts match.
4. Build a tabular dataframe with coordinates, identifiers, and PZ output
   columns.
5. Stage any intermediate files needed by the target format.
6. Build the final product.

Keep this converter runnable outside Slurm first. Once it works locally, call it
once at the end of `pz-compute.batch`, after all per-file `rail-estimate` tasks
finish successfully.
