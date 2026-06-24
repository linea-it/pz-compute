# Step by step of running Pz Compute in LIneA Slurm

## Installation

Access the HPC environment via ssh (on Jupyter Hub Terminal or from a Linux Terminal, via srvlogin).

```bash
ssh loginapl01
```

***It is a requirement to have conda or [miniconda](https://docs.anaconda.com/free/miniconda/#quick-command-line-install) loaded on the system.***

#### Add the code below to your `~/.bashrc`:

```bash
if [ -d /scratch/users/`whoami` ]; then
  export ALTHOME=/scratch/users/`whoami`/slurm-home
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
git clone https://github.com/linea-it/pz-compute && cd pz-compute
export REPO_DIR=`pwd`

mkdir -p /scratch/users/$(whoami)/ondemand/conda_pkgs
export CONDA_PKGS_DIRS=/scratch/users/$(whoami)/ondemand/conda_pkgs

conda create --prefix /scratch/users/$(whoami)/ondemand/pz_compute python=3.12 pip
conda activate /scratch/users/$(whoami)/ondemand/pz_compute

bash ./rail_scripts/install-pz-rail

cat <<EOF > env.sh
conda activate /scratch/users/\$(whoami)/ondemand/pz_compute
export PZPATH=$REPO_DIR/rail_scripts/
export PATH=\$PATH:\$PZPATH
EOF

chmod +x env.sh
source env.sh

mkdir sandbox && cd sandbox

ln -s $REPO_DIR/scheduler_examples/slurm/rail-slurm/rail-slurm.batch .
ln -s $REPO_DIR/scheduler_examples/slurm/rail-slurm/rail-slurm.py .

## copy or create symbolic link the input files (pre processing outputs)
mkdir input
mkdir output

## copy or create symbolic link the estimator_{algoritm}.pkl file
cp <your estimator_{algoritm}.pkl> .

cc -o slurm-shield ../utils/slurm/slurm-shield.c
```

#### Execute pz-compute:

```bash
sbatch -n2 -N1 rail-slurm.batch  # using only 2 cores
```