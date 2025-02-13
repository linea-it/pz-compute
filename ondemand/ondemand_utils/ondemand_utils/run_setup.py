#!/usr/bin/env python3

'''
Uses pz_run_setup.py to create processes diretories.
'''

import os
import sys
import shutil 
import argparse
import glob
import yaml
import getpass
from datetime import datetime

import importlib.util
import sys

path = "../scheduler_examples/slurm/setup/pz_run_setup.py"

spec = importlib.util.spec_from_file_location("file", path)
pz_run_setup = importlib.util.module_from_spec(spec)
sys.modules["file"] = pz_run_setup
spec.loader.exec_module(pz_run_setup)

def create_run_dir(algorithm=None, process_id=None, comment=None, will_train=False, creation_path=None, use_all_dp0_dataset=False, env="dev"):
    
    pz_run_setup.create_process_dir(algorithm, process_id, comment, will_train, creation_path, use_all_dp0_dataset, env)
    