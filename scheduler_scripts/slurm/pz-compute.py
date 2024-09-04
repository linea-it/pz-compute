#!/usr/bin/env python3
from dataclasses import dataclass, replace
from os import execv
from os.path import expandvars
from pathlib import Path
from shlex import split
from shutil import which
from sys import argv, executable
from typing import Union

from yaml import safe_load

SBATCH_ARGS = {
        'tpz': '-N 26 -n 1316 --mem-per-cpu=3500M',
        'lephare': '-N 26 -n 1016 -c2',
        None: '-N 26 -n 2032',
}

TIME_LIMITS = {
        'gpz': 4*3600,
        'fzboost': 16*3600,
        None: None,
}

@dataclass
class Configuration:
    inputdir: str = 'input'
    outputdir: str = 'output'
    algorithm: str = 'fzboost'
    sbatch: str = 'sbatch'
    sbatch_args: Union[list[str], str] = None
    rail_slurm_batch: str = 'pz-compute.batch'
    rail_slurm_py: str = 'pz-compute.run'
    param_file: str = None
    calib_file: str = None
    time_limit: int = None

def parse_cmdline():
    try:
        conffile = argv[1]
    except IndexError:
        conffile = 'pz-compute.yaml'

    return conffile

def to_path(text):
    return Path(expandvars(text)).expanduser()

def load_configuration(conffile):
    config = Configuration()

    try:
        with open(conffile) as f:
            tmp = safe_load(f)
    except FileNotFoundError:
        tmp = {}

    config = replace(config, **tmp)

    if not 'sbatch_args' in tmp:
        config.sbatch_args = SBATCH_ARGS.get(config.algorithm, SBATCH_ARGS[None])

    if not 'time_limit' in tmp:
        config.time_limit = TIME_LIMITS.get(config.algorithm, TIME_LIMITS[None])

    config.inputdir = to_path(config.inputdir)
    config.outputdir = to_path(config.outputdir)

    if config.param_file:
        config.param_file = to_path(config.param_file)

    if config.calib_file:
        config.calib_file = to_path(config.calib_file)

    if isinstance(config.sbatch_args, str):
        config.sbatch_args = split(config.sbatch_args)

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

def seconds_to_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return '%d:%02d:%02d' % (hours, minutes, seconds)

def run(config):
    cmd = [config.sbatch]

    if config.sbatch_args:
        cmd += config.sbatch_args

    if config.time_limit is not None:
        cmd += ['--time=' + seconds_to_time(config.time_limit)]

    cmd += [config.rail_slurm_batch, config.inputdir, config.outputdir, '-a',
            config.algorithm]

    if config.param_file:
        cmd += ['-p', config.param_file]

    if config.calib_file:
        cmd += ['-c', config.calib_file]

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
