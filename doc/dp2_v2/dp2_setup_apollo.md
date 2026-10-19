# DP2 GAaP 1.0: common Apollo/LineA setup

Run this setup once on the LineA Apollo cluster before following the three DP2
stages. It clones `pz-compute`, defines the shared paths and creates two conda
environments:

- `pz_compute_dp2_gaap1p0` is the frozen scientific environment shared by
  Stage 1 training and Stage 2 estimation;
- `pz_compute_dp2_stage3_hats` contains the additional HATS dependencies used
  only by Stage 3.

Keeping these environments separate prevents Stage 3 package installation from
changing the library versions used to train or load the FlexZBoost pickle.

## 1. Login and shared paths

```bash
ssh loginapl01
```

Conda or Miniconda must be available in the shell. Use `/scripts` for source
code, environments and caches, and `/scratch` for run artifacts:

```bash
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_PLATFORM=apollo
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_BIN_DIR=$SCRIPTS/bin
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp2_gaap1p0
export PZ_STAGE3_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp2_stage3_hats

mkdir -p "$PZ_INSTALL_ROOT" "$PZ_SRC_DIR" "$PZ_RUN_ROOT" "$PZ_BIN_DIR"
mkdir -p "$PZ_INSTALL_ROOT/conda_pkgs" "$PZ_INSTALL_ROOT/pip_cache"

export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
```

## 2. Clone and select the repository revision

```bash
if [ ! -d "$PZ_COMPUTE_DIR/.git" ]; then
    git clone https://github.com/linea-it/pz-compute "$PZ_COMPUTE_DIR"
fi

cd "$PZ_COMPUTE_DIR"
git status --short
```

Check out the repository revision that will be used for all three stages before
installing. Do not change revisions between Stage 1 and Stage 2 without
revalidating the environment and regenerating the model.

## 3. Create the Stage 1/Stage 2 scientific environment

```bash
if [ ! -d "$PZ_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_CONDA_ENV" python=3.12 pip
fi

conda activate "$PZ_CONDA_ENV"
PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT" "$PZ_COMPUTE_DIR/rail_scripts/install-pz-rail"
```

When prompted by `install-pz-rail`, confirm with `yes`. Install the remaining
I/O packages:

```bash
conda install -y --prefix "$PZ_CONDA_ENV" -c conda-forge \
    pyarrow tables-io hdf5 h5py
```

Run the installation only when intentionally creating or updating the shared
scientific environment. Once Stage 1 begins, keep it unchanged until Stage 2
is complete.

## 4. Create the Stage 3 HATS environment

```bash
if [ ! -d "$PZ_STAGE3_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_STAGE3_CONDA_ENV" python=3.12 pip
fi

conda install -y --prefix "$PZ_STAGE3_CONDA_ENV" -c conda-forge \
    numpy pyarrow hdf5 h5py astropy distributed dask-jobqueue docopt

"$PZ_STAGE3_CONDA_ENV/bin/python" -m pip install lsdb hats-import hats
```

## 5. Create command links and environment loaders

```bash
for command in rail-train rail-estimate pz-build-hats; do
    ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/$command" "$PZ_BIN_DIR/$command"
    chmod +x "$PZ_BIN_DIR/$command"
done
```

Create the loader shared by Stages 1 and 2:

```bash
cat > "$PZ_INSTALL_ROOT/env-dp2-gaap1p0.sh" <<'EOF'
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_PLATFORM=apollo
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_BIN_DIR=$SCRIPTS/bin
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp2_gaap1p0
export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
export PZ_PY=$PZ_CONDA_ENV/bin/python
export PATH=$PZ_CONDA_ENV/bin:$PZ_BIN_DIR:$PZ_COMPUTE_DIR/rail_scripts:$PATH
export PYTHONPATH=$PZ_COMPUTE_DIR/rail_scripts:${PYTHONPATH:-}
EOF

chmod +x "$PZ_INSTALL_ROOT/env-dp2-gaap1p0.sh"
```

Create the independent Stage 3 loader:

```bash
cat > "$PZ_INSTALL_ROOT/env-dp2-stage3-hats.sh" <<'EOF'
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_PLATFORM=apollo
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_BIN_DIR=$SCRIPTS/bin
export PZ_STAGE3_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp2_stage3_hats
export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
export PZ_PY=$PZ_STAGE3_CONDA_ENV/bin/python
export PATH=$PZ_STAGE3_CONDA_ENV/bin:$PZ_BIN_DIR:$PZ_COMPUTE_DIR/rail_scripts:$PATH
export PYTHONPATH=$PZ_COMPUTE_DIR/rail_scripts:${PYTHONPATH:-}
EOF

chmod +x "$PZ_INSTALL_ROOT/env-dp2-stage3-hats.sh"
```

The loaders deliberately avoid `conda activate`. This makes them safe to use
inside non-interactive Slurm jobs.

## 6. Validate and record both environments

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
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
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
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

After this one-time setup, each stage only needs to source its loader and
change to `$PZ_COMPUTE_DIR`. On Apollo, Slurm jobs use partition `cpu` and
account `hpc-public`; those execution parameters remain in the relevant stage
documents.

Continue with:

1. [Stage 1: train the GAaP 1.0 model](dp2_stage1_train_instructions_clipped.md)
2. [Stage 2: estimate DP2 photo-z values](dp2_stage2_estimate_instructions_clipped.md)
3. [Stage 3: build the HATS products](dp2_stage3_build_hats.md)
