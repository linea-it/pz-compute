# Conda Environment and Kernel Configuration for Open OnDemand (LIneA) - LSST DP0.2 Object Data Preparation Scripts

Author: Luigi Silva  
Last reviewed: 28/03/2025

## Accessing Open OnDemand
To access the Open OnDemand platform, follow the steps below:

1. Go to: [ondemand.linea.org.br](https://ondemand.linea.org.br)
2. On the main page, click on: **Clusters -> LIneA Shell Access**

---

## Setting Up the Environment in LIneA Shell Access

### 1. Go to your `$SCRATCH` directory, download and install Miniconda
Run the following commands in the terminal:

```bash
cd $SCRATCH
curl -L -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod +x Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh -p $SCRATCH/miniconda
source miniconda/bin/activate
conda deactivate  # Necessary to deactivate the "base" environment
```

### 2. Create the Conda environment and install required packages
To create the environment:

```bash
conda create -p $SCRATCH/data_preparation -c conda-forge \
  numpy pandas dask dask-jobqueue ipykernel \
  astropy dustmaps -y
```

To activate the environment:

```bash
conda activate $SCRATCH/data_preparation
```

### 3. Configure `JUPYTER_PATH` and create the Jupyter Kernel
With the environment activated, set the required Jupyter path and install the kernel:

```bash
JUPYTER_PATH=$SCRATCH/.local
export JUPYTER_PATH
python -m ipykernel install --prefix=$JUPYTER_PATH --name 'data_preparation'
```

### 4. Download the Dustmaps Data (required once)
Since the JupyterLab interface does not have internet access, you need to download the required dustmaps from a Python shell via the terminal.

With the environment active, open a Python shell:

```bash
conda activate $SCRATCH/data_preparation
python
```

Then, run the following Python code:

```python
import getpass
import dustmaps.config
from dustmaps.sfd import fetch

user = getpass.getuser()
dustmaps.config.config['data_dir'] = f"/lustre/t0/scratch/users/{user}/miniconda3/envs/data_preparation/lib/python3.*/site-packages/dustmaps/data"
fetch()
```

> 💡 You may need to adjust the Python version (e.g., `python3.11`) in the path above depending on your environment.

This will download the necessary SFD dust maps into the environment's internal `site-packages` directory, making them available to your notebooks.

---

### Observation
After following the steps above, the kernel `data_preparation` will be available in the Jupyter Notebook interface on Open OnDemand. To use it, just select the kernel and execute the notebook cells.

---

## References
- https://docs.linea.org.br/processamento/uso/openondemand.html