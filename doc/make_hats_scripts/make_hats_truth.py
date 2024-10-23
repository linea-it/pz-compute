################################### IMPORTAÇÕES ###########################################
############################ GERAL ###########################
import os
import warnings
import glob
import getpass
from pathlib import Path
############################ DASK ############################
from dask.distributed import Client, performance_report
from dask_jobqueue import SLURMCluster
######################## HATS ######################
### HATS
import hats
from hats_import.catalog.file_readers import ParquetReader
from hats_import.margin_cache.margin_cache_arguments import MarginCacheArguments
from hats_import.pipeline import ImportArguments, pipeline_with_client  
###########################################################################################

######################### CONFIGURAÇÃO DOS PATHS DO USUÁRIO ###############################
# Identificar o path do usuário
user = getpass.getuser()
base_path = f'/lustre/t0/scratch/users/{user}/hats_files'

# Criar pastas 'output' e 'logs' se não existirem
user_output_dir = os.path.join(base_path, 'output')
user_logs_dir = os.path.join(base_path, 'logs')
os.makedirs(user_output_dir, exist_ok=True)
os.makedirs(user_logs_dir, exist_ok=True)
###########################################################################################

################################## CONFIGURAÇÕES DE INPUT #################################
### Diretório e nome dos arquivos de input. O nome pode ser uma lista ou conter um wildcard, ex: files_*.parquet.
CATALOG_DIR = Path('/lustre/t1/cl/lsst/dp01/primary/catalogs/truth')
CATALOG_FILES = 'truth_tract507*.parquet'
### Colunas a serem selecionadas no arquivo de input. As colunas de id, ra e dec são indispensáveis.
CATALOG_SELECTED_COLUMNS = ['id', 'host_galaxy', 'ra', 'dec', 'redshift', 'is_variable',
                            'is_pointsource', 'flux_u', 'flux_g', 'flux_r', 'flux_i', 'flux_z',
                            'flux_y', 'flux_u_noMW', 'flux_g_noMW', 'flux_r_noMW', 'flux_i_noMW',
                            'flux_z_noMW', 'flux_y_noMW', 'tract', 'patch', 'truth_type',
                            'cosmodc2_hp', 'cosmodc2_id', 'mag_r', 'match_objectId', 'match_sep',
                            'is_good_match', 'is_nearest_neighbor', 'is_unique_truth_entry']
CATALOG_SORT_COLUMN = 'id'
CATALOG_RA_COLUMN = 'ra'
CATALOG_DEC_COLUMN = 'dec'
### Tipo de arquivos que serão lidos.
FILE_TYPE = 'parquet'
### Nomes do catálogo HATS a ser salvo.
CATALOG_HATS_NAME = 'test_truth_hats'
###########################################################################################

################################# CONFIGURAÇÕES DE OUTPUT #################################
### Diretório de output para os catálogos.
OUTPUT_DIR = Path(user_output_dir)
HATS_DIR_NAME = 'hats'
HATS_DIR = OUTPUT_DIR / HATS_DIR_NAME

### Nomes para os outputs do catalógo e do cache de margem no formato HATS.
CATALOG_HATS_DIR = HATS_DIR / CATALOG_HATS_NAME

### Caminho para o relatório de desempenho do Dask.
LOGS_DIR = Path(user_logs_dir) 

PERFORMANCE_REPORT_NAME = 'performance_report_make_hats_truth.html'
PERFORMANCE_DIR = LOGS_DIR / PERFORMANCE_REPORT_NAME
###########################################################################################

######################## CONFIGURAÇÃO DO CLUSTER ##########################################
# Configuração do SLURMCluster.
cluster = SLURMCluster(
    interface='ib0',    # Interface do Lustre
    queue='cpu_small',  # Substitua pelo nome da sua fila
    cores=50,           # Número de núcleos lógicos por nó
    processes=25,       # Número de processos por nó (um processo por núcleo)
    memory='80GB',     # Memória por nó
    walltime='02:30:00',  # Tempo máximo de execução
    job_extra_directives=[
        '--propagate',
        f'--output={LOGS_DIR}/make_hats_truth_dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={LOGS_DIR}/make_hats_truth_dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],                                             
)

# Escalando o cluster para usar X nós
cluster.scale(jobs=10)  

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
        raise Exception('The type of names of catalogs files (CATALOG_FILES) is not supported. Supported types are list and str.')
    
    if FILE_TYPE=='parquet':
        catalog_args = ImportArguments(
            sort_columns=CATALOG_SORT_COLUMN,
            ra_column=CATALOG_RA_COLUMN,
            dec_column=CATALOG_DEC_COLUMN,
            input_file_list=CATALOG_PATHS,
            file_reader=ParquetReader(column_names=CATALOG_SELECTED_COLUMNS),
            output_artifact_name=CATALOG_HATS_NAME,
            output_path=HATS_DIR,
        )
        pipeline_with_client(catalog_args, client)
    else:
        raise Exception('Input catalog type not supported yet.')
###########################################################################################
    
# Fechando o client
client.close()
cluster.close()