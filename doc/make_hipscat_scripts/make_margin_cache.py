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
######################## HIPSCAT ######################
### HIPSCAT
import hipscat
from hipscat_import.catalog.file_readers import ParquetReader
from hipscat_import.margin_cache.margin_cache_arguments import MarginCacheArguments
from hipscat_import.pipeline import ImportArguments, pipeline_with_client  
###########################################################################################

######################### CONFIGURAÇÃO DOS PATHS DO USUÁRIO ###############################
# Identificar o path do usuário
user = getpass.getuser()
base_path = f'/lustre/t0/scratch/users/{user}/hipscat_files'

# Criar pastas 'output' e 'logs' se não existirem
user_output_dir = os.path.join(base_path, 'output')
user_logs_dir = os.path.join(base_path, 'logs')
os.makedirs(user_output_dir, exist_ok=True)
os.makedirs(user_logs_dir, exist_ok=True)
###########################################################################################

################################## CONFIGURAÇÕES DE INPUT #################################
### Diretório do catálogo hipscat de input.
CATALOG_HIPSCAT_DIR = Path(f'/lustre/t0/scratch/users/{user}/hipscat_files/output/hipscat/test_truth_hipscat')
MARGIN_CACHE_THRESHOLD = 1.0 #arcsec
CATALOG_MARGIN_CACHE_NAME = "test_truth_margin_cache"
###########################################################################################

################################# CONFIGURAÇÕES DE OUTPUT #################################
### Diretório de output para os catálogos.
OUTPUT_DIR = Path(user_output_dir)
HIPSCAT_DIR_NAME = "hipscat"
HIPSCAT_DIR = OUTPUT_DIR / HIPSCAT_DIR_NAME

CATALOG_MARGIN_CACHE_DIR = HIPSCAT_DIR / CATALOG_MARGIN_CACHE_NAME

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
    catalog = hipscat.read_from_hipscat(CATALOG_HIPSCAT_DIR)

    info_frame = catalog.partition_info.as_dataframe()

    for index, partition in info_frame.iterrows():
        file_name = result = hipscat.io.paths.pixel_catalog_file(
            CATALOG_HIPSCAT_DIR, partition["Norder"], partition["Npix"]
        )
        info_frame.loc[index, "size_on_disk"] = os.path.getsize(file_name)

    info_frame = info_frame.astype(int)
    info_frame["gbs"] = info_frame["size_on_disk"] / (1024 * 1024 * 1024)
        
    ### Computing the margin cache, if it is possible.
    number_of_pixels = len(info_frame["Npix"])
    if number_of_pixels <= 1:
        warnings.warn(f"Number of pixels is equal to {number_of_pixels}. Impossible to compute margin cache.")
    else:
        margin_cache_args = MarginCacheArguments(
            input_catalog_path=CATALOG_HIPSCAT_DIR,
            output_path=HIPSCAT_DIR,
            margin_threshold=MARGIN_CACHE_THRESHOLD,  # arcsec
            output_artifact_name=CATALOG_MARGIN_CACHE_NAME,
        )
        pipeline_with_client(margin_cache_args, client)
###########################################################################################
    
# Fechando o client
client.close()
cluster.close()