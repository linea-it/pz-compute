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

# Configuração do SLURMCluster para usar 4 nós com 56 núcleos lógicos e 128GB de RAM cada
cluster = SLURMCluster(
    interface="ib0",    # Interface do Lustre.
    queue='cpu_small',  # Substitua pelo nome da sua fila
    cores=56,           # Número de núcleos lógicos por nó
    processes=28,       # Número de processos por nó (um processo por núcleo físico)
    memory='128GB',      # Memória por nó
    walltime='01:00:00',  # Tempo máximo de execução
    job_extra_directives=['--propagate'],  # Argumentos adicionais para o SLURM
)

# Escalando o cluster para usar 4 nós
cluster.scale(jobs=4)  # Defina para usar 4 nós

# Criação do client Dask
client = Client(cluster)

# Definir os bins para os histogramas
bins = {
    'u': (np.arange(16, 28, 0.02), np.arange(0, 0.4, 0.0007)),
    'g': (np.arange(16, 28, 0.02), np.arange(0, 0.4, 0.0007)),
    'r': (np.arange(16, 28, 0.02), np.arange(0, 0.4, 0.0007)),
    'i': (np.arange(16, 28, 0.02), np.arange(0, 0.4, 0.0007)),
    'z': (np.arange(16, 28, 0.02), np.arange(0, 0.4, 0.0007)),
    'y': (np.arange(16, 28, 0.02), np.arange(0, 0.4, 0.0007)),
}

def compute_total_histogram(dask_dataframe, band):
    mag = dask_dataframe[f'mag_{band}'].to_dask_array()
    magerr = dask_dataframe[f'magerr_{band}'].to_dask_array()
    hist, _, _ = da.histogram2d(mag, magerr, bins=bins[band])
    return hist.compute()

# Medir o tempo de execução
start_wall_time = time.time()
start_cpu_time = psutil.cpu_times()

# Obter lista de arquivos Parquet na pasta
file_list = glob.glob('/lustre/t1/cl/lsst/dp0_skinny/DP0/DP0_FULL/parquet/*.parquet')

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
output_path = '/lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/output/histo_2d_mag_magerr_all_bands.parquet'
all_data_df.to_parquet(output_path, engine='fastparquet')

# Medir o tempo de execução
end_wall_time = time.time()
end_cpu_time = psutil.cpu_times()

# Calcular o tempo de execução
total_wall_time = end_wall_time - start_wall_time
total_cpu_time_user = end_cpu_time.user - start_cpu_time.user
total_cpu_time_system = end_cpu_time.system - start_cpu_time.system

# Salvar os tempos de execução em um arquivo de texto
output_time_path = '/lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/logs/histo_2d_mag_magerr_execution_times.txt'
with open(output_time_path, 'w') as f:
    f.write(f'Total Wall Time: {total_wall_time} seconds\n')
    f.write(f'Total CPU Time (User): {total_cpu_time_user} seconds\n')
    f.write(f'Total CPU Time (System): {total_cpu_time_system} seconds\n')

# Fechando o client
client.close()
cluster.close()
