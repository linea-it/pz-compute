#!/usr/bin/env python3
import yaml
import os
import subprocess

import post_process_pz_compute

from collections import namedtuple
from datetime import datetime
from re import search, match, compile
from sys import argv, stdin

file_pattern = compile(r'slurm-(\d+)\.out')
process_info_file = 'process_info.yaml'
current_dir = os.path.abspath(os.getcwd())

def get_directory_size(directory):
    result = subprocess.run(['du', '-sh', directory], capture_output=True, text=True)

    if result.returncode == 0:
        size_str = result.stdout.split()[0]
        return size_str
    else:
        raise Exception(f"Error: {result.stderr}")

def output_basic_info():
    input_path = os.listdir(f'{current_dir}/input')
    output_path = os.listdir(f'{current_dir}/output')
    
    files_processed = f"{len(output_path)}/{len(input_path)} files processed"    
    total_size = get_directory_size(f'{current_dir}/output/');
    
    print(files_processed)
    print("Output size:", total_size)
    
    return total_size, files_processed

def calculate_duration(start_time, end_time):
    start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f")
    end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S.%f")
    return end - start

def save_info_yaml_process_info(begins, ends, duration, total_size, files_processed, objects):    
    time_dict = {'Process started': str(begins),
                 'Process finished': str(ends),
                 'Total duration': str(duration),
                 'Files count': str(files_processed),
                 'Output size': str(total_size),
                 'Total objects': objects
                }

    with open('process_info.yaml','a') as yamlfile:
        cur_yaml = {"time stats": time_dict}
        yaml_text = yaml.dump(cur_yaml)
        yamlfile.write(yaml_text)
     
    print(f'\nInformation saved in {process_info_file}')

def find_slurm_file():
    file = None
    
    if len(argv) > 1:
        file = open(argv[1])
    else:
        max_num = 0
        
        for filename in os.listdir(current_dir):
            match = file_pattern.match(filename)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
                    file = filename
    return file

def main():
    file_path = find_slurm_file()
    if file_path:
        print(f"\nReading {file_path} file\n")
    else:
        print("No slurm log files found")
        return;
    
    start_time = None
    end_time = None
    duration = None
    
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            if 'Starting: rail-estimate' in line:
                start_time = line.split(': ')[0]
            elif 'Finished: rail-estimate' in line:
                end_time = line.split(': ')[0]

    if start_time and end_time:
        duration = calculate_duration(start_time, end_time)
        print(f"Starting time rail-estimate: {start_time}")
        print(f"Finished time rail-estimate: {end_time}")
        print(f"Total duration rail-estimate: {duration}")
        print()
    else:
        if start_time and end_time is None:
            print(f"Process still running")
        else:
            print("there was an error running the process")
        return;

    total_size, files_processed = output_basic_info()
    total_objects = post_process_pz_compute.run_paralell_post_process(current_dir)
    save_info_yaml_process_info(start_time, end_time, duration, total_size, files_processed, total_objects)
    post_process_pz_compute.time_profiler(current_dir, file_path)
    

if __name__ == '__main__': main()