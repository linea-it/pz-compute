import dask
from dask import dataframe as dd
from dask import delayed
from dask.distributed import Client, performance_report
from dask_jobqueue import SLURMCluster
import numpy as np
import pandas as pd
import glob
import psutil
import time
import tables_io
import os 

# Configuração do SLURMCluster para usar 12 nós com 56 núcleos lógicos e 128GB de RAM cada
cluster = SLURMCluster(
    interface="ib0",    # Interface do Lustre
    queue='cpu_small',  # Substitua pelo nome da sua fila
    cores=56,           # Número de núcleos lógicos por nó
    processes=56,       # Número de processos por nó (um processo por núcleo)
    memory='128GB',     # Memória por nó
    walltime='01:00:00',  # Tempo máximo de execução
    job_extra_directives=['--propagate'],  # Argumentos adicionais para o SLURM
)

# Escalando o cluster para usar 6 nós
cluster.scale(jobs=6)  # Defina para usar 6 nós

# Definindo o client do Dask
client = Client(cluster)  

# Medir o tempo de execução - START
start_wall_time = time.time()
start_cpu_time = psutil.cpu_times()

# Definição das variáveis pelo usuário
band_for_cut = 'i' 
#mag_cut = 24.1  
mag_cut = 25.2  
fraction = 0.002  
process_dir =  os.getcwd()  

# Caminho para o relatório de desempenho do Dask
performance_report_path = f'{process_dir}/performance_report_{band_for_cut}_{mag_cut}_{fraction}.html'

with performance_report(filename=performance_report_path):
    # Obter lista de arquivos HDF5 na pasta
    file_list = glob.glob('/lustre/t1/cl/lsst/dp0.2/secondary/catalogs/skinny/*.hdf5')
    
    # Ler todos os arquivos HDF5 com dask delayed.
    def read_hdf5(file):
        x = tables_io.read(file)
        return pd.DataFrame(x)
    # Ler os arquivos usando dask.delayed
    dfs = [delayed(read_hdf5)(file) for file in file_list]
    ddf = dd.from_delayed(dfs)
    
    # Remover valores NaN nas colunas de magnitude
    ddf = ddf.dropna(subset=[f'mag_{band_for_cut}'])
    
    # Aplicar corte baseado na banda e magnitude fornecidas
    ddf_filtered = ddf[ddf[f'mag_{band_for_cut}'] <= mag_cut]
    
    # Fazer uma seleção aleatória.
    ddf_sampled = ddf_filtered.sample(frac=fraction)

    # Caminhos de saída
    output_path_parquet = f'{process_dir}/output/random_sample_{band_for_cut}_{mag_cut}_{fraction}.parquet'
    output_path_csv = f'{process_dir}/output/random_sample_{band_for_cut}_{mag_cut}_{fraction}.csv'
    output_path_hdf5 = f'{process_dir}/output/random_sample_{band_for_cut}_{mag_cut}_{fraction}.hdf5'

    # Computando o dataframe.
    ddf_computed = ddf_sampled.compute()
    ddf_computed = ddf_computed.reset_index(drop=True)
    
    # Salvar os dados em Parquet
    ddf_computed.to_parquet(output_path_parquet, index=False)

    # Salvar os dados em CSV
    ddf_computed.to_csv(output_path_csv, index=False)

    # Salvar os dados em HDF5
    tables_io.write(ddf_computed, output_path_hdf5)

# Medir o tempo de execução - END
end_wall_time = time.time()
end_cpu_time = psutil.cpu_times()

# Calcular o tempo de execução
total_wall_time = end_wall_time - start_wall_time
total_cpu_time_user = end_cpu_time.user - start_cpu_time.user
total_cpu_time_system = end_cpu_time.system - start_cpu_time.system

# Salvar os tempos de execução em um arquivo de texto
output_time_path = f'{process_dir}/execution_times_{band_for_cut}_{mag_cut}_{fraction}.txt'
with open(output_time_path, 'w') as f:
    f.write(f'Total Wall Time: {total_wall_time} seconds\n')
    f.write(f'Total CPU Time (User): {total_cpu_time_user} seconds\n')
    f.write(f'Total CPU Time (System): {total_cpu_time_system} seconds\n')

# Fechando o client
client.close()
cluster.close()
