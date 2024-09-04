**Instructions for running the DP02_QA scripts in the Apollo Cluster**
Last updated: September 4, 2024

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

3. Create a conda virtual environment named "dp02_qa", activate it and install all the necessary packages:
```bash
conda create -n dp02_qa
conda activate dp02_qa 
conda install -c conda-forge dask dask-jobqueue distributed numpy pandas psutil tables-io h5py fastparquet
```
Note: the name of the environment must be "dp02_qa". If you choose another name, you must change the .sbatch scripts accordingly.

4. Run the following commands to create the necessary folders:
```bash
cd $SCRATCH
mkdir -p dp02_qa
cd dp02_qa
mkdir output
mkdir logs
```

5. Still in the dp02_qa directory, copy the scripts to this directory. If you had made the clone of the github repository, just run:
```bash
cp $SCRATCH/pz-compute/doc/dp02_qa_scripts/{DP02_QA_basic_stats.py,DP02_QA_basic_stats.sbatch} .
cp $SCRATCH/pz-compute/doc/dp02_qa_scripts/{DP02_QA_histo_2d_ra_dec.py,DP02_QA_histo_2d_ra_dec.sbatch} .
cp $SCRATCH/pz-compute/doc/dp02_qa_scripts/{DP02_QA_histo_1d_mag.py,DP02_QA_histo_1d_mag.sbatch} .
cp $SCRATCH/pz-compute/doc/dp02_qa_scripts/{DP02_QA_histo_1d_magerr.py,DP02_QA_histo_1d_magerr.sbatch} .
cp $SCRATCH/pz-compute/doc/dp02_qa_scripts/{DP02_QA_histo_2d_mag_magerr.py,DP02_QA_histo_2d_mag_magerr.sbatch} .
cp $SCRATCH/pz-compute/doc/dp02_qa_scripts/{DP02_QA_histo_2d_mag_color.py,DP02_QA_histo_2d_mag_color.sbatch} .
cp $SCRATCH/pz-compute/doc/dp02_qa_scripts/{DP02_QA_histo_2d_color_color.py,DP02_QA_histo_2d_color_color.sbatch} .
```

6. Run the scripts with:
```bash
sbatch DP02_QA_basic_stats.sbatch
sbatch DP02_QA_histo_2d_ra_dec.sbatch
sbatch DP02_QA_histo_1d_mag.sbatch
sbatch DP02_QA_histo_1d_magerr.sbatch
sbatch DP02_QA_histo_2d_mag_magerr.sbatch
sbatch DP02_QA_histo_2d_mag_color.sbatch
sbatch DP02_QA_histo_2d_color_color.sbatch
```
If you want to see info of the running job, use:
```bash
scontrol show job <your-job-number>
```

7. Don't forget to copy the following outputs
```bash
basic_stats_no_nan_no_inf.parquet
basic_stats.parquet
histo_2d_ra_dec.parquet
histo_1d_mag_all_bands.parquet
histo_1d_magerr_all_bands.parquet
histo_2d_mag_magerr_all_bands.parquet
histo_2d_mag_color_all_graphs.parquet
histo-2d_color_color_all_graphs.parquet
```
to your ```$HOME```, to a folder named ```output``` in the same directory of the DP02_QA_notebook_input.ipynb, for visualizing the results in the notebook. The notebook can be found in ```pz-compute/doc/notebooks/```.