#!/usr/bin/env python3
from glob import glob
from math import ceil
from os.path import isfile, join
from os import chdir, getcwd
from sys import argv

from tables_io import read

MAX_TASKS = 22222

CMD_TEXT = '''$(Process) %s'''
OUTPUT_DIR = 'output'
INPUT_DIR = 'input'

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

    return input_dir, output_dir

def main():
    input_dir, output_dir = parse_cmdline()
    files = get_input_files(input_dir)
    num_tasks = get_num_tasks(len(files))
    generate_tasks(files, num_tasks, input_dir, output_dir)

if __name__ == '__main__': main()
