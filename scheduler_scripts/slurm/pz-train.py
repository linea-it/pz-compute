#!/usr/bin/env python3
from dataclasses import dataclass, field, replace
from os import environ, execv
from os.path import expandvars
from pathlib import Path
from shlex import split
from shutil import which
from sys import argv, executable

from yaml import safe_load

from pz_compute import get_lephare_dirs

SBATCH_ARGS = '-N 1 --exclusive --ntasks-per-node=1 --mem=0'
PROG = 'pz-train'
OUTPUT_TEMPLATE = 'estimator_%s.pkl'

@dataclass
class Configuration:
    inputfile: str = 'input.hdf5'
    algorithm: str = 'fzboost'
    outputfile: str = OUTPUT_TEMPLATE % algorithm
    sbatch: str = 'sbatch'
    sbatch_args: list[str] = field(default_factory=lambda: split(SBATCH_ARGS))
    prog_batch: str = '%s.batch' % PROG
    param_file: str = None
    lepharedir: str = None
    lepharework: str = None

def parse_cmdline():
    try:
        conffile = argv[1]
    except IndexError:
        conffile = '%s.yaml' % PROG

    return conffile

def to_path(text):
    return Path(expandvars(text)).expanduser()

def load_configuration(conffile):
    config = Configuration()

    try:
        with open(conffile) as f:
            tmp = safe_load(f)
    except FileNotFoundError:
        tmp = None

    if tmp:
        if 'algorithm' in tmp and not 'outputfile' in tmp:
            tmp['outputfile'] = OUTPUT_TEMPLATE % tmp['algorithm']

        config = replace(config, **tmp)

    if config.algorithm == 'lephare':
        lepharedir, lepharework = get_lephare_dirs()

        if not 'lepharedir' in tmp:
            config.lepharedir = lepharedir

        if not 'lepharework' in tmp:
            config.lepharework = lepharework

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

    if not config.inputfile.is_file():
        raise RuntimeError('input file not found: %s' % config.inputfile)

    if config.lepharedir:
        environ['LEPHAREDIR'] = config.lepharedir

    if config.lepharework:
        environ['LEPHAREWORK'] = config.lepharework

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
