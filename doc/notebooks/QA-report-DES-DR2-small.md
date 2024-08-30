Instructions to create the virtual environment in LIneA's JupyterLab to run the QA-report-DES-DR2-small notebook.

1. In LIneA's JupyterLab environment, clean your conda and pip:
```bash
conda clean --all
```
```bash
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

3. Create a conda virtual environment named "hv-bokeh", activate it and install all the necessary packages:
```bash
conda create -p $HOME/.conda/envs/hv-bokeh
```
```bash
conda activate hv-bokeh
```
OU
```bash
source activate hv-bokeh
```
```bash
conda install -c conda-forge numpy pandas bokeh holoviews geoviews cartopy astropy dask pyogrio ipykernel pyviz_comms jupyter_bokeh
```
```bash
pip install dblinea
```

4. Make the environment available as a kernel for Jupyter.
```bash
python -m ipykernel install --user --name=hv-bokeh
```

5. Install the "jupyter-bokeh" extension in the Jupyter Lab extensions menu (right sidebar, puzzle symbol) and refresh the page.

6. Install the "pyviz-comms" extension in the Jupyter Lab extensions menu (right sidebar, puzzle symbol) and refresh the page.

7. Execute the notebook.

Note: If the graphics do not re-render at first when running the notebook, I recommend that you restart your server (STOP SERVER / START SERVER) and repeat steps 5, 6 and 7.