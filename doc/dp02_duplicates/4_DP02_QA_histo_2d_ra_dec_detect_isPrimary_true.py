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
import dask.array as da
from dask_jobqueue import SLURMCluster
from dask.distributed import Client, performance_report
###########################################################################################

######################### CONFIGURAÇÃO DOS PATHS ##########################################
# Identificar o path do usuário
user = getpass.getuser()
base_path = f'/lustre/t0/scratch/users/{user}/report_hipscat'

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
        f'--output={output_dir}/h2dradec_detect_isPrimary_true_dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={output_dir}/h2dradec_detect_isPrimary_true_dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],
)

# Escalando o cluster para usar múltiplos nós.
cluster.scale(jobs=12)  

# Criação do client Dask
client = Client(cluster)
###########################################################################################

################################## CONFIGURAÇÕES DE INPUT #################################
# Caminho para o relatório de desempenho do Dask.
performance_report_path = os.path.join(logs_dir, f'performance_report_histo_2d_ra_dec_detect_isPrimary_true.html')

# Defina o caminho da pasta onde os arquivos estão localizados.
file_list = glob.glob('/lustre/t1/cl/lsst/dp02/primary/catalogs/object/*.parq')

# Definir os bins para os histogramas
bins_ra_dec = (np.arange(48, 76, 0.056), np.arange(-46, -25, 0.042))
###########################################################################################

################################ CÁLCULO DOS HISTOGRAMAS ##################################
def compute_total_histogram(dask_dataframe):
    ra = dask_dataframe['coord_ra'].to_dask_array()
    dec = dask_dataframe['coord_dec'].to_dask_array()
    hist, _, _ = da.histogram2d(ra, dec, bins=bins_ra_dec)
    return hist.compute()

with performance_report(filename=performance_report_path):
    # Ler todos os arquivos parquet com dask.
    ddf = dd.read_parquet(file_list)
    
    # Aplicar corte baseado na banda e magnitude fornecidas
    ddf_filtered = ddf[ddf['detect_isPrimary'] == True]

    total_histogram_ra_dec = compute_total_histogram(ddf_filtered)
    all_data = [
        {'type': 'histogram_ra_dec', 'values': total_histogram_ra_dec.tolist()},
        {'type': 'bins_ra_dec', 'values': {'ra_bins': bins_ra_dec[0].tolist(), 'dec_bins': bins_ra_dec[1].tolist()}}
    ]

    all_data_df = pd.DataFrame(all_data)
    output_path = os.path.join(output_dir, 'histo_2d_ra_dec_detect_isPrimary_true.parquet')
    all_data_df.to_parquet(output_path, engine='fastparquet')
###########################################################################################

# Fechando o client
client.close()
cluster.close()
