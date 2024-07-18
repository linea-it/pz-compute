################################### IMPORTAÇÕES ###########################################
############################ GERAL ###########################
import os
import numpy as np
import pandas as pd
import glob
import psutil
import time
import tables_io
from pathlib import Path
import pyarrow.parquet as pq
############################ DASK ############################
import dask
from dask import dataframe as dd
from dask import delayed
from dask.distributed import Client, performance_report
from dask_jobqueue import SLURMCluster
######################## HIPSCAT E LSDB ######################
### HIPSCAT
from hipscat_import.catalog.file_readers import ParquetReader
from hipscat_import.margin_cache.margin_cache_arguments import MarginCacheArguments
from hipscat_import.pipeline import ImportArguments, pipeline_with_client  
### LDSB
import lsdb
###########################################################################################


######################## CONFIGURAÇÃO DO CLUSTER ##########################################
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
cluster.scale(jobs=12)  # Defina para usar 6 nós

# Definindo o client do Dask
client = Client(cluster)
###########################################################################################


#################### INÍCIO DA MEDIDA DO TEMPO DE EXECUÇÃO ################################
# Medir o tempo de execução - START
start_wall_time = time.time()
start_cpu_time = psutil.cpu_times()
###########################################################################################


############################### DEFINIÇÃO DOS PATHS #######################################
################## CONFIGURÁVEIS PELO USUÁRIO #######################
### Diretório dos dados de input.
LEFT_CATALOG_DIR = Path("/lustre/t1/cl/lsst/dp0/lsst_dp0/")
LEFT_CATALOG_FILES = "truth_*.parquet"
RIGHT_CATALOG_DIR = Path("/lustre/t0/scratch/users/julia/photoz/poster_andreia_rcw24/training_sets/test_random_luigi/output/")
RIGHT_CATALOG_FILES = "random_sample_i_24.1_0.002.parquet"

### Nome para o diretório do catalógo esquerdo no formato HiPSCat.
LEFT_CATALOG_HIPSCAT_NAME = "_dp0.1_truth"
### Nomes para os diretórios do catalógo e do cache de margem do catálogo direito no formato HiPSCat.
RIGHT_CATALOG_HIPSCAT_NAME = "_random_sample_i_24.1_0.002"
RIGHT_CATALOG_MARGIN_CACHE_NAME = "_MC_random_sample_i_24.1_0.002"

### Diretório para salvar os dados em formato HiPSCat.
HIPSCAT_DIR = Path("/lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/output/hipscat/")

### Caminho para o relatório de desempenho do Dask
performance_report_path = '/lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/output/performance_report_'+LEFT_CATALOG_HIPSCAT_NAME+RIGHT_CATALOG_HIPSCAT_NAME+'.html'

############################ AUTOMÁTICOS ############################
### Definindo os diretórios para os arquivos HiPSCat com base nos nomes definidos anteriormente.
LEFT_HIPSCAT_DIR = HIPSCAT_DIR / LEFT_CATALOG_HIPSCAT_NAME
RIGHT_HIPSCAT_DIR = HIPSCAT_DIR / RIGHT_CATALOG_HIPSCAT_NAME
RIGHT_MARGIN_CACHE_DIR = HIPSCAT_DIR / RIGHT_CATALOG_MARGIN_CACHE_NAME

### Nome e diretório para o crossmatching.
XMATCH_NAME = LEFT_CATALOG_HIPSCAT_NAME+'_x_'+RIGHT_CATALOG_HIPSCAT_NAME
OUTPUT_HIPSCAT_DIR = HIPSCAT_DIR / XMATCH_NAME
###########################################################################################

################################# TAMANHOS DOS PIXELS THRESHOLD ###########################
#### Estimativa simples dos tamanhos dos pixels threshold, de acordo com https://hipscat-import.readthedocs.io/en/stable/notebooks/estimate_pixel_threshold.html.

## 300MB
ideal_file_small = 300 * 1024 * 1024
## 1GB
ideal_file_large = 1024 * 1024 * 1024

### LEFT CATALOG
left_sample_parquet_files = LEFT_CATALOG_DIR.glob(LEFT_CATALOG_FILES)

left_total_num_rows = 0
left_total_file_size = 0

for file in left_sample_parquet_files:
    file_size = os.path.getsize(file)
    parquet_file = pq.ParquetFile(file)
    num_rows = parquet_file.metadata.num_rows
    
    # Acumula o número de linhas e o tamanho dos arquivos
    left_total_num_rows += num_rows
    left_total_file_size += file_size

# Calcula os thresholds com base nos valores totais
left_threshold_small = ideal_file_small / left_total_file_size * left_total_num_rows
left_threshold_large = ideal_file_large / left_total_file_size * left_total_num_rows

left_threshold = int((left_threshold_small+left_threshold_large)/2)

### RIGHT CATALOG
right_sample_parquet_files = RIGHT_CATALOG_DIR.glob(RIGHT_CATALOG_FILES)

right_total_num_rows = 0
right_total_file_size = 0

for file in right_sample_parquet_files:
    file_size = os.path.getsize(file)
    parquet_file = pq.ParquetFile(file)
    num_rows = parquet_file.metadata.num_rows
    
    # Acumula o número de linhas e o tamanho dos arquivos
    right_total_num_rows += num_rows
    right_total_file_size += file_size

# Calcula os thresholds com base nos valores totais
right_threshold_small = ideal_file_small / right_total_file_size * right_total_num_rows
right_threshold_large = ideal_file_large / right_total_file_size * right_total_num_rows

right_threshold = int((right_threshold_small + right_threshold_large) / 2)
###########################################################################################


############################### EXECUTANDO O PIPELINE ######################################
with performance_report(filename=performance_report_path):
    ### Rodando o pipeline de conversão para o catálogo esquerdo.
    left_args = ImportArguments(
        sort_columns="id",
        ra_column="ra",
        dec_column="dec",
        input_file_list=list(LEFT_CATALOG_DIR.glob(LEFT_CATALOG_FILES)),
        file_reader=ParquetReader(
                        column_names=['id', 'ra', 'dec', 'redshift', 'truth_type'],
        ),
        output_artifact_name=LEFT_CATALOG_HIPSCAT_NAME,
        output_path=HIPSCAT_DIR,
        #pixel_threshold=left_threshold,
    )
    pipeline_with_client(left_args, client)
    
    ### Rodando o pipeline de conversão para o catálogo direito.
    right_args = ImportArguments(
        sort_columns="objectId",
        ra_column="coord_ra",
        dec_column="coord_dec",
        input_file_list=list(RIGHT_CATALOG_DIR.glob(RIGHT_CATALOG_FILES)),
        file_reader=ParquetReader( 
                        column_names=['coord_dec', 'coord_ra', 'mag_g', 'mag_i', 'mag_r', 'mag_u', 'mag_y', 
                                      'mag_z', 'magerr_g', 'magerr_i', 'magerr_r', 'magerr_u', 'magerr_y', 
                                      'magerr_z', 'objectId'],
        ),
        output_artifact_name=RIGHT_CATALOG_HIPSCAT_NAME,
        output_path=HIPSCAT_DIR,
        pixel_threshold=right_threshold,
    )
    pipeline_with_client(right_args, client)
    
    ### Rodando o pipeline de conversão para o cache de margem do catálogo direito.
    margin_cache_args = MarginCacheArguments(
        input_catalog_path=RIGHT_HIPSCAT_DIR,
        output_path=HIPSCAT_DIR,
        margin_threshold=1.0,  # arcsec
        output_artifact_name=RIGHT_CATALOG_MARGIN_CACHE_NAME,
    )
    pipeline_with_client(margin_cache_args, client)

    ### Lendo os dados salvos no formato HiPSCat.
    left_catalog = lsdb.read_hipscat(LEFT_HIPSCAT_DIR)
    right_margin_cache_catalog = lsdb.read_hipscat(RIGHT_MARGIN_CACHE_DIR)
    right_catalog = lsdb.read_hipscat(RIGHT_HIPSCAT_DIR, margin_cache=right_margin_cache_catalog)
    
    ### Executando o crossmatching.
    xmatched = left_catalog.crossmatch(
        right_catalog,
        # Up to 1 arcsec distance, it is the default
        radius_arcsec=1.0,
        # Single closest object, it is the default
        n_neighbors=1,
        # Default would be to use names of the HiPSCat catalogs
        suffixes=(LEFT_CATALOG_HIPSCAT_NAME, RIGHT_CATALOG_HIPSCAT_NAME),
    )
    xmatched.to_hipscat(OUTPUT_HIPSCAT_DIR)
    

####################### FIM DA MEDIDA DO TEMPO DE EXECUÇÃO ################################
end_wall_time = time.time()
end_cpu_time = psutil.cpu_times()

# Calcular o tempo de execução
total_wall_time = end_wall_time - start_wall_time
total_cpu_time_user = end_cpu_time.user - start_cpu_time.user
total_cpu_time_system = end_cpu_time.system - start_cpu_time.system

# Salvar os tempos de execução em um arquivo de texto
output_time_path = '/lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/output/execution_times_'+LEFT_CATALOG_HIPSCAT_NAME+RIGHT_CATALOG_HIPSCAT_NAME+'.txt'
with open(output_time_path, 'w') as f:
    f.write(f'Total Wall Time: {total_wall_time} seconds\n')
    f.write(f'Total CPU Time (User): {total_cpu_time_user} seconds\n')
    f.write(f'Total CPU Time (System): {total_cpu_time_system} seconds\n')
###########################################################################################

# Fechando o client
client.close()
cluster.close()