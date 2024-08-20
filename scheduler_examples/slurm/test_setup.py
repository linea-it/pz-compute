#!/usr/bin/env python3

'''Prepare directories and ancillary files to run 
   rail-estimate script in parallel using Slurm. 
   Write provenance info in text file. 

   Usage:
   
   prepare-pz-test [options] [--] <process_id> <comment> 
   prepare-pz-test -h | --help
   prepare-pz-test --version
   
   Options:
   -h --help   Show help text.
   --version   Show version.
   -a <algorithm>, --algorithm=<algorithm> fzboost, bpz, gpz, tpz.
   -p <process id>, --process_id=<process id> Integer or short string without 
                                               blank spaces to identify the 
                                               process. There is no warranty of
                                               uniqueness, only if in the same 
                                               parent directory. If empty, 
                                               attribute test_pz_compute_x where
                                               x is incremental integer.
   -c <comment>, --comment=<comment> Long string (enclosed in quotes) with the 
                                     process description. (optional) 
                                      
'''

import os
import sys
import shutil 
import argparse
import glob
import yaml
import getpass
from datetime import datetime


ENV = os.environ.get('ENVIRONMENT') or None
APP_PZ_COMPUTE_PATH = '/lustre/t0/scratch/users/app.photoz/pz-compute'
SCRATCH_PATH = os.environ.get('SCRATCH')

def parse_cmd():
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", "--process_id", help = "Integer or short string without blank spaces") 
    parser.add_argument("-c", "--comment", help = "Comment with process description (enclosed in quotes)") 
    parser.add_argument("-a", "--algorithm", help = "Specify the algorithm to run") 
    
    args = parser.parse_args()
    args.user = getpass.getuser()
    if args.algorithm == None:
        raise "Algorithm must be informed, options are: fzboost, bpz, tpz, gpz"
       
    user_input = input("Will you execute a train run? (yes/no): ").strip().lower()
    
    if user_input == 'yes' or user_input == 'y':
        args.will_train = True
    else:
        args.will_train = False
        
    return args


def represent_list(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

def print_output(args, yaml_file):
    print('---------------------------------------')
    print(f'Process ID: {args.process_id}')
    if not args.comment:
        args.comment = ' --- ' 
    print(f'User: {args.user}')
    print(f'Algorithm: {args.algorithm}')
    print(f'Description: {args.comment}')
    print('---------------------------------------')
    print()
    
    print(f'Process info saved in {yaml_file}')    
    print() 
    print() 

def create_yaml_process_file(args):
    yaml_file = f'./{args.process_id}/process_info.yaml'

    with open(yaml_file, 'w') as outfile:
        yaml.dump(vars(args), outfile, default_flow_style=False)
    
    return yaml_file

def create_yaml_pz_compute(args):
    yaml_file_config = f'./{args.process_id}/pz_compute.yaml'
    
    yaml.add_representer(list, represent_list)
    
    configs_pz_compute = {'algorithm': args.algorithm, 'sbatch_args': ["-N5", "-n140"]}
    
    with open(yaml_file_config, 'w') as outfile:
        yaml.dump(configs_pz_compute, outfile, default_flow_style=False)

def create_required_dirs(args):
    process_dir = f'./{args.process_id}' 
    try:
        os.makedirs(f'{process_dir}', exist_ok = True)
        os.makedirs(f'{process_dir}/input', exist_ok = True)
    except OSError as error:
        print('Failed to create directories')

def create_test_dir(args):
    if args.process_id:
        duplicate_id = os.path.isdir(args.process_id)
        if duplicate_id:
            print(f'Process {args.process_id} already exists!')
            print('Aborting...')
            quit()
    else: 
        old_process_ids = glob.glob('test_pz_compute_*') 
        if len(old_process_ids)>0:
            old_n = []
            for old_process_id in old_process_ids:
                old_n.append(int(old_process_id.split('_')[-1]))
            max_id = max(old_n)
            args.process_id = 'test_pz_compute_'+ str(max_id+1)
        else:
            args.process_id = 'test_pz_compute_0'
         
        
def create_link_to_host_performance(args):
    rail_path = ""
   
    if ENV == "prod":
        rail_path = f'{APP_PZ_COMPUTE_PATH}/performance'
    elif ENV == "dev":
        rail_path = f'{SCRATCH_PATH}/pz-compute/performance'
    else:
        print("Env not defined, not linking the performance script")
        return

    os.symlink(f'{rail_path}/slurm/slurm-analyze-host-performance.py', f'./{args.process_id}/slurm-analyze-host-performance.py')

def add_input_data(args):
    user_input = input("Do you want to use the complete LSST DP0.2 dataset? (yes/no): ").strip().lower()
    
    if user_input == 'yes' or user_input == 'y':
        if os.path.exists(f'{args.process_id}/input'):
            source_dir = '/lustre/t1/cl/lsst/dp0.2/secondary/catalogs/skinny/'
            pattern = '*.hdf5'
            target_dir = f'./{args.process_id}/input/'
            
            for file_path in glob.glob(os.path.join(source_dir, pattern)):
                filename = os.path.basename(file_path)
                target_file = os.path.join(target_dir, filename)

                try:
                    os.symlink(file_path, target_file)
                except FileExistsError:
                    print(f"File {target_file} already exists.")
                except Exception as e:
                    print(f"Error creating symbolic link to {file_path}: {e}")
            
            print("\nUsing the skinny tables for the complete LSST DP0.2\n")
        else:
            print("The input dir does not exists.")
    else:
        print("\nNot using the complete LSST DP0.2 dataset.")
        print(f'Please add manually the data in the input dir with the folowing command:\n ln -s <origin_path>/*.hdf5 {args.process_id}/input/')
        print()

def copy_configs_file(args):
    file_name_train = f"{args.algorithm}_train.yaml"
    file_name_estimate = f"{args.algorithm}_estimate.yaml"
    dst = f"./{args.process_id}/"
    
    if ENV == "prod":
        if args.will_train:
            src = f'{APP_PZ_COMPUTE_PATH}/doc/algorithms_config/{file_name_train}'
            shutil.copy(src, dst)

        src = f'{APP_PZ_COMPUTE_PATH}/doc/algorithms_config/{file_name_estimate}'
        shutil.copy(src, dst)

    elif ENV == "dev":
        if args.will_train:
            src = f'{SCRATCH}/pz-compute/doc/algorithms_config/{file_name_train}'
            shutil.copy(src, dst)

        src = f'{SCRATCH}/pz-compute/doc/algorithms_config/{file_name_estimate}'
        shutil.copy(src, dst)
    else:
        print("Env not defined, not creating the configurations yaml")
        return

    
def main():
    args = parse_cmd() 
    
    create_test_dir(args)
    create_required_dirs(args)
    
    add_input_data(args)
    
    create_yaml_pz_compute(args)
    yaml_file = create_yaml_process_file(args)
    
    print_output(args, yaml_file)
    
    create_link_to_host_performance(args)
    copy_configs_file(args)
    
if __name__ == '__main__': main()
