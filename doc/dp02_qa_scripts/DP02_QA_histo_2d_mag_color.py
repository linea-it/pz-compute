################################### IMPORTAÇÕES ###########################################
############################ GERAL ###########################
import os
import glob
import numpy as np
import pandas as pd
import tables_io
import logging
import getpass
############################ DASK ############################
import dask.delayed as delayed
import dask.dataframe as dd
import dask.array as da
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

######################### CONFIGURAÇÃO DO LOGGING #########################################
logging.basicConfig(
    filename=os.path.join(logs_dir, 'histo_2d_mag_color_debug.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
###########################################################################################

######################## CONFIGURAÇÃO DO CLUSTER ##########################################
# Configuração do SLURMCluster.
cluster = SLURMCluster(
    interface="ib0",                      # Interface do Lustre.
    queue='cpu_small',                    # Substitua pelo nome da sua fila
    cores=56,                             # Número de núcleos lógicos por nó
    processes=28,                         # Número de processos por nó.
    memory='100GB',                       # Memória por nó
    walltime='01:00:00',                  # Tempo máximo de execução
    job_extra_directives=[
        '--propagate',
        f'--output={logs_dir}/h2dmagcolor_dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={logs_dir}/h2dmagcolor_dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],
)

# Escalando o cluster para usar múltiplos nós.
cluster.scale(jobs=12)  

# Criação do client Dask
client = Client(cluster)
###########################################################################################

################################## CONFIGURAÇÕES DE INPUT #################################
# Caminho para o relatório de desempenho do Dask.
performance_report_path = os.path.join(output_dir, f'performance_report_histo_2d_mag_color.html')

# Defina o caminho da pasta onde os arquivos estão localizados.
file_list = glob.glob('/lustre/t1/cl/lsst/dp02/secondary/catalogs/skinny/hdf5/*.hdf5')

# Definir os bins para os histogramas
bins = {
    'u_x_umg': (np.arange(10, 30, 0.032), np.arange(-10, 10, 0.032)),
    'g_x_gmr': (np.arange(10, 30, 0.032), np.arange(-10, 10, 0.032)),
    'r_x_rmi': (np.arange(10, 30, 0.032), np.arange(-10, 10, 0.032)),
    'i_x_imz': (np.arange(10, 30, 0.032), np.arange(-10, 10, 0.032)),
    'z_x_zmy': (np.arange(10, 30, 0.032), np.arange(-10, 10, 0.032)),
    'i_x_gmr': (np.arange(10, 30, 0.032), np.arange(-10, 10, 0.032)),
}
###########################################################################################

################################ CÁLCULO DOS HISTOGRAMAS ##################################
def compute_total_histogram(dask_dataframe, mag_col, color_col, graph):
    mag = dask_dataframe[mag_col].to_dask_array()
    color = dask_dataframe[color_col].to_dask_array()
    hist, _, _ = da.histogram2d(mag, color, bins=bins[graph])
    return hist.compute()

def read_hdf5(file):
    x = tables_io.read(file)
    return pd.DataFrame(x)

def replace_nan_inf_and_calculate_colors(df, filename):
    if isinstance(df, pd.DataFrame):
        mag_cols = ['mag_u', 'mag_g', 'mag_r', 'mag_i', 'mag_z', 'mag_y']
        missing_columns = [col for col in mag_cols if col not in df.columns]

        if missing_columns:
            logging.error(f"Arquivo {filename} está faltando as colunas: {', '.join(missing_columns)}")
        else:
            df[mag_cols] = df[mag_cols].replace([np.nan, np.inf, -np.inf], 99.)
            df['umg'] = df['mag_u'] - df['mag_g']
            df['gmr'] = df['mag_g'] - df['mag_r']
            df['rmi'] = df['mag_r'] - df['mag_i']
            df['imz'] = df['mag_i'] - df['mag_z']
            df['zmy'] = df['mag_z'] - df['mag_y']
    else:
        logging.error(f"O objeto retornado de {filename} não é um DataFrame: {type(df)}")

    return df

with performance_report(filename=performance_report_path):
    dfs = [delayed(read_hdf5)(file) for file in file_list]
    processed_dfs = [delayed(replace_nan_inf_and_calculate_colors)(df, file) for df, file in zip(dfs, file_list)]
    ddf = dd.from_delayed(processed_dfs)

    all_data = []
    graphs = {
        'u_x_umg': ('mag_u', 'umg'),
        'g_x_gmr': ('mag_g', 'gmr'),
        'r_x_rmi': ('mag_r', 'rmi'),
        'i_x_imz': ('mag_i', 'imz'),
        'z_x_zmy': ('mag_z', 'zmy'),
        'i_x_gmr': ('mag_i', 'gmr'),
    }

    for graph, (mag_col, color_col) in graphs.items():
        total_histogram = compute_total_histogram(ddf, mag_col, color_col, graph)
        all_data.append({'graph': graph, 'type': 'histogram', 'values': total_histogram.tolist()})
        all_data.append({'graph': graph, 'type': 'bins', 'values': {'mag_bins': bins[graph][0].tolist(), 'color_bins': bins[graph][1].tolist()}})

    all_data_df = pd.DataFrame(all_data)

    output_path = os.path.join(output_dir, 'histo_2d_mag_color_all_graphs.parquet')
    all_data_df.to_parquet(output_path, engine='fastparquet')
###########################################################################################

# Fechando o client
client.close()
cluster.close()