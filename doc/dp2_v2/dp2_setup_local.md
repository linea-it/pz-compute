# DP2 GAaP 1.0: common local setup

Run this setup once before following the three DP2 stages. It clones
`pz-compute`, creates the shared directories and prepares two conda
environments:

- `pz_compute_dp2_gaap1p0` is the frozen scientific environment used by both
  Stage 1 training and Stage 2 estimation;
- `pz_compute_dp2_stage3_hats` contains the additional HATS dependencies used
  by Stage 3 and does not modify the scientific environment.

The full Stage 2 catalog run and the distributed Stage 3 production build are
intended for Apollo. Locally, Stage 1 can be run in full when the machine has
enough CPU and memory; Stages 2 and 3 provide reduced end-to-end paths using
one or two downloaded Object shards.

## 1. Choose the local root and clone the repository

Choose one absolute directory outside an existing repository checkout:

```bash
export PZ_LOCAL_ROOT=/path/to/pz-dp2-work
export PZ_INSTALL_ROOT=$PZ_LOCAL_ROOT/software
export PZ_SRC_DIR=$PZ_LOCAL_ROOT/src
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$PZ_LOCAL_ROOT/runs
export PZ_BIN_DIR=$PZ_INSTALL_ROOT/bin

mkdir -p "$PZ_INSTALL_ROOT" "$PZ_SRC_DIR" "$PZ_RUN_ROOT" "$PZ_BIN_DIR"
mkdir -p "$PZ_INSTALL_ROOT/conda_pkgs" "$PZ_INSTALL_ROOT/pip_cache"

export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache

if [ ! -d "$PZ_COMPUTE_DIR/.git" ]; then
    git clone https://github.com/linea-it/pz-compute "$PZ_COMPUTE_DIR"
fi

cd "$PZ_COMPUTE_DIR"
git status --short
```

Before installing, check out the repository revision that will be used for all
three stages. Do not change revisions between Stage 1 and Stage 2 without
revalidating the environment and regenerating the model.

## 2. Create the Stage 1/Stage 2 scientific environment

Conda or Miniconda must already be available in the shell.

```bash
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp2_gaap1p0

if [ ! -d "$PZ_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_CONDA_ENV" python=3.12 pip
fi

conda activate "$PZ_CONDA_ENV"
PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT" "$PZ_COMPUTE_DIR/rail_scripts/install-pz-rail"
```

When prompted by `install-pz-rail`, confirm with `yes`. Then install the I/O
packages used by the DP2 workflow:

```bash
conda install -y --prefix "$PZ_CONDA_ENV" -c conda-forge \
    pyarrow tables-io hdf5 h5py
```

Run the installation only when intentionally creating or updating the shared
scientific environment. Once training begins, keep this environment unchanged
until Stage 2 is complete.

## 3. Create the Stage 3 HATS environment

```bash
export PZ_STAGE3_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp2_stage3_hats

if [ ! -d "$PZ_STAGE3_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_STAGE3_CONDA_ENV" python=3.12 pip
fi

conda install -y --prefix "$PZ_STAGE3_CONDA_ENV" -c conda-forge \
    numpy pyarrow hdf5 h5py astropy distributed dask-jobqueue docopt \
    pyyaml pyxdg

"$PZ_STAGE3_CONDA_ENV/bin/python" -m pip install lsdb hats-import hats
```

## 4. Create command links and environment loaders

```bash
for command in rail-train rail-estimate pz-build-hats; do
    ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/$command" "$PZ_BIN_DIR/$command"
    chmod +x "$PZ_BIN_DIR/$command"
done
```

Create the loader used by Stages 1 and 2:

```bash
cat > "$PZ_INSTALL_ROOT/env-dp2-gaap1p0.sh" <<EOF
export PZ_LOCAL_ROOT="$PZ_LOCAL_ROOT"
export PZ_PLATFORM="local"
export PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT"
export PZ_SRC_DIR="$PZ_SRC_DIR"
export PZ_COMPUTE_DIR="$PZ_COMPUTE_DIR"
export PZ_RUN_ROOT="$PZ_RUN_ROOT"
export PZ_BIN_DIR="$PZ_BIN_DIR"
export PZ_CONDA_ENV="$PZ_CONDA_ENV"
export CONDA_PKGS_DIRS="$PZ_INSTALL_ROOT/conda_pkgs"
export PIP_CACHE_DIR="$PZ_INSTALL_ROOT/pip_cache"
export PZ_PY="$PZ_CONDA_ENV/bin/python"
export PATH="$PZ_CONDA_ENV/bin:$PZ_BIN_DIR:$PZ_COMPUTE_DIR/rail_scripts:\$PATH"
export PYTHONPATH="$PZ_COMPUTE_DIR/rail_scripts:\${PYTHONPATH:-}"
EOF

chmod +x "$PZ_INSTALL_ROOT/env-dp2-gaap1p0.sh"
```

Create the independent Stage 3 loader:

```bash
cat > "$PZ_INSTALL_ROOT/env-dp2-stage3-hats.sh" <<EOF
export PZ_LOCAL_ROOT="$PZ_LOCAL_ROOT"
export PZ_PLATFORM="local"
export PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT"
export PZ_SRC_DIR="$PZ_SRC_DIR"
export PZ_COMPUTE_DIR="$PZ_COMPUTE_DIR"
export PZ_RUN_ROOT="$PZ_RUN_ROOT"
export PZ_BIN_DIR="$PZ_BIN_DIR"
export PZ_STAGE3_CONDA_ENV="$PZ_STAGE3_CONDA_ENV"
export CONDA_PKGS_DIRS="$PZ_INSTALL_ROOT/conda_pkgs"
export PIP_CACHE_DIR="$PZ_INSTALL_ROOT/pip_cache"
export PZ_PY="$PZ_STAGE3_CONDA_ENV/bin/python"
export PATH="$PZ_STAGE3_CONDA_ENV/bin:$PZ_BIN_DIR:$PZ_COMPUTE_DIR/rail_scripts:\$PATH"
export PYTHONPATH="$PZ_COMPUTE_DIR/rail_scripts:\${PYTHONPATH:-}"
EOF

chmod +x "$PZ_INSTALL_ROOT/env-dp2-stage3-hats.sh"
```

Neither loader calls `conda activate`; both select their environment by placing
its `bin` directory first in `PATH` and by defining `PZ_PY` explicitly.

## 5. Validate both environments

Replace `/path/to/pz-dp2-work` below with the same root selected in Section 1.

```bash
source /path/to/pz-dp2-work/software/env-dp2-gaap1p0.sh
cd "$PZ_COMPUTE_DIR"

"$PZ_PY" - <<'PY'
import flexcode
import pyarrow
import rail
import sklearn
import tables_io
import xgboost

print("Stage 1/Stage 2 environment is importable")
PY

"$PZ_PY" -m pip freeze > "$PZ_INSTALL_ROOT/dp2-gaap1p0-setup-freeze.txt"
git rev-parse HEAD > "$PZ_INSTALL_ROOT/pz-compute-revision.txt"
```

```bash
source /path/to/pz-dp2-work/software/env-dp2-stage3-hats.sh
cd "$PZ_COMPUTE_DIR"

"$PZ_PY" - <<'PY'
import dask_jobqueue
import distributed
import hats
import hats_import
import h5py
import lsdb
import pyarrow

print("Stage 3 environment is importable")
PY

"$PZ_PY" -m pip freeze > "$PZ_INSTALL_ROOT/dp2-stage3-hats-setup-freeze.txt"
```

After this one-time setup, each stage only needs to source the appropriate
loader and change to `$PZ_COMPUTE_DIR`.

Continue with:

1. [Stage 1: train the GAaP 1.0 model](dp2_stage1_train_instructions_clipped.md)
2. [Stage 2: estimate DP2 photo-z values](dp2_stage2_estimate_instructions_clipped.md)
3. [Stage 3: build the HATS products](dp2_stage3_build_hats.md)
