**Instructions for running the make_xmatching script in the Apollo Cluster**
Last updated: October 18, 2024

**WARNING**
Before running this script, you must run the make_hats_object, make_hats_truth and make_margin_cache with the default configurations.

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
conda create -n hats_env
```
```bash
conda activate hats_env
```
```bash
conda install -c conda-forge numpy dask dask-jobqueue distributed
```
```bash
pip install git+https://github.com/astronomy-commons/hats.git@main
```
```bash
pip install git+https://github.com/astronomy-commons/hats-import.git@main
```
```bash
pip install git+https://github.com/astronomy-commons/lsdb.git@main
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
cp $SCRATCH/pz-compute/doc/make_hats_scripts/{make_xmatching.py,make_xmatching.sbatch} .
```

6. Run the script with:
```bash
sbatch make_xmatching.sbatch
```
If you want to see info of the running job, use:
```bash
scontrol show job <your-job-number>
```