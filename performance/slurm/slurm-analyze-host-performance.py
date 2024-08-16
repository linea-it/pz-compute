#!/usr/bin/env python3
import yaml
import os

from collections import namedtuple
from datetime import datetime
from re import search, match, compile
from sys import argv, stdin


JOB_EXECUTING = \
        r'[.](\d+)[.].*(\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Starting: rail-estimate *<(.*):'

JOB_TERMINATED = \
    r'[.](\d+)[.].*(\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Finished: rail-estimate'

file_pattern = compile(r'slurm-(\d+)\.out')
process_info_file = 'process_info.yaml'


def calculate_duration(start_time, end_time):
    start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f")
    end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S.%f")
    return end - start

def save_info_yaml_process_info(begins, ends, duration):    
    time_dict = {'Process started': str(begins),
                 'Process finished': str(ends),
                 'Total duration': str(duration)}

    with open(process_info_file,'r') as yamlfile:
        cur_yaml = yaml.safe_load(yamlfile)
        cur_yaml['time stats'] = time_dict
    with open('process_info.yaml','a') as yamlfto:
        yaml.safe_dump(cur_yaml, yamlfto)
        
    print(f'Information saved in {process_info_file}')

def find_slurm_file():
    file = None
    
    if len(argv) > 1:
        file = open(argv[1])
    else:
        max_num = 0

        current_dir = os.path.abspath(os.getcwd())
        
        for filename in os.listdir(current_dir):
            match = file_pattern.match(filename)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
                    file = filename
    return file
              
def main():
    file = find_slurm_file()
    if file:
        print(f"\nReading {file} file\n")
    else:
        print("No slurm log files found")
        return;
    

    start_time = None
    end_time = None
    duration = None
    
    with open(file, 'r') as file:
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
    else:
        print(f"Process not started or finished yet.")
        return;

    save_info_yaml_process_info(start_time, end_time, duration)
    

if __name__ == '__main__': main()