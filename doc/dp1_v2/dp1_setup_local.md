# DP1 GAaP 1.0: common local setup

Run this setup once before the three DP1 stages. Stage 1 can be run completely
on a suitable workstation; Stages 2 and 3 provide reduced end-to-end tests on
one or two downloaded DP1 Object shards. Full catalog production belongs on
Apollo.

Two environments are used:

- `pz_compute_dp1_gaap1p0` for training and estimation;
- `pz_compute_dp1_stage3_hats` for HATS construction.

## 1. Choose a local root and clone the repository

Choose an absolute directory outside an existing checkout:

```bash
export PZ_LOCAL_ROOT=/path/to/pz-dp1-work
export PZ_PLATFORM=local
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

Select one repository revision for all stages before installing.

## 2. Create the Stage 1/Stage 2 environment

```bash
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp1_gaap1p0

if [ ! -d "$PZ_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_CONDA_ENV" python=3.12 pip
fi

conda activate "$PZ_CONDA_ENV"
PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT" "$PZ_COMPUTE_DIR/rail_scripts/install-pz-rail"
conda install -y --prefix "$PZ_CONDA_ENV" -c conda-forge \
    pyarrow tables-io hdf5 h5py pyyaml
```

Keep this environment unchanged between training and estimation.

## 3. Create the Stage 3 environment

```bash
export PZ_STAGE3_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp1_stage3_hats

if [ ! -d "$PZ_STAGE3_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_STAGE3_CONDA_ENV" python=3.12 pip
fi

conda install -y --prefix "$PZ_STAGE3_CONDA_ENV" -c conda-forge \
    numpy pyarrow hdf5 h5py astropy distributed dask-jobqueue docopt
"$PZ_STAGE3_CONDA_ENV/bin/python" -m pip install lsdb hats-import hats
```

## 4. Create command links and loaders

```bash
for command in rail-train rail-estimate pz-build-hats; do
    ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/$command" "$PZ_BIN_DIR/$command"
    chmod +x "$PZ_BIN_DIR/$command"
done
```

```bash
cat > "$PZ_INSTALL_ROOT/env-dp1-gaap1p0.sh" <<EOF
export PZ_LOCAL_ROOT="$PZ_LOCAL_ROOT"
export PZ_PLATFORM="local"
export PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT"
export PZ_SRC_DIR="$PZ_SRC_DIR"
export PZ_COMPUTE_DIR="$PZ_COMPUTE_DIR"
export PZ_RUN_ROOT="$PZ_RUN_ROOT"
export PZ_BIN_DIR="$PZ_BIN_DIR"
export PZ_CONDA_ENV="$PZ_CONDA_ENV"
export PZ_PY="$PZ_CONDA_ENV/bin/python"
export PATH="$PZ_CONDA_ENV/bin:$PZ_BIN_DIR:$PZ_COMPUTE_DIR/rail_scripts:\$PATH"
export PYTHONPATH="$PZ_COMPUTE_DIR/rail_scripts:\${PYTHONPATH:-}"
EOF
chmod +x "$PZ_INSTALL_ROOT/env-dp1-gaap1p0.sh"
```

```bash
cat > "$PZ_INSTALL_ROOT/env-dp1-stage3-hats.sh" <<EOF
export PZ_LOCAL_ROOT="$PZ_LOCAL_ROOT"
export PZ_PLATFORM="local"
export PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT"
export PZ_SRC_DIR="$PZ_SRC_DIR"
export PZ_COMPUTE_DIR="$PZ_COMPUTE_DIR"
export PZ_RUN_ROOT="$PZ_RUN_ROOT"
export PZ_BIN_DIR="$PZ_BIN_DIR"
export PZ_STAGE3_CONDA_ENV="$PZ_STAGE3_CONDA_ENV"
export PZ_PY="$PZ_STAGE3_CONDA_ENV/bin/python"
export PATH="$PZ_STAGE3_CONDA_ENV/bin:$PZ_BIN_DIR:$PZ_COMPUTE_DIR/rail_scripts:\$PATH"
export PYTHONPATH="$PZ_COMPUTE_DIR/rail_scripts:\${PYTHONPATH:-}"
EOF
chmod +x "$PZ_INSTALL_ROOT/env-dp1-stage3-hats.sh"
```

## 5. Validate both environments

```bash
source /path/to/pz-dp1-work/software/env-dp1-gaap1p0.sh
cd "$PZ_COMPUTE_DIR"

"$PZ_PY" - <<'PY'
import flexcode, pyarrow, rail, sklearn, tables_io, xgboost
print("Stage 1/Stage 2 environment is importable")
PY

"$PZ_PY" -m pip freeze > "$PZ_INSTALL_ROOT/dp1-gaap1p0-setup-freeze.txt"
git rev-parse HEAD > "$PZ_INSTALL_ROOT/pz-compute-revision.txt"
```

```bash
source /path/to/pz-dp1-work/software/env-dp1-stage3-hats.sh

"$PZ_PY" - <<'PY'
import distributed, hats, hats_import, h5py, lsdb, pyarrow
print("Stage 3 environment is importable")
PY

"$PZ_PY" -m pip freeze > "$PZ_INSTALL_ROOT/dp1-stage3-hats-setup-freeze.txt"
```

Continue with:

1. [Stage 1: reproduce the final DP1 model](dp1_stage1_train_instructions_matched_v4.md)
2. [Stage 2: run a reduced local estimate](dp1_stage2_estimate_instructions_matched_v4.md#10-run-a-reduced-local-test)
3. [Stage 3: build a reduced local HATS product](dp1_stage3_build_hats.md#8-build-a-reduced-local-test-product)
