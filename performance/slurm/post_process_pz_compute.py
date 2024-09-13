import os
import dask
import numpy as np
import pandas as pd
import glob
import psutil
import time
import tables_io
import getpass
import matplotlib.pyplot as plt


from dask import dataframe as dd
from dask import delayed
from dask.distributed import Client, performance_report
from dask_jobqueue import SLURMCluster
from re import search
from datetime import datetime

JOB_EXECUTING = \
    r'\d{4}-(?P<start_time>\d{2}-\d{2} \d{2}:\d{2}:\d{2}\..*): Starting: rail-estimate .* id=(?P<process_id>\d+)'

JOB_TERMINATED = \
    r'\d{4}-(?P<finish_time>\d{2}-\d{2} \d{2}:\d{2}:\d{2}\..*): Finished: rail-estimate .* id=(?P<process_id>\d+)'


def time_profiler(process_dir, file_path):
    times = {}

    process_ids = []
    start_times = [] 
    durations = []  
    end_times = [] 

    with open(file_path, 'r') as file:
        for line in file:
            m = search(JOB_EXECUTING, line)
            if m:
                task_id = int(m.group('process_id'))
                start_time = datetime.strptime(m.group('start_time'), '%m-%d %H:%M:%S.%f')
                times[task_id] = start_time

            m = search(JOB_TERMINATED, line)
            if m:
                task_id = int(m.group('process_id'))

                if task_id in times:
                    time_end = datetime.strptime(m.group('finish_time'), '%m-%d %H:%M:%S.%f')
                    time_begin = times[task_id]
                    time_diff = time_end - time_begin

                    process_ids.append(task_id)
                    start_times.append(time_begin)
                    end_times.append(time_end)
                    durations.append(time_diff)
                else:
                    raise "error while collecting time os processes"
                    
    plt.figure(figsize=(16, 12))
    plt.hlines(process_ids, start_times, end_times, color='k', linewidth=0.2)

    plt.scatter(start_times, process_ids, color='teal', label='Start', s=2, zorder=2)
    plt.scatter(end_times, process_ids, color='teal', label='End', s=2, zorder=3)

    plt.title(f'Time profiler of {len(process_ids)} Processes')
    plt.xlabel('time (s)')
    plt.ylabel('Process ID')
    plt.grid(True, linestyle='--')
    plt.legend()

    output_img_path = os.path.join(process_dir, f'processes_time_profiler.png')
    plt.savefig(output_img_path)

def run_paralell_post_process(process_dir):
    # Criar pastas 'output' e 'logs' se não existirem
    output_dir = os.path.join(process_dir, 'output_dask')
    logs_dir = os.path.join(process_dir, 'logs_dask')
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    
    
    cluster = SLURMCluster(
        interface="ib0",    # Interface do Lustre
        queue='cpu_small',  # Substitua pelo nome da sua fila
        cores=56,           # Número de núcleos lógicos por nó
        processes=28,       # Número de processos por nó (um processo por núcleo)
        memory='100GB',     # Memória por nó
        walltime='01:00:00',  # Tempo máximo de execução
        job_extra_directives=[
            '--propagate',
            f'--output={output_dir}/dask_job_%j.out',  # Redireciona a saída para a pasta output
            f'--error={output_dir}/dask_job_%j.err'    # Redireciona o erro para a pasta output
        ],
    )

    # Escalando o cluster para usar X nós
    cluster.scale(jobs=6)

    # Definindo o client do Dask
    client = Client(cluster)   

    # Caminho para o relatório de desempenho do Dask
    performance_report_path = os.path.join(process_dir, f'dask_performance_report.html')
    
    with performance_report(filename=performance_report_path):
        # Obter lista de arquivos HDF5 na pasta
        file_list = glob.glob(f'{process_dir}/output/*.hdf5')

        # Ler todos os arquivos HDF5 com dask delayed.
        def read_hdf5(file):
            #data = tables_io.read(file)

            #y_vals = data['data']['yvals'][:]

            #y_vals_sum = np.sum(y_vals, axis=0)
            #df = pd.DataFrame(y_vals_sum).T

            #df['objects']= int(len(y_vals))
            
            ens = qp.read(file)
            number_objects = ens.npdf
            
            pdfs = ens.pdf(test_xvals)
            pdfs_stack = np.sum(pdfs, axis=0)
            
            df = pd.DataFrame(pdfs_stack).T
            df['objects']= ens.npdf
            
            return df
        
        # Ler os arquivos usando dask.delayed
        parts = [delayed(read_hdf5)(file) for file in file_list]
        ddf = dd.from_delayed(parts)
        
        ddf_computed = ddf.compute()
        data = ddf_computed.sum(axis=0)
        
        total_objects = data['objects']
        zmode_values=pd.DataFrame(data.drop(['objects']))
        
        #apagar mais pra frente
        output_path_csv = os.path.join(process_dir, f'sample.csv')
        zmode_values.to_csv(output_path_csv, index=False)
        
        output_path_parquet = os.path.join(process_dir, f'sample.parquet')
        zmode_values.to_parquet(output_path_parquet, index=False)
        
        output_path_hdf5 = os.path.join(process_dir, f'sample.hdf5')
        tables_io.write(zmode_values, output_path_hdf5)
        ######
        
        output_img_path = os.path.join(process_dir, f'stack_nz.png')
        plt.plot(zmode_values)
        plt.savefig(output_img_path)
        
        return total_objects

    # Fechando o client
    client.close()
    cluster.close()