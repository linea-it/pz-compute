# DP1 GAaP 1.0: common Apollo/LineA setup

Run this setup once before the three DP1 stages. It creates two independent
environments:

- `pz_compute_dp1_gaap1p0` for Stage 1 training and Stage 2 estimation;
- `pz_compute_dp1_stage3_hats` for the additional HATS dependencies in Stage 3.

Keeping Stage 3 separate prevents its packages from changing the environment
that creates and consumes the FlexZBoost pickle.

## 1. Login and shared paths

```bash
ssh loginapl01

export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_PLATFORM=apollo
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_BIN_DIR=$SCRIPTS/bin
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp1_gaap1p0
export PZ_STAGE3_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp1_stage3_hats

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

Select the revision that will be used by all stages before installing. Do not
change it between Stages 1 and 2 without regenerating and revalidating the
model.

## 3. Create the Stage 1/Stage 2 environment

```bash
if [ ! -d "$PZ_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_CONDA_ENV" python=3.12 pip
fi

conda activate "$PZ_CONDA_ENV"
PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT" "$PZ_COMPUTE_DIR/rail_scripts/install-pz-rail"
conda install -y --prefix "$PZ_CONDA_ENV" -c conda-forge \
    pyarrow tables-io hdf5 h5py pyyaml
```

When prompted by `install-pz-rail`, confirm with `yes`. Once Stage 1 begins,
freeze this environment until Stage 2 is complete.

## 4. Create the Stage 3 environment

```bash
if [ ! -d "$PZ_STAGE3_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_STAGE3_CONDA_ENV" python=3.12 pip
fi

conda install -y --prefix "$PZ_STAGE3_CONDA_ENV" -c conda-forge \
    numpy pyarrow hdf5 h5py astropy distributed dask-jobqueue docopt

"$PZ_STAGE3_CONDA_ENV/bin/python" -m pip install lsdb hats-import hats
```

## 5. Create command links and loaders

```bash
for command in rail-train rail-estimate pz-build-hats; do
    ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/$command" "$PZ_BIN_DIR/$command"
    chmod +x "$PZ_BIN_DIR/$command"
done
```

Create the Stage 1/Stage 2 loader:

```bash
cat > "$PZ_INSTALL_ROOT/env-dp1-gaap1p0.sh" <<'EOF'
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_PLATFORM=apollo
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_BIN_DIR=$SCRIPTS/bin
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp1_gaap1p0
export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
export PZ_PY=$PZ_CONDA_ENV/bin/python
export PATH=$PZ_CONDA_ENV/bin:$PZ_BIN_DIR:$PZ_COMPUTE_DIR/rail_scripts:$PATH
export PYTHONPATH=$PZ_COMPUTE_DIR/rail_scripts:${PYTHONPATH:-}
EOF
chmod +x "$PZ_INSTALL_ROOT/env-dp1-gaap1p0.sh"
```

Create the Stage 3 loader:

```bash
cat > "$PZ_INSTALL_ROOT/env-dp1-stage3-hats.sh" <<'EOF'
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_PLATFORM=apollo
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_BIN_DIR=$SCRIPTS/bin
export PZ_STAGE3_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp1_stage3_hats
export PZ_PY=$PZ_STAGE3_CONDA_ENV/bin/python
export PATH=$PZ_STAGE3_CONDA_ENV/bin:$PZ_BIN_DIR:$PZ_COMPUTE_DIR/rail_scripts:$PATH
export PYTHONPATH=$PZ_COMPUTE_DIR/rail_scripts:${PYTHONPATH:-}
EOF
chmod +x "$PZ_INSTALL_ROOT/env-dp1-stage3-hats.sh"
```

The loaders avoid `conda activate`, which makes them safe in non-interactive
Slurm jobs.

## 6. Validate and record both environments

```bash
source /scripts/$(whoami)/ondemand/env-dp1-gaap1p0.sh
cd "$PZ_COMPUTE_DIR"

"$PZ_PY" - <<'PY'
import flexcode, pyarrow, rail, sklearn, tables_io, xgboost
print("Stage 1/Stage 2 environment is importable")
PY

"$PZ_PY" -m pip freeze > "$PZ_INSTALL_ROOT/dp1-gaap1p0-setup-freeze.txt"
git rev-parse HEAD > "$PZ_INSTALL_ROOT/pz-compute-revision.txt"
```

```bash
source /scripts/$(whoami)/ondemand/env-dp1-stage3-hats.sh

"$PZ_PY" - <<'PY'
import dask_jobqueue, distributed, hats, hats_import, h5py, lsdb, pyarrow
print("Stage 3 environment is importable")
PY

"$PZ_PY" -m pip freeze > "$PZ_INSTALL_ROOT/dp1-stage3-hats-setup-freeze.txt"
```

Continue with:

1. [Stage 1: reproduce the final DP1 model](dp1_stage1_train_instructions_matched_v4.md)
2. [Stage 2: estimate DP1 photo-z values](dp1_stage2_estimate_instructions_matched_v4.md)
3. [Stage 3: build the HATS products](dp1_stage3_build_hats.md)
