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
    memory='128GB',     # Memória por nó
    walltime='01:00:00',  # Tempo máximo de execução
    job_extra_directives=['--propagate'],  # Argumentos adicionais para o SLURM
)

# Escalando o cluster para usar 4 nós
cluster.scale(jobs=4)  # Defina para usar 4 nós

# Criação do client Dask
client = Client(cluster)

# Definir os bins para os histogramas de ra e dec
#bins_ra_dec = (np.arange(0, 360, 0.1), np.arange(-90, 90, 0.1))
bins_ra_dec = (np.arange(49, 75, 0.05), np.arange(-45, -26, 0.038))

def compute_histogram_ra_dec(dask_dataframe):
    ra = dask_dataframe['ra'].to_dask_array()
    dec = dask_dataframe['dec'].to_dask_array()
    hist, _, _ = da.histogram2d(ra, dec, bins=bins_ra_dec)
    return hist.compute()

# Medir o tempo de execução
start_wall_time = time.time()
start_cpu_time = psutil.cpu_times()

# Obter lista de arquivos Parquet na pasta
file_list = glob.glob('/lustre/t1/cl/lsst/dp0_skinny/DP0/DP0_FULL/parquet/*.parquet')

# Ler e concatenar todos os arquivos Parquet
df = dd.read_parquet(file_list)

# Computar e salvar histogramas e bins para ra e dec
total_histogram_ra_dec = compute_histogram_ra_dec(df)
all_data = [
    {'type': 'histogram_ra_dec', 'values': total_histogram_ra_dec.tolist()},
    {'type': 'bins_ra_dec', 'values': {'ra_bins': bins_ra_dec[0].tolist(), 'dec_bins': bins_ra_dec[1].tolist()}}
]

# Criar dataframe único e salvar em arquivo Parquet
all_data_df = pd.DataFrame(all_data)
output_path = '/lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/output/histo_2d_ra_dec.parquet'
all_data_df.to_parquet(output_path, engine='fastparquet')

# Medir o tempo de execução
end_wall_time = time.time()
end_cpu_time = psutil.cpu_times()

# Calcular o tempo de execução
total_wall_time = end_wall_time - start_wall_time
total_cpu_time_user = end_cpu_time.user - start_cpu_time.user
total_cpu_time_system = end_cpu_time.system - start_cpu_time.system

# Salvar os tempos de execução em um arquivo de texto
output_time_path = '/lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/logs/histo_2d_ra_dec_execution_times.txt'
with open(output_time_path, 'w') as f:
    f.write(f'Total Wall Time: {total_wall_time} seconds\n')
    f.write(f'Total CPU Time (User): {total_cpu_time_user} seconds\n')
    f.write(f'Total CPU Time (System): {total_cpu_time_system} seconds\n')

# Fechando o client
client.close()
cluster.close()
