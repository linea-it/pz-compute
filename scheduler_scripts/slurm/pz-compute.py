#!/usr/bin/env python3
from dataclasses import dataclass, field, replace
from os import execv
from pathlib import Path
from shlex import split
from shutil import which
from sys import argv, executable

from yaml import safe_load

SBATCH_ARGS = '-N 26 -n 2032'

@dataclass
class Configuration:
    inputdir: str = 'input'
    outputdir: str = 'output'
    algorithm: str = 'fzboost'
    sbatch: str = 'sbatch'
    sbatch_args: list[str] = field(default_factory=lambda: split(SBATCH_ARGS))
    rail_slurm_batch: str = 'pz-compute.batch'
    rail_slurm_py: str = 'pz-compute.run'

def parse_cmdline():
    try:
        conffile = argv[1]
    except IndexError:
        conffile = 'pz-compute.yaml'

    return conffile

def to_path(text):
    return Path(text).expanduser()

def load_configuration(conffile):
    config = Configuration()

    try:
        with open(conffile) as f:
            tmp = safe_load(f)
    except FileNotFoundError:
        tmp = None

    if tmp:
        config = replace(config, **tmp)

    config.inputdir = to_path(config.inputdir)
    config.outputdir = to_path(config.outputdir)

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
            config.inputdir, config.outputdir, config.algorithm]
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
