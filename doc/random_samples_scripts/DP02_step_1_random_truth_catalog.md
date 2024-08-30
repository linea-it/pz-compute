Instructions for running the random_truth_catalog scripts.

1. In LIneA's HPC environment, clean your conda and pip:
```bash
conda clean --all
pip cache purge
```

2. Check if you have the conda-forge channel in your list of channels.
```bash
conda config --show channels
```
If you don't have it, append it to the list.
```bash
conda config --append channels conda-forge
```

3. Create a conda virtual environment named "pz_compute", activate it and install all the necessary packages:
```bash
conda create -n pz_compute
conda activate pz_compute 
conda install -c conda-forge dask dask-jobqueue numpy pandas psutil tables-io h5py
```
Note: the name of the environment must be "pz_compute". If you choose another name, you must change the .sbatch script accordingly.

4. Run the following commands to create the necessary folders:
```bash
cd $SCRATCH
mkdir -p random_from_files
cd random_from_files
mkdir output
mkdir logs
```

5. Still in the random_from_files directory, copy the scripts to this directory. If you had made the clone of the github repository, just run:
```bash
cp $SCRATCH/pz-compute/doc/random_samples_scripts/{DP02_step_1_random_truth_catalog.py,DP02_step_1_random_truth_catalog.sbatch} .
```

6. Run the script with:
```bash
sbatch DP02_step_1_random_truth_catalog.sbatch
```
If you want to see info of the running job, use:
```bash
scontrol show job <your-job-number>
```

