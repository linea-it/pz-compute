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
import subprocess
from datetime import datetime


def main():  

    # Initialize parser
    parser = argparse.ArgumentParser()
    # Adding optional argument
    parser.add_argument("-p", "--process_id", 
                        help = "Integer or short string without blank spaces") 
    parser.add_argument("-c", "--comment", 
                        help = "Comment with process description (enclosed in quotes)") 
                                

    # Read arguments from command line
    args = parser.parse_args()
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


    args.user = getpass.getuser()
    
    print('---------------------------------------')
    print(f'Process ID: {args.process_id}')
    if not args.comment:
        args.comment = ' --- ' 
    print(f'User: {args.user}')
    print(f'Description: {args.comment}')
    print('---------------------------------------')
    print()
    process_dir = f'./{args.process_id}' 
    try:
        os.makedirs(f'{process_dir}', exist_ok = True)
        os.makedirs(f'{process_dir}/input', exist_ok = True)
        os.makedirs(f'{process_dir}/output', exist_ok = True)
    except OSError as error:
        print('Failed to create directories')

    repo_dir = os.environ['REPO_DIR']
    slurm_batch_path = f"{repo_dir}/scheduler_examples/slurm/rail-slurm/rail-slurm.batch"
    slurm_py_path = f"{repo_dir}/scheduler_examples/slurm/rail-slurm/rail-slurm.py"
    slurm_shield_path = f"{repo_dir}/utils/slurm/slurm-shield.c"
    
    if not os.path.isfile(slurm_shield_path) or not os.path.isfile(slurm_py_path) or not os.path.isfile(slurm_shield_path):
        print(f"REPO_DIR NOT FOUND > {repo_dir} error creatind important links")
    
    os.symlink(f'{slurm_batch_path}', f'./{args.process_id}/rail-slurm.batch')
    os.symlink(f'{slurm_py_path}', f'./{args.process_id}/rail-slurm.py')
    
    command = ['cc', '-o', f'{args.process_id}/slurm-shield', slurm_shield_path]
    process = subprocess.run(command, capture_output=True, text=True)
    
    if process.returncode == 0:
        print("Compilação bem-sucedida.")
        print("Saída:", process.stdout)
        
        if os.path.exists(f'{args.process_id}/slurm-shield'):
            print(f"Arquivo slurm-shield criado com sucesso")
        else:
            print(f"Falha ao criar o arquivo slurm-shield")
    else:
        print("Erro na compilação.")
        print("Erro:", process.stderr)
    
    # Write info file  
    yaml_file = f'./{args.process_id}/process_info.yaml'
    
    with open(yaml_file, 'w') as outfile:
        yaml.dump(vars(args), outfile, default_flow_style=False)
    
    #with open(yaml_file, 'w') as file:
    #    file.write(yaml.dump(vars(args)))
    print(f'Process info saved in {yaml_file}')    
    print() 
    print() 
    
    

if __name__ == '__main__': main()