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
import shutil
import h5py

import qp

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
                    
    plt.figure(figsize=(12, 8))
    plt.hlines(process_ids, start_times, end_times, color='k', linewidth=0.2)

    plt.scatter(start_times, process_ids, color='teal', label='Start', s=2, zorder=2)
    plt.scatter(end_times, process_ids, color='teal', label='End', s=2, zorder=3)

    plt.title(f'Time profiler of {len(process_ids)} Processes')
    plt.xlabel('time')
    plt.ylabel('Process ID')
    plt.grid(True, linestyle='--')
    plt.legend()

    output_img_path = os.path.join(process_dir, f'processes_time_profiler.png')
    plt.savefig(output_img_path)

def run_paralell_post_process(process_dir):
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

    cluster.scale(jobs=10)

    client = Client(cluster)   

    performance_report_path = os.path.join(process_dir, f'dask_performance_report.html')
    file_to_copy = None
    
    print("\nBuilding plots...")
    with performance_report(filename=performance_report_path):
        file_list = glob.glob(f'{process_dir}/output/*.hdf5')
        file_to_copy = file_list[0]
        has_zmode = False
        has_pdfs = False
        bins = []
        
        data = tables_io.read(file_to_copy)
        total_objects = 0
        
        if 'data' in data:
            if 'yvals' in data['data']:
                has_pdfs = True

        if 'ancil' in data:
            if 'zmode' in data['ancil']:
                has_zmode = True
        
        if 'meta' in data:
            if 'xvals' in data['meta']:
                bins = data['meta']["xvals"][0]
            else:
                bins = np.linspace(0,3,301)
        else:
            bins = np.linspace(0,3,301)
            
        def read_zmodes(file):
            data = tables_io.read(file)

            zmodes = data['ancil']['zmode'][:]
            
            n = plt.hist(zmodes, bins)
            df = pd.DataFrame(n[0]).T
            df['objects']= int(len(zmodes))

            return df
        
        def read_pdfs(file):
            data = tables_io.read(file)

            y_vals = data['data']['yvals'][:]
            number_objects = len(y_vals)
            
            y_vals_sum = np.sum(y_vals, axis=0)
            df = pd.DataFrame(y_vals_sum).T

            df['objects']= int(number_objects)

            return df

        def transform_output_to_ensenble(yval):
            output_file_hdf5 = 'stacked_output_pdfs.hdf5'
            shutil.copy(file_to_copy, output_file_hdf5)
            
            with h5py.File(file_to_copy, 'r') as f_src:
                with h5py.File(output_file_hdf5, 'w') as f_dst:
                    data_group = f_dst.create_group('data')
                    data_group.create_dataset('yvals', data=[yval], dtype='f8') 
                    meta_group = f_dst.create_group('meta')
                    meta_group.create_dataset('pdf_name', data=[f_src['meta']["pdf_name"][0]], dtype=h5py.string_dtype(encoding='ascii', length=6))
                    meta_group.create_dataset('pdf_version', data=[f_src['meta']["pdf_version"][0]], dtype='i8')
                    meta_group.create_dataset('xvals', data=[bins], dtype='f8')
                    
            return qp.read(output_file_hdf5)
        
        def plot_stack_pdfs(ens):
            test_xvals = ens.gen_obj.xvals
            pdfs = ens.pdf(test_xvals)
            pdfs_stack = pdfs.sum(axis=0)
            mean = ens.mean()

            peak = pdfs_stack.max()
            x_peak = test_xvals[np.where(pdfs_stack == peak)][0]
            peak = round(peak, 2)
            x_peak = round(x_peak, 2)
            mean = round(mean[0][0], 2) 

            plt.plot(test_xvals, pdfs_stack)

            plt.vlines(mean, 0, peak+0.2, label=f'z mean: {mean}', linestyles='dashed')
            plt.plot(x_peak, peak, marker = 'o', label=f'value of z {x_peak}, peak of data: {peak}')

            plt.xlabel('z values', fontsize=11)
            plt.ylabel('stack pdfs', fontsize=11)
            plt.axis([0, test_xvals.max(), 0, peak+0.2])

            plt.title("Pdfs distribuition")
            plt.legend(loc="upper right")

            output_img_path = os.path.join(process_dir, f'stack_pdfs.png')
            plt.savefig(output_img_path)
            
            plt.close('all')
            
        def plot_stack_zmode(zmodes):
            plt.plot(np.linspace(0,3,len(zmodes)), zmodes)
            
            plt.title("Zmode distribuition")
            plt.xlabel('z values', fontsize=11)
            plt.ylabel('stack zmodes', fontsize=11)

            output_img_path = os.path.join(process_dir, f'stack_zmode.png')
            plt.savefig(output_img_path)
            
            plt.close('all')
        

        if has_zmode:
            print("Output files have z-modes")
            parts = [delayed(read_zmodes)(file) for file in file_list]
        
            ddf = dd.from_delayed(parts)
            ddf_computed = ddf.compute()
            data = ddf_computed.sum(axis=0)
            
            total_objects = int(data['objects'])
            ddf_computed.to_csv("stacked_zmodes.csv", index=False)
            
            data.drop(['objects'], inplace=True)
            plot_stack_zmode(data)
        
        if has_pdfs:
            print("Output files have yvals (pdfs)")
        
            parts = [delayed(read_pdfs)(file) for file in file_list]
        
            ddf = dd.from_delayed(parts)
            ddf_computed = ddf.compute()
            data = ddf_computed.sum(axis=0)
            ddf_computed.to_csv("stacked_pdfs.csv", index=False)
            
            total_objects = int(data['objects'])
            data.drop(['objects'], inplace=True)

            #stacked_yval = [x for x in data]

            ens = transform_output_to_ensenble(data)
            plot_stack_pdfs(ens)
        
        return f'{total_objects:_}'

    client.close()
    cluster.close()