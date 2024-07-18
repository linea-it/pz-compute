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
            
def parse_cmd():
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", "--process_id", help = "Integer or short string without blank spaces") 
    parser.add_argument("-c", "--comment", help = "Comment with process description (enclosed in quotes)") 
    parser.add_argument("-a", "--algorithm", help = "specify the algorithm to run") 
    
    args = parser.parse_args()
    args.user = getpass.getuser()
    if args.algorithm == None:
        args.algorithm = 'to-be-defined'
        
    return args

def check_bashcrc():
    print("OPENING BACH")
    bashrc_path = os.path.expanduser('~/.bashrc')
    print("OPENING BACH", bashrc_path)

    code_block = [
        "if [[ -d ~app.photoz ]]\n",
        "then\n",
        "    source ~app.photoz/conf-pz-compute-user.sh\n",
        "fi\n"
    ]
    

    add = False
    
    with open(bashrc_path, 'r') as file:
        print("OPENING BACH", "   ABRIU")
        lines = file.readlines()
        print("OPENING BACH", lines)
        block_present = any(code_block[0] in line for line in lines)
        for i in range(len(lines) - len(code_block) + 1):
            if lines[i:i+len(code_block)] == code_block:
                block_present = True
                break

    if add is True:
        with open(bashrc_path, 'a') as file:
            file.write(new_line)
        print(f"Already has the block code in {bashrc_path}")
    else:
        print(f"It doesn't has the block code in {bashrc_path}")
    
def main():
    #check_bashcrc()
    
    args = parse_cmd()
    
    create_test_dir(args)
    create_required_dirs(args)
    
    create_yaml_pz_compute(args)
    yaml_file = create_yaml_process_file(args)
    
    print_output(args, yaml_file)
    
    #rail_production_path = '/lustre/t0/scratch/users/app.photoz/pz-compute/performance'
    #os.symlink(f'{rail_production_path}/slurm/slurm-analyze-host-performance.py', f'./{args.process_id}/slurm-analyze-host-performance.py')

if __name__ == '__main__': main()