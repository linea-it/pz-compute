**Instructions for running the make_margin_cache script in the Apollo Cluster**
Last updated: November 01, 2024

If you just want to run the **make_margin_cache** script with the predefined configuration, you must run the **make_hats_truth** script with its predefined configuration first. So, you will have a hats catalog named "test_truth_hats" in the path ```/lustre/t0/scratch/users/<your-user>/hats_files/output/hats/test_truth_hats```. Once this is done, you can skip to step 5 in this instruction file.

If you have another **hats catalog** and want to generate the margin_cache for this catalog, you must change the CATALOG_HATS_DIR and CATALOG_MARGIN_CACHE_NAME variables in the ```make_margin_cache.py``` file, and then follow the steps below.

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

3. Create a conda virtual environment named "hats_env", activate it and install all the necessary packages:
```bash
conda create -n hats_env python=3.12.7
```
```bash
conda activate hats_env
```
```bash
conda install -c conda-forge --override-channels numpy dask dask-jobqueue distributed hats=0.4.2 hats-import=0.4.1 lsdb=0.4.1
```
Note: the name of the environment must be "hats_env". If you choose another name, you must change the .sbatch scripts accordingly.

4. Run the following commands to create the necessary folders:
```bash
cd $SCRATCH
mkdir -p hats_files
cd hats_files
mkdir output
mkdir logs
```

5. Still in the hats_files, copy the scripts to this directory. If you had made the clone of the github repository, just run:
```bash
cp $SCRATCH/pz-compute/doc/make_hats_scripts/{make_margin_cache.py,make_margin_cache.sbatch} .
```

6. Run the script with:
```bash
sbatch make_margin_cache.sbatch
```
If you want to see info of the running job, use:
```bash
scontrol show job <your-job-number>
```