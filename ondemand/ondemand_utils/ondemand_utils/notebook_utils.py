import subprocess
import pyarrow
import yaml
import time
import sys
import os
import re

WILL_TRAIN = None

def __load_config(config_file):
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def __get_will_train():
    global WILL_TRAIN
    if WILL_TRAIN is None:
        process_info = __load_config('process_info.yaml')
        WILL_TRAIN = process_info['will_train']
        
    return WILL_TRAIN

def load_config(config_file):
    if "train" in config_file:
        if __get_will_train() is False:
            print("A train run was not configured to be executed, skipping this step")
            return None

    return __load_config(config_file)


def __check_slurm_job_status(job_id):
    command = ["sacct", "-j", str(job_id), "--format", "JobID,State"]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        output = result.stdout
        lines = output.splitlines()
        
        return lines[2].split()[-1] if len(lines) > 2 else None
    
    except subprocess.CalledProcessError as e:
        print(f"Error executing sacct: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")
    
    return None

def run_command(command_text):
    current_python = sys.executable
    conda_env_path = os.path.dirname(os.path.dirname(current_python))
    base_conda_path = os.path.dirname(os.path.dirname(conda_env_path))
    
    command = f"source {base_conda_path}/etc/profile.d/conda.sh && conda activate {conda_env_path} && export PATH=$PATH:$SCRATCH/bin && export DUSTMAPS_CONFIG_FNAME=$SCRATCH/pz-compute/rail_scripts/dustmaps_config.json && export PATH=$PATH:$SCRATCH/pz-compute/scheduler_examples/slurm && {command_text}"
    os.system(command)

def get_last_job_id():
    pattern = re.compile(r"slurm-(\d+)")
    all_jobs = []
    
    for file_name in os.listdir(os.getcwd()):
        match = pattern.search(file_name)
        if match:
            all_jobs.append(int(match.group(1)))
    
    if all_jobs:
        return int(max(all_jobs))
    else:
        return None

def monitor_job(job_id, check_interval=10):
    print(f"Monitoring status Job {job_id}\n", flush=True)
    
    dots = "."
    
    while True:
        status = __check_slurm_job_status(job_id)
        
        if status is None:
            print(f"Job id {job_id} not found or does not exist.", flush=True, end='\r')
            break
        
        
        print(f"Job status {job_id}: {status} | {dots}", flush=True, end='\r')
        dots = dots+'.'
        if status == "COMPLETED":
            print(f"\nJob {job_id} completed!", flush=True)
            break
        elif status in ["FAILED", "CANCELLED", "TIMEOUT"]:
            print(f"\nJob {job_id} failed with status: {status}.", flush=True)
            break
        
        time.sleep(check_interval) 
        
def run_pz_train(env="dev"):
    WILL_TRAIN = __get_will_train()
    if WILL_TRAIN is False:
        print("A train run was not configured to be executed, skipping this step")
        return
    
    raise Exception("This is not working yet, use your terminal!")
    if env == "dev":
        run_command("pz-train-dev")
    elif env == "prod":
        run_command("pz-train")
    else:
        raise NotValidEnvironment("env property should be 'dev' or 'prod'")
        
def run_pz_compute(env="dev"):
    raise Exception("This is not working yet, use your terminal!")
    if env == "dev":
        run_command("pz-compute-dev")
    elif env == "prod":
        run_command("pz-compute")
    else:
        raise NotValidEnvironment("env property should be 'dev' or 'prod'")
        
def run_post_process_evaluation():
    run_command('python $SCRATCH/pz-compute/performance/slurm/slurm-analyze-host-performance.py')