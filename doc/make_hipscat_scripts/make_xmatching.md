**Instructions for running the make_xmatching script in the Apollo Cluster**
Last updated: September 5, 2024

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

3. Create a conda virtual environment named "hipscat_env", activate it and install all the necessary packages:
```bash
conda create -n hipscat_env
```
```bash
conda activate hipscat_env
```
```bash
conda install -c conda-forge numpy dask dask-jobqueue distributed lsdb
```
```bash
pip install git+https://github.com/astronomy-commons/hipscat-import.git@main
```
Note: the name of the environment must be "hipscat_env". If you choose another name, you must change the .sbatch scripts accordingly.

4. Run the following commands to create the necessary folders:
```bash
cd $SCRATCH
mkdir -p hipscat_files
cd hipscat_files
mkdir output
mkdir logs
```

5. Still in the hipscat_files, copy the scripts to this directory. If you had made the clone of the github repository, just run:
```bash
cp $SCRATCH/pz-compute/doc/make_hipscat_scripts/{make_xmatching.py,make_xmatching.sbatch} .
```

6. Run the script with:
```bash
sbatch make_xmatching.sbatch
```
If you want to see info of the running job, use:
```bash
scontrol show job <your-job-number>
```