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
### Diretório e nome dos arquivos de input. O nome pode ser uma lista ou conter um wildcard, ex: files_*.parquet.
#CATALOG_DIR = Path("/lustre/t1/cl/lsst/dp0/lsst_dp0/")
#CATALOG_FILES = ['truth_tract5065.parquet', 'truth_tract5066.parquet', 'truth_tract5067.parquet']
### Colunas a serem selecionadas no arquivo de input. As colunas de id, ra e dec são indispensáveis.
#CATALOG_SELECTED_COLUMNS = ['id', 'ra', 'dec', 'redshift', 'truth_type']
#CATALOG_SORT_COLUMN = "id"
#CATALOG_RA_COLUMN = "ra"
#CATALOG_DEC_COLUMN = "dec"
#FILE_TYPE = "parquet"
#GENERATE_MARGIN_CACHE = True
#MARGIN_CACHE_THRESHOLD = 1.0 #arcsec

### Diretório e nome dos arquivos de input. O nome pode ser uma lista ou conter um wildcard, ex: files_*.parquet.
CATALOG_DIR = Path("/lustre/t0/scratch/users/julia/photoz/poster_andreia_rcw24/training_sets/test_random_luigi/output/")
CATALOG_FILES = "random_sample_i_24.1_0.002.parquet"
### Colunas a serem selecionadas no arquivo de input. As colunas de id, ra e dec são indispensáveis.
CATALOG_SELECTED_COLUMNS = ['coord_dec', 'coord_ra', 'mag_g', 'mag_i', 'mag_r', 'mag_u', 'mag_y', 
                            'mag_z', 'magerr_g', 'magerr_i', 'magerr_r', 'magerr_u', 'magerr_y',
                            'magerr_z', 'objectId']
CATALOG_SORT_COLUMN = "objectId"
CATALOG_RA_COLUMN = "coord_ra"
CATALOG_DEC_COLUMN = "coord_dec"
FILE_TYPE = "parquet"
GENERATE_MARGIN_CACHE = True
MARGIN_CACHE_THRESHOLD = 1.0 #arcsec
###########################################################################################

################################# CONFIGURAÇÕES DE OUTPUT #################################
### Diretório de output para os catálogos.
OUTPUT_DIR = Path("/lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/output/")
HIPSCAT_DIR_NAME = "hipscat"
HIPSCAT_DIR = OUTPUT_DIR / HIPSCAT_DIR_NAME

### Nomes para os outputs do catalógo e do cache de margem no formato HiPSCat.
#CATALOG_HIPSCAT_NAME = "dp0.1_truth"
#CATALOG_MARGIN_CACHE_NAME = "dp0.1_truth_MC"

CATALOG_HIPSCAT_NAME = "dp0.2_random"
CATALOG_MARGIN_CACHE_NAME = "dp0.2_random_MC"

CATALOG_HIPSCAT_DIR = HIPSCAT_DIR / CATALOG_HIPSCAT_NAME
CATALOG_MARGIN_CACHE_DIR = HIPSCAT_DIR / CATALOG_MARGIN_CACHE_NAME

### Caminho para o relatório de desempenho do Dask.
PERFORMANCE_REPORT_NAME = 'performance_report_make_hipscat.html'
PERFORMANCE_DIR = OUTPUT_DIR / PERFORMANCE_REPORT_NAME
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
            #pixel_threshold=left_threshold,
        )
        pipeline_with_client(catalog_args, client)
    else:
        raise Exception("Input catalog type not supported yet.")
    
    if GENERATE_MARGIN_CACHE==True:
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