# Step by step of running Pz Compute in LIneA Slurm

## Installation

Access the HPC environment via ssh (on Jupyter Hub Terminal or from a Linux Terminal, via srvlogin).

```bash
ssh loginapl01
```

***It is a requirement to have conda or [miniconda](https://docs.anaconda.com/free/miniconda/#quick-command-line-install) loaded on the system.***

#### Add the code below to your `~/.bashrc`:

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

#### Prepare sandbox:

```bash
export PZ_INSTALL_ROOT=/scripts/$(whoami)/ondemand
export PZ_SRC_DIR=/scripts/$(whoami)
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=/scratch/users/$(whoami)/pz-compute-runs

mkdir -p "$PZ_SRC_DIR" "$PZ_RUN_ROOT" "$PZ_INSTALL_ROOT/conda_pkgs"
export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs

cd "$PZ_SRC_DIR"
if [ ! -d pz-compute ]; then
  git clone https://github.com/linea-it/pz-compute
fi
cd "$PZ_COMPUTE_DIR"

conda create --prefix "$PZ_INSTALL_ROOT/pz_compute" python=3.12 pip
conda activate "$PZ_INSTALL_ROOT/pz_compute"

PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT" bash ./rail_scripts/install-pz-rail

cat <<EOF > "$PZ_INSTALL_ROOT/env.sh"
export PZ_INSTALL_ROOT=/scripts/\$(whoami)/ondemand
export PZ_SRC_DIR=/scripts/\$(whoami)
export PZ_COMPUTE_DIR=\$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=/scratch/users/\$(whoami)/pz-compute-runs
conda activate \$PZ_INSTALL_ROOT/pz_compute
export PZPATH=\$PZ_COMPUTE_DIR/rail_scripts/
export PATH=\$PATH:\$PZPATH
EOF

chmod +x "$PZ_INSTALL_ROOT/env.sh"
source "$PZ_INSTALL_ROOT/env.sh"
```

The repository clone, conda environment, package caches, `env.sh`, and other
small support files stay under `/scripts/$(whoami)/ondemand`. The run directory
below is created under `/scratch`, where the input links or copied inputs,
outputs, and logs will be written.

```bash
RUN_ID=test-001
mkdir -p "$PZ_RUN_ROOT/$RUN_ID"
cd "$PZ_RUN_ROOT/$RUN_ID"

ln -s "$PZ_COMPUTE_DIR/scheduler_examples/slurm/rail-slurm/rail-slurm.batch" .
ln -s "$PZ_COMPUTE_DIR/scheduler_examples/slurm/rail-slurm/rail-slurm.py" .

## copy or create symbolic links to the input files (pre-processing outputs)
mkdir input output

## Example: keep the real input files elsewhere and link them into scratch
# ln -s /path/to/preprocessed/input/*.hdf5 input/

## copy or create symbolic link to the estimator_{algorithm}.pkl file
cp <your estimator_{algorithm}.pkl> .

cc -o slurm-shield "$PZ_COMPUTE_DIR/utils/slurm/slurm-shield.c"
```

#### Execute pz-compute:

```bash
source /scripts/$(whoami)/ondemand/env.sh
cd /scratch/users/$(whoami)/pz-compute-runs/test-001

sbatch -n2 -N1 rail-slurm.batch input output fzboost  # using only 2 cores
```

The Slurm job creates the top-level `slurm-<jobid>.out` file and the per-task
`log/` directory in the current run directory under `/scratch`.
