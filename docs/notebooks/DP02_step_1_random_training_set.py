from dask.distributed import Client
from dask_jobqueue import SLURMCluster
import dask.dataframe as dd
import dask.array as da
import numpy as np
import pandas as pd
import os
import glob
import time
import psutil

cluster = SLURMCluster(
    interface="ib0",    
    queue='cpu_small',  
    cores=56,           
    processes=28,       
    memory='128GB',      
    walltime='01:00:00',  
    job_extra_directives=['--propagate']
)

cluster.scale(jobs=4)

# Client Dask
client = Client(cluster)

def select_data(filename, fraction=0.001): 
    """ Read table, load as dataframe, trim columns, remove low s/n objects, then select random fraction. """
    
    
def prepare_data(dataframe):
    """ Apply extiction correction, remove extreme color outliers."""
    
def save_partial_tmp_files(): 
    
        
    

# Measure execution time 
start_wall_time = time.time()
start_cpu_time = psutil.cpu_times()

# Get list of parquet files in the  folder 
file_list = glob.glob('/lustre/t1/cl/lsst/dp0.2/*.parq')

# Ler e concatenar todos os arquivos Parquet
df = dd.read_parquet(file_list)

# Inicializar a lista para armazenar todos os dados
all_data = []

# Computar e salvar histogramas e bins para cada banda
for band in bins.keys():
    total_histogram = compute_total_histogram(df, band)
    all_data.append({'band': band, 'type': 'histogram', 'values': total_histogram.tolist()})
    all_data.append({'band': band, 'type': 'bins', 'values': {'mag_bins': bins[band][0].tolist(), 'magerr_bins': bins[band][1].tolist()}})

# Criar dataframe único e salvar em arquivo Parquet
all_data_df = pd.DataFrame(all_data)
output_path = '/lustre/t0/scratch/users/luigi.silva/lsst/combined-graphs-QA-notebook/output/histo_2d_mag_magerr_all_bands.parquet'
all_data_df.to_parquet(output_path, engine='fastparquet')

# Medir o tempo de execução
end_wall_time = time.time()
end_cpu_time = psutil.cpu_times()

# Calcular o tempo de execução
total_wall_time = end_wall_time - start_wall_time
total_cpu_time_user = end_cpu_time.user - start_cpu_time.user
total_cpu_time_system = end_cpu_time.system - start_cpu_time.system

# Salvar os tempos de execução em um arquivo de texto
output_time_path = '/lustre/t0/scratch/users/luigi.silva/lsst/combined-graphs-QA-notebook/logs/histo_2d_mag_magerr_execution_times.txt'
with open(output_time_path, 'w') as f:
    f.write(f'Total Wall Time: {total_wall_time} seconds\n')
    f.write(f'Total CPU Time (User): {total_cpu_time_user} seconds\n')
    f.write(f'Total CPU Time (System): {total_cpu_time_system} seconds\n')

# Fechando o client
client.close()
cluster.close()
