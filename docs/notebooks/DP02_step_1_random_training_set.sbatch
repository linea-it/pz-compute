#!/bin/bash
#SBATCH --job-name=dask_make_random_train     # job name
#SBATCH --output=/lustre/t0/scratch/users/gschwend/github/pz-compute/docs/notebooks/slurm_%j.out # slurm log output name (%j replaced by job ID)
#SBATCH --error=/lustre/t0/scratch/users/gschwend/github/pz-compute/docs/notebooks/slurm_%j.err # slurm raise error output name (%j replaced by job ID)
#SBATCH --partition=cpu_small  # slurm queue 
#SBATCH --nodes=4              # number of nodes 
#SBATCH --ntasks-per-node=28   # equivalent to number of Dask processes 
#SBATCH --cpus-per-task=2      # threads per task (2 threads per physical core) 
#SBATCH --mem=128GB            # memory per node 
#SBATCH --time=01:00:00        # timeout limit  
#SBATCH --propagate

# Initialize Conda e activate environment pz_compute
export PATH="/lustre/t0/scratch/users/gschwend/miniconda3/bin:$PATH"
eval "$(conda shell.bash hook)"
conda activate pz_compute

# Verify if env is activated correctly 
echo "Python from: $(which python)"
echo "Python version: $(python --version)"
echo "Installed packages:"
pip list

# Execute Python script 
python /lustre/t0/scratch/users/gschwend/github/pz-compute/docs/notebooks/DP02_step_1_random_training_set.py 