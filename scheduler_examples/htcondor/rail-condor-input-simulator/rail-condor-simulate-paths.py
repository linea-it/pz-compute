#!/usr/bin/env python3
from glob import glob
from math import ceil
from os.path import isfile, join, realpath
from os import chdir, getcwd, symlink, makedirs
from sys import argv

from tables_io import read

MAX_TASKS = 22222

CMD_TEXT = '''$(Process) %s'''
OUTPUT_DIR = 'output'
INPUT_DIR = 'input'
LOOP = 3

def get_input_files(input_dir):
    cwd = getcwd()
    chdir(input_dir)
    try:
        return [path for path in glob('**/*', recursive=True) if isfile(path)]
    finally:
        chdir(cwd)

def get_num_tasks(num_files):
    if num_files == 0:
        return 0

    files_per_task = ceil(num_files / MAX_TASKS)
    num_tasks = ceil(num_files / files_per_task)

    return num_tasks

def generate_tasks(files, num_tasks, input_dir, output_dir):
    num_files = len(files)
    for t in range(num_tasks):
        ini = t * num_files // num_tasks
        end = (t+1) * num_files // num_tasks

        args = []
        for path in files[ini:end]:
            args.append(join(input_dir, path))
            args.append(join(output_dir, path))

        print(CMD_TEXT % ' '.join(args))

def parse_cmdline():
    if len(argv) > 1:
        input_dir = argv[1]
    else:
        input_dir = INPUT_DIR

    if len(argv) > 2:
        output_dir = argv[2]
    else:
        output_dir = OUTPUT_DIR

    if len(argv) > 3:
        loop = int(argv[3])
    else:
        loop = LOOP

    return input_dir, output_dir, loop

def main():
    input_dir, output_dir, loop = parse_cmdline()
    makedirs("syminputs", exist_ok=True)

    for dirsim in range(loop):
        sym_input_dir = "syminputs/%s" % str(dirsim)
        symlink(realpath(input_dir), sym_input_dir, target_is_directory=True)
        files = get_input_files(sym_input_dir)
        num_tasks = get_num_tasks(len(files))
        sym_output_dir = "%s/%s" % (output_dir, str(dirsim))
        makedirs(sym_output_dir, exist_ok=True)
        generate_tasks(files, num_tasks, sym_input_dir, sym_output_dir)

if __name__ == '__main__': main()
