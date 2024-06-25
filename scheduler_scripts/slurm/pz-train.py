#!/usr/bin/env python3
from dataclasses import dataclass, field, replace
from os import execv
from pathlib import Path
from shlex import split
from shutil import which
from sys import argv, executable

from yaml import safe_load

SBATCH_ARGS = '-N 1 --ntasks-per-node=1'
PROG = 'pz-train'

@dataclass
class Configuration:
    inputfile: str = 'input.hdf5'
    algorithm: str = 'fzboost'
    outputfile: str = 'estimator_%s.pkl' % algorithm
    sbatch: str = 'sbatch'
    sbatch_args: list[str] = field(default_factory=lambda: split(SBATCH_ARGS))
    prog_batch: str = '%s.batch' % PROG
    param_file: str = None

def parse_cmdline():
    try:
        conffile = argv[1]
    except IndexError:
        conffile = '%s.yaml' % PROG

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

    config.inputfile = to_path(config.inputfile)
    config.outputfile = to_path(config.outputfile)

    if config.param_file:
        config.param_file = to_path(config.param_file)

    print(config)

    return config

def find_prog(basename):
    prog = which(basename)

    if not prog:
        raise RuntimeError('program not found: %s.' % basename)

    return prog

def setup(config):
    config.sbatch = find_prog(config.sbatch)
    find_prog(config.prog_batch)

def run(config):
    cmd = [config.sbatch] + config.sbatch_args + [config.prog_batch,
            config.inputfile, config.outputfile, '-a', config.algorithm]

    if config.param_file:
        cmd += ['-p', config.param_file]

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
