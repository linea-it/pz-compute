#!/usr/bin/env python3
<<<<<<< HEAD
from dataclasses import dataclass, field, replace
from os import execv
=======
from dataclasses import dataclass, replace
from os import execv
from os.path import expandvars
>>>>>>> main
from pathlib import Path
from shlex import split
from shutil import which
from sys import argv, executable
<<<<<<< HEAD
=======
from typing import Union
>>>>>>> main

from yaml import safe_load

SBATCH_ARGS = '-N 26 -n 2032'
<<<<<<< HEAD
=======
SBATCH_ARGS_TPZ = '-N 26 -n 1316 --mem-per-cpu=3500M'
>>>>>>> main

@dataclass
class Configuration:
    inputdir: str = 'input'
    outputdir: str = 'output'
    algorithm: str = 'fzboost'
    sbatch: str = 'sbatch'
<<<<<<< HEAD
    sbatch_args: list[str] = field(default_factory=lambda: split(SBATCH_ARGS))
    rail_slurm_batch: str = 'pz-compute.batch'
    rail_slurm_py: str = 'pz-compute.run'
    param_file: str = None
=======
    sbatch_args: Union[list[str], str] = SBATCH_ARGS
    rail_slurm_batch: str = 'pz-compute.batch'
    rail_slurm_py: str = 'pz-compute.run'
    param_file: str = None
    calib_file: str = None
>>>>>>> main

def parse_cmdline():
    try:
        conffile = argv[1]
    except IndexError:
        conffile = 'pz-compute.yaml'

    return conffile

def to_path(text):
<<<<<<< HEAD
    return Path(text).expanduser()
=======
    return Path(expandvars(text)).expanduser()
>>>>>>> main

def load_configuration(conffile):
    config = Configuration()

    try:
        with open(conffile) as f:
            tmp = safe_load(f)
    except FileNotFoundError:
        tmp = None

    if tmp:
        config = replace(config, **tmp)

<<<<<<< HEAD
=======
        if tmp.get('algorithm') == 'tpz' and not 'sbatch_args' in tmp:
            config.sbatch_args = SBATCH_ARGS_TPZ

>>>>>>> main
    config.inputdir = to_path(config.inputdir)
    config.outputdir = to_path(config.outputdir)

    if config.param_file:
        config.param_file = to_path(config.param_file)

<<<<<<< HEAD
=======
    if config.calib_file:
        config.calib_file = to_path(config.calib_file)

    if isinstance(config.sbatch_args, str):
        config.sbatch_args = split(config.sbatch_args)

>>>>>>> main
    print(config)

    return config

def find_prog(basename):
    prog = which(basename)

    if not prog:
        raise RuntimeError('program not found: %s.' % basename)

    return prog

def setup(config):
    config.sbatch = find_prog(config.sbatch)
    find_prog(config.rail_slurm_batch)
    find_prog(config.rail_slurm_py)

    if not config.inputdir.is_dir():
        raise RuntimeError('input directory not found: %s' % config.inputdir)

def run(config):
    cmd = [config.sbatch] + config.sbatch_args + [config.rail_slurm_batch,
<<<<<<< HEAD
            config.inputdir, config.outputdir, config.algorithm]

    if config.param_file:
        cmd.append(config.param_file)
=======
            config.inputdir, config.outputdir, '-a', config.algorithm]

    if config.param_file:
        cmd += ['-p', config.param_file]

    if config.calib_file:
        cmd += ['-c', config.calib_file]
>>>>>>> main

    print(' '.join(str(x) for x in cmd))
    execv(config.sbatch, cmd)
    raise RuntimeError('error executing slurm')

def main():
    try:
        conffile = parse_cmdline()
        config = load_configuration(conffile)
        setup(config)
        run(config)
    except RuntimeError as e:
        print('Error: %s' % e)

if __name__ == '__main__': main()
