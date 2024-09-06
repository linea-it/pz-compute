################################### IMPORTAÇÕES ###########################################
############################ GERAL ###########################
import os
import glob
import numpy as np
import pandas as pd
import tables_io
import getpass
############################ DASK ############################
import dask
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
    processes=28,                        # Número de processos por nó.
    memory='100GB',                       # Memória por nó
    walltime='00:30:00',                  # Tempo máximo de execução
    job_extra_directives=[
        '--propagate',
        f'--output={logs_dir}/h1dmagerr_dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={logs_dir}/h1dmagerr_dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],
)

# Escalando o cluster para usar múltiplos nós.
cluster.scale(jobs=12)  

# Criação do client Dask
client = Client(cluster)
###########################################################################################

################################## CONFIGURAÇÕES DE INPUT #################################
# Caminho para o relatório de desempenho do Dask.
performance_report_path = os.path.join(output_dir, f'performance_report_histo_1d_magerr.html')

# Defina o caminho da pasta onde os arquivos estão localizados.
file_list = glob.glob('/lustre/t1/cl/lsst/dp02/secondary/catalogs/skinny/hdf5/*.hdf5')

# Definição dos bins específicos para cada banda
bins = {
    'u': np.arange(0, 2, 0.02),
    'g': np.arange(0, 2, 0.02),
    'r': np.arange(0, 2, 0.02),
    'i': np.arange(0, 2, 0.02),
    'z': np.arange(0, 2, 0.02),
    'y': np.arange(0, 2, 0.02)
}
###########################################################################################

################################ CÁLCULO DOS HISTOGRAMAS ##################################
def read_hdf5(file):
    x = tables_io.read(file)
    return pd.DataFrame(x)

def compute_histogram(df, filename, coluna, bin_edges, banda):
    counts, _ = np.histogram(df[coluna].values, bins=bin_edges)
    return pd.DataFrame({'band': [banda], 'filename': [filename], 'counts': [counts.tolist()]})

def process_file(file, banda):
    coluna = f'magerr_{banda}'
    bin_edges = bins[banda]
    df = read_hdf5(file)
    histogram = compute_histogram(df, file, coluna, bin_edges, banda)
    return histogram

with performance_report(filename=performance_report_path):
    all_histograms = [dask.delayed(process_file)(file, banda) for banda in bins for file in file_list]
    final_histograms = dd.from_delayed(all_histograms).compute()

    bins_rows = [{'band': banda, 'filename': 'bins', 'counts': bins[banda].tolist()} for banda in bins]
    bins_df = pd.DataFrame(bins_rows)

    final_df = pd.concat([final_histograms, bins_df], ignore_index=True)

    output_path = os.path.join(output_dir, 'histo_1d_magerr_all_bands.parquet')
    final_df.to_parquet(output_path, engine='fastparquet')
###########################################################################################

client.close()
cluster.close()