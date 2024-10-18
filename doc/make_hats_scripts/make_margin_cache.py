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
### Diretório do catálogo hats de input.
CATALOG_HATS_DIR = Path(f'/lustre/t0/scratch/users/{user}/hats_files/output/hats/test_truth_hats')
MARGIN_CACHE_THRESHOLD = 1.0 #arcsec
CATALOG_MARGIN_CACHE_NAME = "test_truth_margin_cache"
###########################################################################################

################################# CONFIGURAÇÕES DE OUTPUT #################################
### Diretório de output para os catálogos.
OUTPUT_DIR = Path(user_output_dir)
HATS_DIR_NAME = "hats"
HATS_DIR = OUTPUT_DIR / HATS_DIR_NAME

CATALOG_MARGIN_CACHE_DIR = HATS_DIR / CATALOG_MARGIN_CACHE_NAME

### Caminho para o relatório de desempenho do Dask.
LOGS_DIR = Path(user_logs_dir)

PERFORMANCE_REPORT_NAME = 'performance_report_make_margin_cache.html'
PERFORMANCE_DIR = LOGS_DIR / PERFORMANCE_REPORT_NAME
###########################################################################################

######################## CONFIGURAÇÃO DO CLUSTER ##########################################
# Configuração do SLURMCluster.
cluster = SLURMCluster(
    interface="ib0",    # Interface do Lustre
    queue='cpu_small',  # Substitua pelo nome da sua fila
    cores=50,           # Número de núcleos lógicos por nó
    processes=25,       # Número de processos por nó (um processo por núcleo)
    memory='80GB',     # Memória por nó
    walltime='02:30:00',  # Tempo máximo de execução
    job_extra_directives=[
        '--propagate',
        f'--output={LOGS_DIR}/make_margin_cache_dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={LOGS_DIR}/make_margin_cache_dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],                                             
)

# Escalando o cluster para usar X nós
cluster.scale(jobs=10)  

# Definindo o client do Dask
client = Client(cluster)
###########################################################################################


############################### EXECUTANDO O PIPELINE ######################################
with performance_report(filename=PERFORMANCE_DIR):   
    ### Getting informations from the catalog.
    catalog = hats.read_hats(CATALOG_HATS_DIR)
    info_frame = catalog.partition_info.as_dataframe()
    info_frame = info_frame.astype(int)
        
    ### Computing the margin cache, if it is possible.
    number_of_pixels = len(info_frame["Npix"])
    if number_of_pixels <= 1:
        warnings.warn(f"Number of pixels is equal to {number_of_pixels}. Impossible to compute margin cache.")
    else:
        margin_cache_args = MarginCacheArguments(
            input_catalog_path=CATALOG_HATS_DIR,
            output_path=HATS_DIR,
            margin_threshold=MARGIN_CACHE_THRESHOLD,  # arcsec
            output_artifact_name=CATALOG_MARGIN_CACHE_NAME,
        )
        pipeline_with_client(margin_cache_args, client)
###########################################################################################
    
# Fechando o client
client.close()
cluster.close()