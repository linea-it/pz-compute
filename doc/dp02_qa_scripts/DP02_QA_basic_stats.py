################################### IMPORTAÇÕES ###########################################
############################ GERAL ###########################
import os
import glob
import numpy as np
import pandas as pd
import tables_io
import getpass
############################ DASK ############################
import dask.delayed as delayed
import dask.dataframe as dd
from dask_jobqueue import SLURMCluster
from dask.distributed import Client, performance_report
###########################################################################################

######################### CONFIGURAÇÃO DOS PATHS ##########################################
# Identificar o path do usuário
user = getpass.getuser()
base_path = f'/lustre/t0/scratch/users/{user}/dp02_qa'

# Criar pastas 'output' e 'logs' se não existirem
output_dir = os.path.join(base_path, 'output')
logs_dir = os.path.join(base_path, 'logs')
os.makedirs(output_dir, exist_ok=True)
os.makedirs(logs_dir, exist_ok=True)
###########################################################################################

######################## CONFIGURAÇÃO DO CLUSTER ##########################################
# Configuração do SLURMCluster.
cluster = SLURMCluster(
    interface="ib0",                      # Interface do Lustre.
    queue='cpu_small',                    # Substitua pelo nome da sua fila
    cores=56,                             # Número de núcleos lógicos por nó
    processes=28,                         # Número de processos por nó.
    memory='100GB',                       # Memória por nó
    walltime='00:30:00',                  # Tempo máximo de execução
    job_extra_directives=[
        '--propagate',
        f'--output={logs_dir}/bs_dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={logs_dir}/bs_dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],
)

# Escalando o cluster para usar múltiplos nós.
cluster.scale(jobs=12)  

# Criação do client Dask
client = Client(cluster)
###########################################################################################

################################## CONFIGURAÇÕES DE INPUT #################################
# Caminho para o relatório de desempenho do Dask.
performance_report_path = os.path.join(output_dir, f'performance_report_basic_stats.html')

# Defina o caminho da pasta onde os arquivos estão localizados.
file_list = glob.glob('/lustre/t1/cl/lsst/dp02/secondary/catalogs/skinny/hdf5/*.hdf5')
###########################################################################################

################################ CÁLCULO DOS HISTOGRAMAS ##################################
def compute_basic_stats(dask_dataframe):
    dask_dataframe_basic_stats = dask_dataframe.describe()
    return dask_dataframe_basic_stats

def compute_basic_stats_filtered(dask_dataframe):
    mask = dask_dataframe.isin([np.nan, np.inf, -np.inf]).any(axis=1)
    filt_dask_dataframe = dask_dataframe[~mask]
    filt_dask_dataframe_basic_stats = filt_dask_dataframe.describe()
    return filt_dask_dataframe_basic_stats
    
def read_hdf5(file):
    x = tables_io.read(file)
    return pd.DataFrame(x)

with performance_report(filename=performance_report_path):
    dfs = [delayed(read_hdf5)(file) for file in file_list]
    ddf = dd.from_delayed(dfs)
    
    basic_stats = compute_basic_stats(ddf)
    basic_stats_filtered = compute_basic_stats_filtered(ddf)
    
    output_path = output_dir
    basic_stats_name = 'basic_stats.parquet'
    basic_stats_filtered_name = 'basic_stats_no_nan_no_inf.parquet'
    
    basic_stats.compute().to_parquet(os.path.join(output_path, basic_stats_name), engine='fastparquet')
    basic_stats_filtered.compute().to_parquet(os.path.join(output_path, basic_stats_filtered_name), engine='fastparquet')
###########################################################################################

# Fechando o client
client.close()
cluster.close()