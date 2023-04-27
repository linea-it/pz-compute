#!/usr/bin/env python3
from glob import glob
from heapq import heappush, heappop
from os.path import dirname, getsize, isfile, join, relpath
from sys import argv

CMD_TEXT = '$(Process) %s %s %s'

def get_output_file_dir(input_dir, output_dir, file_name):
    return dirname(join(output_dir, relpath(file_name, input_dir)))

def lpt_schedule_by_size(files, num_slots):
    sizes = []
    for file in files:
        sizes.append((getsize(file), file))

    sizes.sort()

    file_map = {i: [] for i in range(num_slots)}
    weights = [(0, i) for i in range(num_slots)]

    while len(sizes) > 0:
        size, file = sizes.pop()
        weight, slot = heappop(weights)
        file_map[slot].append((file, size))
        heappush(weights, (weight + size, slot))

    return file_map

def main():
    slots = int(argv[1])
    input_dir = argv[2]
    output_dir = argv[3]
    patterns = argv[4:]

    files = []

    for pattern in patterns:
        files += [f for f in glob(pattern, recursive=True) if isfile(f)]

    file_map = lpt_schedule_by_size(files, slots)

    for file_list in file_map.values():
        if len(file_list) == 0:
            continue
        total_size = 0
        args = []
        for file, size in file_list:
            args.append(relpath(file, input_dir))

        args = ' '.join(args)

        print(CMD_TEXT % (input_dir, output_dir, args))

if __name__ == '__main__': main()
