Instructions to create the virtual environment in LIneA's JupyterLab to run the QA-report-DES-DR2-small notebook.
1) Create the environment and activate it.
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

2) Install the necessary packages with conda and pip. This may take a while.
```bash
conda install numpy pandas bokeh holoviews geoviews cartopy astropy dask pyogrio ipykernel pyviz_comms jupyter_bokeh
```
```bash
pip install dblinea
```

3) Make the environment available as a kernel for Jupyter.
```bash
python -m ipykernel install --user --name=hv-bokeh
```

6) Install the "jupyter-bokeh" extension in the Jupyter Lab extensions menu (right sidebar, puzzle symbol) and refresh the page.

7) Install the "pyviz-comms" extension in the Jupyter Lab extensions menu (right sidebar, puzzle symbol) and refresh the page.

8) Execute the notebook.

Note: If the graphics do not re-render at first when running the notebook, I recommend that you restart your server (STOP SERVER / START SERVER) and repeat steps 6, 7 and 8.