**Instructions to run the DP02_duplicates notebooks in OnDemand platform**
Last updated: October 7, 2024

1. The first step is to create a conda virtual environment and let it available as a kernel for the OnDemand Jupyter environment. This can be done by following the instructions in the [LIneA's documentation](https://docs.linea.org.br/processamento/uso/openondemand.html). For running the notebooks and scripts here without needing to change anything, the conda environment name must be ```ondemand-kernel``` and be in the path ```/lustre/t0/scratch/users/<your-user>/ondemand-kernel```. If you have other environment with other name or path, you must change the ```.sbatch``` scripts accordingly.

2. In the OnDemand page, Cluters, _LIneA Shell Access, check if you have the conda-forge channel in your list of channels.
```bash
conda config --show channels
```
If you don't have it, append it to the list.
```bash
conda config --append channels conda-forge
```

3. Still there, activate your conda environment and install the necessary packages.
```bash
conda activate <full-path-to-your-environment>
```
```bash
conda install -c conda-forge numpy astropy pandas bokeh holoviews geoviews cartopy datashader dask dask-jobqueue distributed psutil tables-io h5py pyogrio fastparquet ipykernel pyviz_comms jupyter_bokeh lsdb
```
```bash
pip install git+https://github.com/astronomy-commons/hipscat-import.git@main
```

4. Create some necessary folders.
```bash
cd $SCRATCH
mkdir -p report_hipscat
cd report_hipscat
mkdir output
mkdir logs
```

5. Still in the report_hipscat directory, copy the scripts to this directory. If you had made the clone of the github repository, just run:
```bash
cp $SCRATCH/pz-compute/doc/dp02_duplicates/1_DP02_duplicates_two_tracts.ipynb .
cp $SCRATCH/pz-compute/doc/dp02_duplicates/2_DP02_duplicates_even_and_odd_tracts_subsamples.ipynb .
cp $SCRATCH/pz-compute/doc/dp02_duplicates/3_DP02_duplicates_spatial_distribution.ipynb .
cp $SCRATCH/pz-compute/doc/dp02_duplicates/4_DP02_duplicates_spatial_distribution_by_hand.ipynb .
cp $SCRATCH/pz-compute/doc/dp02_duplicates/{4_DP02_QA_histo_2d_ra_dec.py,4_DP02_QA_histo_2d_ra_dec.sbatch} .
cp $SCRATCH/pz-compute/doc/dp02_duplicates/{4_DP02_QA_histo_2d_ra_dec_detect_isPrimary_true.py,4_DP02_QA_histo_2d_ra_dec_detect_isPrimary_true.sbatch} .
cp $SCRATCH/pz-compute/doc/dp02_duplicates/5_DP02_conclusions.ipynb .
```


6. Execute the notebooks 1, 2 and 3 in the OnDemand platform using the kernel you created.

7. For notebook 4, first you have to run the ```.sbatch```scripts in the OnDemand terminal. Just go the ```report_hipscat``` folder and run
```bash
sbatch 4_DP02_QA_histo_2d_ra_dec.sbatch
```
```bash
sbatch 4_DP02_QA_histo_2d_ra_dec_detect_isPrimary_true.sbatch
```

8. Now you can run notebook 4.


Note: the plots with bokeh, geoviews, holoviews and datashader still have some bugs in the OnDemand platform and may not show up sometimes. Work is in progress to correct these bugs.