################################### IMPORTAÇÕES ###########################################
############################ GERAL ###########################
import os
import getpass
from pathlib import Path
############################ DASK ############################
from dask.distributed import Client, performance_report
from dask_jobqueue import SLURMCluster
######################## LSDB ######################
import lsdb
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
LEFT_HIPSCAT_DIR = Path('/lustre/t1/cl/lsst/dp02/secondary/catalogs/hipscat/')
LEFT_CATALOG_HIPSCAT_NAME = 'dp02_object'
RIGHT_HIPSCAT_DIR = Path('/lustre/t1/cl/lsst/pz_project/test_data/truth_z_hipscat')
RIGHT_CATALOG_HIPSCAT_NAME = 'dp01_random_sample_truth'
RIGHT_MARGIN_CACHE_DIR = Path('/lustre/t1/cl/lsst/pz_project/test_data/truth_z_hipscat_margin_cache')

CROSS_MATCHING_RADIUS = 1.0 # Up to 1 arcsec distance, it is the default
NEIGHBORS_NUMBER = 1 # Single closest object, it is the default
###########################################################################################

################################# CONFIGURAÇÕES DE OUTPUT #################################
OUTPUT_DIR = Path(user_output_dir)
HIPSCAT_DIR_NAME = 'hipscat'
HIPSCAT_DIR = OUTPUT_DIR / HIPSCAT_DIR_NAME

XMATCH_NAME = LEFT_CATALOG_HIPSCAT_NAME+'_x_'+RIGHT_CATALOG_HIPSCAT_NAME
OUTPUT_HIPSCAT_DIR = HIPSCAT_DIR / XMATCH_NAME

### Caminho para o relatório de desempenho do Dask.
LOGS_DIR = Path(user_logs_dir)

PERFORMANCE_REPORT_NAME = 'performance_report_make_xmatching.html'
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
        f'--output={LOGS_DIR}/make_xmatching_dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={LOGS_DIR}/make_xmatching_dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],                                             
)

# Escalando o cluster para usar X nós
cluster.scale(jobs=10)  

# Definindo o client do Dask
client = Client(cluster)
###########################################################################################

############################### EXECUTANDO O PIPELINE ######################################
with performance_report(filename=PERFORMANCE_DIR):
    ### Lendo os dados salvos no formato HiPSCat.
    left_catalog = lsdb.read_hipscat(LEFT_HIPSCAT_DIR)
    right_margin_cache_catalog = lsdb.read_hipscat(RIGHT_MARGIN_CACHE_DIR)
    right_catalog = lsdb.read_hipscat(RIGHT_HIPSCAT_DIR, margin_cache=right_margin_cache_catalog)
    
    ### Executando o crossmatching.
    xmatched = left_catalog.crossmatch(
        right_catalog,
        radius_arcsec=CROSS_MATCHING_RADIUS,
        n_neighbors=NEIGHBORS_NUMBER,
        suffixes=(LEFT_CATALOG_HIPSCAT_NAME, RIGHT_CATALOG_HIPSCAT_NAME),
    )
    xmatched.to_hipscat(OUTPUT_HIPSCAT_DIR)
    

# Fechando o client
client.close()
cluster.close()