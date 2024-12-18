############################################################ IMPORTS ############################################################
########################### GENERAL ##########################
import os
import gc
import re
import sys
import glob
import time
import math
import getpass
import warnings
import tables_io
import subprocess
import numpy as np
import pandas as pd
import healpy as hp
from pathlib import Path
from datetime import datetime
############################ DASK ############################
import dask
from dask import dataframe as dd
from dask import delayed
from dask.distributed import Client, performance_report, wait
import dask_jobqueue
from dask_jobqueue import SLURMCluster
########################## HATS ###########################
import hats
from hats.inspection.visualize_catalog import plot_pixels
from hats.pixel_math import HealpixPixel
########################## HATS IMPORT ###########################
import hats_import
from hats_import.catalog.file_readers import ParquetReader, FitsReader
from hats_import.margin_cache.margin_cache_arguments import MarginCacheArguments
from hats_import.pipeline import ImportArguments, pipeline_with_client
############################ LSDB ############################
import lsdb
from lsdb.core.search import BoxSearch
######################## VISUALIZATION #######################
### BOKEH
import bokeh
from bokeh.io import output_notebook, show
from bokeh.models import ColorBar, LinearColorMapper
from bokeh.palettes import Viridis256

### HOLOVIEWS
import holoviews as hv
from holoviews import opts
from holoviews.operation.datashader import rasterize, dynspread

### GEOVIEWS
import geoviews as gv
import geoviews.feature as gf
from cartopy import crs

### DATASHADER
import datashader as ds

### MATPLOTLIB
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
########################## ASTRONOMY #########################
from astropy.io import fits
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.units.quantity import Quantity

### Getting hats version manually, because it has no __version__ attribute.
result = subprocess.run(
    ["conda", "run", "-p", "/lustre/t0/scratch/users/luigi.silva/hats_env_081124", "conda", "list", "hats"],
    stdout=subprocess.PIPE, text=True
)
for line in result.stdout.splitlines():
    if line.startswith("hats "):
        hats_version = line.split()[1]
        break



############################################################ OPTIONS ############################################################
# DO YOU WANT TO RUN THE MARGIN CACHE PIPELINE? 
run_the_pipeline = True

# DO YOU WANT TO SAVE ALL THE DASK JOBS OUTPUTS AND ERRORS OF DASK SLURMCluster?
save_the_dask_jobs_info = True

# DO YOU WANT TO SAVE ALL THE GENERAL INFORMATIONS OF THIS RUNNING (MAIN LIB VERSIONS, INPUT FILES SIZES, JOBS SCONTROL INFO, OUTPUT FILES SIZES)?
save_the_info = True

# DO YOU WANT TO CLOSE THE CLIENT AND THE CLUSTER AT THE END?
close_the_cluster = True



############################################################ PATHS ############################################################
hats_input_catalog = '/lustre/t1/public/des/dr2/secondary/catalogs/hats'
hats_input_catalog_ra = 'RA'
hats_input_catalog_dec = 'DEC'

if run_the_pipeline==True:
    hats_margin_cache_path = '/lustre/t1/cl/lsst/pz_project/test_data'
    hats_margin_cache_name = f'DES_DR2_margin_cache'

if save_the_dask_jobs_info or save_the_info:
    user = getpass.getuser()
    user_base_path = f'/lustre/t0/scratch/users/{user}/report_hats/DES-DR2-margin-cache'

if save_the_dask_jobs_info or save_the_info:
    os.makedirs(user_base_path, exist_ok=True)

    current_date = datetime.now().strftime('%Y-%m-%d_%H-%M')

    run_path = os.path.join(user_base_path, f'run_hats_{current_date}')
    os.makedirs(run_path, exist_ok=True)

    logs_dir = os.path.join(run_path, f'logs')
    os.makedirs(logs_dir, exist_ok=True)

    dask_logs_dir = os.path.join(logs_dir, f'dask_logs')
    os.makedirs(dask_logs_dir , exist_ok=True)

############################################################ CLUSTER ############################################################
extra_dask_configs=False
if extra_dask_configs==True:
    # Additional Dask configurations
    dask_config = {
        "distributed.worker.memory.target": 0.75,         # 75% before starting memory collection
        "distributed.worker.memory.spill": 0.85,          # 85% before starting to use disk
        "distributed.worker.memory.pause": 0.92,          # Pause the worker at 92%
        "distributed.worker.memory.terminate": 0.98,      # Restart the worker at 98%
        "distributed.worker.memory.recent-to-old": 0.2    # Keep 20% of recent data in memory
    }

    # Applying the Dask configurations
    dask.config.set(dask_config)


interface = "ib0"
queue = "cpu_small"
cores = 48
processes = 2
memory = "114GB"
walltime = "08:00:00"
account = "hpc-bpglsst"
if save_the_dask_jobs_info:
    job_extra_directives = [
        '--propagate',
        f'--output={dask_logs_dir}/dask_job_%j_{current_date}.out',  
        f'--error={dask_logs_dir}/dask_job_%j_{current_date}.err',
        f'--account={account}' 
    ]
else:
    job_extra_directives = [
        '--propagate',
        f'--output=/dev/null',  
        f'--error=/dev/null',
        f'--account={account}'  
    ]
number_of_nodes = 20


current_date = datetime.now().strftime('%Y-%m-%d_%H-%M')
# Configuring the SLURMCluster.
cluster = SLURMCluster(
    interface=interface,         # Lustre interface
    queue=queue,                 # Name of the queue
    cores=cores,                 # Number of logical cores per node
    processes=processes,         # Number of dask processes per node
    memory=memory,               # Memory per node
    walltime=walltime,           # Maximum execution time
    job_extra_directives=job_extra_directives,
)
# Scaling the cluster to use X nodes
cluster.scale(jobs=number_of_nodes)
# Defining the dask client
client = Client(cluster)
# Wait for the workers to initialize
cluster.wait_for_workers(n_workers=number_of_nodes*processes)
client.run(lambda: gc.collect())


############################################################ SAVING REQUESTED RESOURCES ############################################################
if save_the_info == True:  

    # Specific settings that you want to separate for the memory section
    memory_params = {
        "distributed.worker.memory.target": None,
        "distributed.worker.memory.spill": None,
        "distributed.worker.memory.pause": None,
        "distributed.worker.memory.terminate": None,
        "distributed.worker.memory.recent-to-old": "None",
        "distributed.worker.memory.recent-to-old-time": "None"
    }

    # Example of requested resource settings
    requested_resources = {
        "interface": f"{interface}",
        "queue": f"{queue}",
        "cores": cores,
        "processes": processes,
        "memory": f"{memory}",
        "walltime": f"{walltime}",
        "job_extra_directives": job_extra_directives,
        "number_of_nodes": number_of_nodes
    }

    # Getting Dask configurations
    dask_config = dask.config.config

    # Overwrite the memory parameters if they are set in the Dask configuration
    for param in memory_params.keys():
        sections = param.split('.')
        config = dask_config
        for section in sections:
            config = config.get(section, None)
            if config is None:
                break
        if config is not None:
            memory_params[param] = config

    # Preparing sections
    output = []

    # Requested resources section
    output.append("# Requested resources")
    for key, value in requested_resources.items():
        output.append(f"{key}={value}")

    # Memory configuration section
    output.append("\n# Dask memory configuration:")
    for key, value in memory_params.items():
        output.append(f'"{key}": {value}')

    # Section with all Dask configurations
    output.append("\n# Dask all configurations:")
    for section, config in dask_config.items():
        if isinstance(config, dict):
            output.append(f"[{section}]")
            for key, value in config.items():
                output.append(f"{key}: {value}")
        else:
            output.append(f"{section}: {config}")

    # Saving to a file or displaying the result
    with open(f'{logs_dir}/requested_resources_info.txt', 'w') as f:
        f.write("\n".join(output))

    print("Informations saved in requested_resources_info.txt")

############################################################ SAVING LIBRARIES AND JOBS ############################################################
if save_the_info==True:
    current_date = datetime.now().strftime('%Y-%m-%d_%H-%M')
    with open(f'{logs_dir}/main_lib_versions_{current_date}.txt', 'w') as f:
        f.write(f'python version: {sys.version} \n')
        f.write(f'numpy version: {np.__version__} \n')
        f.write(f'dask version: {dask.__version__} \n')
        f.write(f'dask_jobqueue version: {dask_jobqueue.__version__} \n')
        f.write(f'hats version: {hats_version} \n')
        f.write(f'hats_import version: {hats_import.__version__} \n')
        f.write(f'lsdb version: {lsdb.__version__} \n')

# Function to collect information about a job using the scontrol show job command
def get_scontrol_job_info(job_id):
    # Remove any interval or `%` from job_id
    clean_job_id = re.sub(r'\[.*?\]', '', job_id)
    
    # Execute scontrol show job
    result = subprocess.run(['scontrol', 'show', 'job', clean_job_id], stdout=subprocess.PIPE)
    job_info = result.stdout.decode('utf-8')
    
    job_dict = {}
    
    # Process the info line by line
    for line in job_info.splitlines():
        items = line.split()
        for item in items:
            if "=" in item:
                key, value = item.split("=", 1)
                job_dict[key] = value
    
    return job_dict

# Function to collect information about all jobs of the user
def get_all_jobs_info_MINE():
    # Gets the username using os.getenv('USER')
    user = os.getenv('USER')
    
    # Captures the list of running jobs for the user
    result = subprocess.run(['squeue', '-u', user, '-h', '-o', '%i'], stdout=subprocess.PIPE)
    job_ids = result.stdout.decode('utf-8').splitlines()

    # Collects information for each job
    jobs_info = []
    for job_id in job_ids:
        # Removes intervals or % from job_id before passing it to scontrol
        clean_job_id = re.sub(r'\[.*?\]', '', job_id)
        try:
            job_info = get_scontrol_job_info(clean_job_id)
            jobs_info.append(job_info)
        except Exception as e:
            print(f"Error processing job {job_id}: {e}")
    
    # Converts the list of dictionaries into a Pandas DataFrame
    df = pd.DataFrame(jobs_info)
    
    return df


# Function to collect information about all jobs that do not belong to the current user
def get_all_jobs_info_NOT_MINE():
    current_user = os.getenv('USER')
    
    # Captures the list of running jobs
    result = subprocess.run(['squeue', '-h', '-o', '%i %u'], stdout=subprocess.PIPE)
    job_lines = result.stdout.decode('utf-8').splitlines()
    
    # Filters jobs from other users
    jobs_info = []
    for line in job_lines:
        job_id, user = line.split()
        
        # Ignores jobs belonging to the current user
        if user != current_user:
            # Removes intervals or % from job_id before passing it to scontrol
            clean_job_id = re.sub(r'\[.*?\]', '', job_id)
            try:
                job_info = get_scontrol_job_info(clean_job_id)
                jobs_info.append(job_info)
            except Exception as e:
                print(f"Error processing job {job_id}: {e}")
    
    # Converts to DataFrame
    df = pd.DataFrame(jobs_info)
    return df

df_jobs_MINE = get_all_jobs_info_MINE()
df_jobs_NOT_MINE = get_all_jobs_info_NOT_MINE()

if save_the_info==True:
    current_date = datetime.now().strftime('%Y-%m-%d_%H-%M')
    
    file_name_MINE = f'{logs_dir}/jobs_info_MINE_{current_date}.csv'
    file_name_NOT_MINE = f'{logs_dir}/jobs_info_NOT_MINE_{current_date}.csv'
    
    df_jobs_MINE.to_csv(file_name_MINE, index=False)
    if len(df_jobs_NOT_MINE)!=0:
        df_jobs_NOT_MINE.to_csv(file_name_NOT_MINE, index=False)
    else:
        df_jobs_NOT_MINE_EMPTY_MSG.to_csv(file_name_NOT_MINE, index=False)



############################################################ MARGIN CACHE ############################################################
if run_the_pipeline==True:
    ################################## INPUT CONFIGS #################################
    ### Directory of the input catalog.
    CATALOG_HATS_DIR = Path(hats_input_catalog)
    MARGIN_CACHE_THRESHOLD = 1.0 #arcsec
    ###########################################################################################

    ################################# CONFIGURAÇÕES DE OUTPUT #################################
    ### Name of the margin cache to be saved.
    CATALOG_MARGIN_CACHE_NAME = hats_margin_cache_name
    
    ### Output directory for the margin cache and logs.
    HATS_DIR = Path(hats_margin_cache_path)
    LOGS_DIR = Path(logs_dir)
    
    CATALOG_MARGIN_CACHE_DIR = HATS_DIR / CATALOG_MARGIN_CACHE_NAME

    ### Path to dask performance report.
    PERFORMANCE_REPORT_NAME = f'dask_performance_report_{current_date}.html'
    PERFORMANCE_DIR = LOGS_DIR / PERFORMANCE_REPORT_NAME
    ###########################################################################################

    ############################### EXECUTANDO O PIPELINE ######################################
    with performance_report(filename=PERFORMANCE_DIR):   
        ### Getting informations from the catalog.
        catalog = hats.read_hats(CATALOG_HATS_DIR)
        info_frame = catalog.partition_info.as_dataframe()
        info_frame = info_frame.astype(int)
        
        ### Computing the margin cache, if it is possible.
        number_of_pixels = len(info_frame["Npix"])
        if number_of_pixels <= 1:
            warnings.warn(f"Number of pixels is equal to {number_of_pixels}. Impossible to compute margin cache.")
        else:
            margin_cache_args = MarginCacheArguments(
                input_catalog_path=CATALOG_HATS_DIR,
                output_path=HATS_DIR,
                margin_threshold=MARGIN_CACHE_THRESHOLD,  # arcsec
                output_artifact_name=CATALOG_MARGIN_CACHE_NAME,
            )
            pipeline_with_client(margin_cache_args, client)
###########################################################################################
else:
    print('You selected not to run the pipeline.') 

############################################################ CLOSING CLUSTER ############################################################
if close_the_cluster==True:
    client.close()
    cluster.close()
