# Conda Environment and Kernel Configuration for Open OnDemand (LIneA) - Data Preparation Scripts

Author: Luigi Silva  
Last reviewed: Apr. 04, 2025

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
First of all, add the following channels to your environment:
```bash
conda config --add channels conda-forge
conda config --add channels defaults
conda config --add channels anaconda
conda config --add channels pyviz
```
I also strongly recomend you to use the mamba solver. See instructions in the following web page:
https://conda.github.io/conda-libmamba-solver/user-guide/

To create the environment:

```bash
conda env create -p $SCRATCH/data_preparation -f environment.yaml
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
dustmaps.config.config['data_dir'] = f'/lustre/t0/scratch/users/{user}/data_preparation/lib/python3.12/site-packages/dustmaps/data'
fetch()
```

To exit the python shell, just type:
```python
exit()
```

This will download the necessary SFD dust maps into the environment's internal `site-packages` directory, making them available to your notebooks.

### 5. Configure your YAML before running the notebook
Before executing the ```1_Data_Preparation``` notebook, make sure to:

1. Rename your YAML configuration file to ```config.yaml```
2. Open the YAML file and edit the field ```user_base_path``` to reflect your username, for example:

```python
"/lustre/t0/scratch/users/<your-user>/dp02_object_data_preparation"
```

Replace ```<your-user>``` with your actual user directory name on the system.

The other notebooks do not have a ```.yaml``` configuration file implemented yet. All the configuration must be done inside the notebooks themselves.

---

### Observation
After following the steps above, the kernel `data_preparation` will be available in the Jupyter Notebook interface on Open OnDemand. To use it, just select the kernel and execute the notebook cells.

---

## References
- https://docs.linea.org.br/processamento/uso/openondemand.html