import dask
import dask.dataframe as dd
from dask_jobqueue import SLURMCluster
from dask.distributed import Client
import dask.array as da
import pandas as pd
import numpy as np
import os
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

# Defina o caminho da pasta onde os arquivos Parquet estão localizados
folder_path = '/lustre/t1/cl/lsst/dp0_skinny/DP0/DP0_FULL/parquet'

# Listar todos os arquivos Parquet na pasta
parquet_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith('.parquet')]

# Definição dos bins específicos para cada banda
bins = {
    'u': np.arange(15, 40, 0.25),
    'g': np.arange(15, 40, 0.25),
    'r': np.arange(15, 40, 0.25),
    'i': np.arange(15, 40, 0.25),
    'z': np.arange(15, 40, 0.25),
    'y': np.arange(15, 40, 0.25)
}

def compute_histogram_partition(df, filename, coluna, bin_edges, banda):
    array = da.from_array(df[coluna].values, chunks='auto')
    counts, _ = da.histogram(array, bins=bin_edges)
    counts = counts.compute()
    return pd.DataFrame({'band': [banda], 'filename': [filename], 'counts': [counts.tolist()]})

def process_file(file, banda):
    coluna = f'mag_{banda}'
    bin_edges = bins[banda]
    ddf = dd.read_parquet(file)
    histogramas = ddf.map_partitions(lambda df: compute_histogram_partition(df, file, coluna, bin_edges, banda), meta=pd.DataFrame({'band': [], 'filename': [], 'counts': []}))
    return histogramas.compute()

# Monitoramento de tempo
start_wall_time = time.time()
start_cpu_time = psutil.cpu_times()

# Coletando e concatenando todos os histogramas em um DataFrame único
all_histograms = [dask.delayed(process_file)(file, banda) for banda in bins for file in parquet_files]
final_histograms = dd.from_delayed(all_histograms).compute()

# Adicionando os dados dos bins
bins_rows = [{'band': banda, 'filename': 'bins', 'counts': bins[banda].tolist()} for banda in bins]
bins_df = pd.DataFrame(bins_rows)

# Concatenação dos histogramas e dados dos bins
final_df = pd.concat([final_histograms, bins_df], ignore_index=True)

output_path = '/lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/output/histo_1d_mag_all_bands.parquet'
final_df.to_parquet(output_path, engine='fastparquet')

end_wall_time = time.time()
end_cpu_time = psutil.cpu_times()

total_wall_time = end_wall_time - start_wall_time
total_cpu_time_user = end_cpu_time.user - start_cpu_time.user
total_cpu_time_system = end_cpu_time.system - start_cpu_time.system

output_time_path = '/lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/logs/histo_1d_mag_execution_times.txt'
with open(output_time_path, 'w') as f:
    f.write(f'Total Wall Time: {total_wall_time} seconds\n')
    f.write(f'Total CPU Time (User): {total_cpu_time_user} seconds\n')
    f.write(f'Total CPU Time (System): {total_cpu_time_system} seconds\n')

client.close()
cluster.close()
