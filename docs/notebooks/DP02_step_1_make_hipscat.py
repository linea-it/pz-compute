################################### IMPORTAÇÕES ###########################################
############################ GERAL ###########################
import os
import warnings
import glob
from pathlib import Path
############################ DASK ############################
from dask.distributed import Client, performance_report
from dask_jobqueue import SLURMCluster
######################## HIPSCAT ######################
### HIPSCAT
import hipscat
from hipscat_import.catalog.file_readers import ParquetReader
from hipscat_import.margin_cache.margin_cache_arguments import MarginCacheArguments
from hipscat_import.pipeline import ImportArguments, pipeline_with_client  
###########################################################################################

###########################################################################################
################################## CONFIGURAÇÕES DE INPUT #################################
### Diretório e nome dos arquivos de input. O nome pode ser uma lista ou conter um wildcard, ex: files_*.parquet.
CATALOG_DIR = Path("/lustre/t0/scratch/users/luigi.silva/random_from_files/truth/output")
CATALOG_FILES = 'random_sample_truth_type_1_0.002.parquet'
### Colunas a serem selecionadas no arquivo de input. As colunas de id, ra e dec são indispensáveis.
CATALOG_SELECTED_COLUMNS = ['id', 'host_galaxy', 'ra', 'dec', 'redshift', 'is_variable',
       'is_pointsource', 'flux_u', 'flux_g', 'flux_r', 'flux_i', 'flux_z',
       'flux_y', 'flux_u_noMW', 'flux_g_noMW', 'flux_r_noMW', 'flux_i_noMW',
       'flux_z_noMW', 'flux_y_noMW', 'tract', 'patch', 'truth_type',
       'cosmodc2_hp', 'cosmodc2_id', 'mag_r', 'match_objectId', 'match_sep',
       'is_good_match', 'is_nearest_neighbor', 'is_unique_truth_entry']
CATALOG_SORT_COLUMN = "id"
CATALOG_RA_COLUMN = "ra"
CATALOG_DEC_COLUMN = "dec"
FILE_TYPE = "parquet"
###########################################################################################

################################# CONFIGURAÇÕES DE OUTPUT #################################
### Diretório de output para os catálogos.
OUTPUT_DIR = Path("/lustre/t0/scratch/users/luigi.silva/")
HIPSCAT_DIR_NAME = "random_from_files"
HIPSCAT_DIR = OUTPUT_DIR / HIPSCAT_DIR_NAME

### Nomes para os outputs do catalógo e do cache de margem no formato HiPSCat.
CATALOG_HIPSCAT_NAME = "truth_z_hipscat"
CATALOG_HIPSCAT_DIR = HIPSCAT_DIR / CATALOG_HIPSCAT_NAME

### Caminho para o relatório de desempenho do Dask.
LOGS_DIR_NAME = "logs_truth_z_hipscat"
LOGS_DIR = HIPSCAT_DIR / LOGS_DIR_NAME 

PERFORMANCE_REPORT_NAME = 'performance_report_make_hipscat.html'
PERFORMANCE_DIR = LOGS_DIR / PERFORMANCE_REPORT_NAME
###########################################################################################

###########################################################################################

######################## CONFIGURAÇÃO DO CLUSTER ##########################################
# Configuração do SLURMCluster.
cluster = SLURMCluster(
    interface="ib0",    # Interface do Lustre
    queue='cpu_small',  # Substitua pelo nome da sua fila
    cores=56,           # Número de núcleos lógicos por nó
    processes=28,       # Número de processos por nó (um processo por núcleo)
    memory='100GB',     # Memória por nó
    walltime='05:00:00',  # Tempo máximo de execução
    job_extra_directives=[
        '--propagate',
        f'--output={LOGS_DIR}/dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={LOGS_DIR}/dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],                                             
)

# Escalando o cluster para usar X nós
cluster.scale(jobs=14)  

# Definindo o client do Dask
client = Client(cluster)
###########################################################################################


############################### EXECUTANDO O PIPELINE ######################################
with performance_report(filename=PERFORMANCE_DIR):
    if isinstance(CATALOG_FILES, list)==True:
        CATALOG_PATHS = [CATALOG_DIR / file for file in CATALOG_FILES]
    elif isinstance(CATALOG_FILES, str)==True:
        CATALOG_PATHS = list(CATALOG_DIR.glob(CATALOG_FILES))
    else:
        raise Exception("The type of names of catalogs files (CATALOG_FILES) is not supported. Supported types are list and str.")
    
    if FILE_TYPE=="parquet":
        catalog_args = ImportArguments(
            sort_columns=CATALOG_SORT_COLUMN,
            ra_column=CATALOG_RA_COLUMN,
            dec_column=CATALOG_DEC_COLUMN,
            input_file_list=CATALOG_PATHS,
            file_reader=ParquetReader(column_names=CATALOG_SELECTED_COLUMNS),
            output_artifact_name=CATALOG_HIPSCAT_NAME,
            output_path=HIPSCAT_DIR,
        )
        pipeline_with_client(catalog_args, client)
    else:
        raise Exception("Input catalog type not supported yet.")
###########################################################################################
    
# Fechando o client
client.close()
cluster.close()