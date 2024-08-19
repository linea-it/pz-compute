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
CATALOG_HIPSCAT_DIR = Path("/lustre/t0/scratch/users/luigi.silva/random_from_files/truth_z_hipscat")
MARGIN_CACHE_THRESHOLD = 1.0 #arcsec
###########################################################################################

################################# CONFIGURAÇÕES DE OUTPUT #################################
### Diretório de output para os catálogos.
OUTPUT_DIR = Path("/lustre/t0/scratch/users/luigi.silva")
HIPSCAT_DIR_NAME = "random_from_files"
HIPSCAT_DIR = OUTPUT_DIR / HIPSCAT_DIR_NAME

### Nomes para os outputs do catalógo e do cache de margem no formato HiPSCat.
CATALOG_MARGIN_CACHE_NAME = "truth_z_hipscat_margin_cache"

CATALOG_MARGIN_CACHE_DIR = HIPSCAT_DIR / CATALOG_MARGIN_CACHE_NAME

### Caminho para o relatório de desempenho do Dask.
LOGS_DIR_NAME = "logs_truth_z_hipscat_margin_cache"
LOGS_DIR = HIPSCAT_DIR / LOGS_DIR_NAME 

PERFORMANCE_REPORT_NAME = 'performance_report_make_margin_cache.html'
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
    walltime='10:00:00',  # Tempo máximo de execução
    job_extra_directives=[
        '--propagate',
        f'--output={LOGS_DIR}/dask_job_%j.out',  # Redireciona a saída para a pasta output
        f'--error={LOGS_DIR}/dask_job_%j.err'    # Redireciona o erro para a pasta output
    ],                                             # Argumentos adicionais para o SLURM
)

# Escalando o cluster para usar X nós.
cluster.scale(jobs=14) 

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