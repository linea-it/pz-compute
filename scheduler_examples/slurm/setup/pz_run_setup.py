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


ENV = os.environ.get('ENVIRONMENT') or "dev"
SCRATCH = os.environ.get('SCRATCH')

APP_PZ_COMPUTE_PATH = '/lustre/t0/scratch/users/app.photoz/pz-compute'
LSST_DP02 = '/lustre/t1/cl/lsst/dp02/secondary/catalogs/skinny/hdf5/'

class SetupDir:
    def __init__(self, process_id, comment, algorithm, will_train, creation_path, use_all_dp0_dataset):
        self.process_id = process_id #"Integer or short string without blank spaces"
        self.comment = comment       #"Comment with process description (enclosed in quotes)"
        self.algorithm = algorithm   #"Specify the algorithm to run"
        self.will_train = will_train
        self.user = getpass.getuser()
        self.creation_path = creation_path
        self.use_all_dp0_dataset = use_all_dp0_dataset

def set_process_id(process_id, algorithm, creation_path):
    if process_id:
        duplicate_id = os.path.isdir(os.path.join(creation_path, process_id))
        if duplicate_id:
            raise Exception(f'Process {process_id} already exists!\nAborting...')
    else: 
        old_process_ids = glob.glob(f'{creation_path}/test_pz_compute_{algorithm}*') 
        if len(old_process_ids)>0:
            old_n = []
            for old_process_id in old_process_ids:
                old_n.append(int(old_process_id.split('_')[-1]))
            max_id = max(old_n)
            process_id = f'test_pz_compute_{algorithm}_'+ str(max_id+1)
        else:
            process_id = f'test_pz_compute_{algorithm}_0'
    
    return process_id
        
def define_setup_dir(process_id, comment, algorithm, will_train, creation_path, use_all_dp0_dataset):
    
    if algorithm == None:
        raise Exception("Algorithm must be informed, options are: fzboost, bpz, tpz, gpz")
       
    if will_train == False:
        print("Train run not defined, remember to add the .pkl file")
        
    if creation_path is None:
        print("Creation path not defined, setting it to your scratch")
        creation_path = SCRATCH
    
    process_id = set_process_id(process_id, algorithm, creation_path)
    
    return SetupDir(process_id, comment, algorithm, will_train, creation_path, use_all_dp0_dataset)
        
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
        print("remember to add the .pkl file for your run")
        args.will_train = False    
    
    user_input = input("Do you want to use the complete LSST DP0.2 dataset? (yes/no): ").strip().lower()
    if user_input == 'yes' or user_input == 'y':
        args.use_all_dp0_dataset = True
    else:
        print("remember to add the .pkl file for your run")
        args.use_all_dp0_dataset = False 
    
    return args


def represent_list(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

def print_output(configs, yaml_file):
    print('---------------------------------------')
    print(f'Process ID: {configs.process_id}')
    if not configs.comment:
        configs.comment = ' --- ' 
    print(f'User: {configs.user}')
    print(f'Algorithm: {configs.algorithm}')
    print(f'Description: {configs.comment}')
    print('---------------------------------------')
    print()
    
    print(f'Process info saved in {yaml_file}')    
    print()

def create_yaml_process_file(configs):
    yaml_file = f'{configs.creation_path}/{configs.process_id}/process_info.yaml'
    dictionary = dict(
        process_id=configs.process_id, 
        user=configs.user,
        algorithm=configs.algorithm,
        comment=configs.comment,
        will_train=configs.will_train,
    )
    with open(yaml_file, 'w') as outfile:
        yaml.dump(dictionary, outfile, default_flow_style=False)
        # yaml.dump(vars(configs), outfile, default_flow_style=False)
    
    return yaml_file

def create_yaml_pz_compute_train(configs):
    yaml_file_config = f'{configs.creation_path}/{configs.process_id}/pz-train.yaml'
    
    yaml.add_representer(list, represent_list)
    
    configs_train = {'algorithm': configs.algorithm, 'sbatch_args': ["-N1", "-n1"], 'param_file':f"{configs.algorithm}_train.yaml", 'inputfile':"train-file.hdf5"}
    
    with open(yaml_file_config, 'w') as outfile:
        yaml.dump(configs_train, outfile, default_flow_style=False)

def create_yaml_pz_compute(configs):
    yaml_file_config = f'{configs.creation_path}/{configs.process_id}/pz-compute.yaml'
    
    yaml.add_representer(list, represent_list)
    
    configs_pz_compute = {'algorithm': configs.algorithm, 'sbatch_args': ["-N5", "-n140"], 'param_file':f"{configs.algorithm}_estimate.yaml", 'calib_file':f"estimator_{configs.algorithm}.pkl"}
    
    with open(yaml_file_config, 'w') as outfile:
        yaml.dump(configs_pz_compute, outfile, default_flow_style=False)

def create_required_dirs(configs):
    process_dir = f'{configs.creation_path}/{configs.process_id}' 
    try:
        os.makedirs(f'{process_dir}', exist_ok = True)
        os.makedirs(f'{process_dir}/input', exist_ok = True)
    except OSError as error:
        print('Failed to create directories')

def add_input_data(configs):
    if configs.use_all_dp0_dataset:
        if os.path.exists(f'{configs.creation_path}/{configs.process_id}/input'):
            pattern = '*.hdf5'
            target_dir = f'{configs.creation_path}/{configs.process_id}/input/'
            
            for file_path in glob.glob(os.path.join(LSST_DP02, pattern)):
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
        print(f'Please add manually the data in the input dir with the folowing command:\n ln -s <origin_path>/*.hdf5 {configs.process_id}/input/')
        print()

def copy_configs_file(configs):
    file_name_train = f"{configs.algorithm}_train.yaml"
    file_name_estimate = f"{configs.algorithm}_estimate.yaml"
    dst = f"{configs.creation_path}/{configs.process_id}/"
    
    if ENV == "prod":
        if configs.will_train:
            src = f'{APP_PZ_COMPUTE_PATH}/doc/algorithms_config/{file_name_train}'
            shutil.copy(src, dst)
            create_yaml_pz_compute_train(configs)

        src = f'{APP_PZ_COMPUTE_PATH}/doc/algorithms_config/{file_name_estimate}'
        shutil.copy(src, dst)

    elif ENV == "dev":
        if configs.will_train:
            src = f'{SCRATCH}/pz-compute/doc/algorithms_config/{file_name_train}'
            shutil.copy(src, dst)
            create_yaml_pz_compute_train(configs)

        src = f'{SCRATCH}/pz-compute/doc/algorithms_config/{file_name_estimate}'
        shutil.copy(src, dst)
    else:
        print("Env not defined, not creating the configurations yaml")
        return

def copy_run_notebook(configs):
    notebook_file_origin = f"2.pz-compute-template.ipynb"
    notebook_file_dest = f"{configs.process_id}.ipynb"
    dst = f"{configs.creation_path}/{configs.process_id}/{notebook_file_dest}"
    
    if ENV == "prod":
        src = f'{APP_PZ_COMPUTE_PATH}/ondemand/{notebook_file_origin}'
        shutil.copy(src, dst)

    elif ENV == "dev":
        src = f'{SCRATCH}/pz-compute/ondemand/{notebook_file_origin}'
        shutil.copy(src, dst)
    else:
        print("Env not defined, not copying the notebook for the run")
        return

def create_process_dir(algorithm=None, process_id=None, comment=None, will_train=False, creation_path=None, use_all_dp0_dataset=False, env="dev"):
    global ENV
    ENV = env
    
    configs = define_setup_dir(process_id, comment, algorithm, will_train, creation_path, use_all_dp0_dataset)
    create_required_dirs(configs)
    
    add_input_data(configs)
    
    create_yaml_pz_compute(configs)
    yaml_file = create_yaml_process_file(configs)
    
    print_output(configs, yaml_file)
    
    copy_configs_file(configs)
    copy_run_notebook(configs)

def main():
    args = parse_cmd() 
    current_dir = os.getcwd()
    
    create_process_dir(args.algorithm, args.process_id, args.comment, args.will_train, current_dir, args.use_all_dp0_dataset, ENV)    
    
if __name__ == '__main__': main()
