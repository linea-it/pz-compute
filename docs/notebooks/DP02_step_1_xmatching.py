################################### IMPORTAÇÕES ###########################################
############################ GERAL ###########################
import os
from pathlib import Path
############################ DASK ############################
from dask.distributed import Client, performance_report
from dask_jobqueue import SLURMCluster
######################## LSDB ######################
import lsdb
###########################################################################################


######################## CONFIGURAÇÃO DO CLUSTER ##########################################
# Configuração do SLURMCluster para usar 12 nós com 56 núcleos lógicos e 128GB de RAM cada
cluster = SLURMCluster(
    interface="ib0",    # Interface do Lustre
    queue='cpu_small',  # Substitua pelo nome da sua fila
    cores=56,           # Número de núcleos lógicos por nó
    processes=56,       # Número de processos por nó (um processo por núcleo)
    memory='100GB',     # Memória por nó
    walltime='01:00:00',  # Tempo máximo de execução
    job_extra_directives=['--propagate'],  # Argumentos adicionais para o SLURM
)

# Escalando o cluster para usar 10 nós
cluster.scale(jobs=10)  # Defina para usar 10 nós

# Definindo o client do Dask
client = Client(cluster)
###########################################################################################


################################## CONFIGURAÇÕES DE INPUT #################################
LEFT_HIPSCAT_DIR = Path("/lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/output/hipscat/dp0.2_random")
LEFT_CATALOG_HIPSCAT_NAME = "dp0.2_random"
RIGHT_HIPSCAT_DIR = Path("/lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/output/hipscat/dp0.1_truth")
RIGHT_CATALOG_HIPSCAT_NAME = "dp0.1_truth"
RIGHT_MARGIN_CACHE_DIR = Path("/lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/output/hipscat/dp0.1_truth_MC")

CROSS_MATCHING_RADIUS = 1.0 # Up to 1 arcsec distance, it is the default
NEIGHBORS_NUMBER = 1 # Single closest object, it is the default
###########################################################################################

################################# CONFIGURAÇÕES DE OUTPUT #################################
OUTPUT_DIR = Path("/lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/output/")
HIPSCAT_DIR_NAME = "hipscat"
HIPSCAT_DIR = OUTPUT_DIR / HIPSCAT_DIR_NAME

XMATCH_NAME = LEFT_CATALOG_HIPSCAT_NAME+'_x_'+RIGHT_CATALOG_HIPSCAT_NAME
OUTPUT_HIPSCAT_DIR = HIPSCAT_DIR / XMATCH_NAME

PERFORMANCE_REPORT_NAME = 'performance_report_xmatching.html'
PERFORMANCE_DIR = OUTPUT_DIR / PERFORMANCE_REPORT_NAME
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