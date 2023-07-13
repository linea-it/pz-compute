#!/usr/bin/env python3

from contextlib import contextmanager
from datetime import datetime
from os import cpu_count, environ, makedirs, sched_setaffinity
from os.path import dirname
from resource import RLIM_INFINITY, RLIMIT_AS, getrlimit, setrlimit
from shutil import which
from subprocess import run
from sys import argv, stderr
from time import sleep
import yaml
import glob

MAX_VIRTUAL_MEM = 16<<30
MAX_CPUS = 3

RAIL_ESTIMATE = 'rail-estimate'

@contextmanager
def now(msg):
    print ('%s: Starting: %s' % (datetime.now(), msg), file=stderr, flush=True)
    yield
    print ('%s: Finished: %s' % (datetime.now(), msg), file=stderr, flush=True)

def pairwise(iterable):
    a = iter(iterable)
    return zip(a, a)

def limit_memory(size):
    limits = list(getrlimit(RLIMIT_AS))

    if limits[0] == RLIM_INFINITY:
        limits[0] = size
    elif limits[0] < size:
        return

    limits[0] = size

    # Note: RLIMIT_RSS is not supported on Linux, use RLIMIT_AS as best effort.
    setrlimit(RLIMIT_AS, limits)

def limit_cpus(start):
    # Best effort attempt to match Hyperthreading siblings and cache-sharing
    # cores.
    total_cpus = cpu_count()
    neigh1 = start//2*2
    neigh2 = start//2*2 + 1
    hyper1 = (neigh1 + total_cpus//2) % total_cpus
    hyper2 = (neigh2 + total_cpus//2) % total_cpus

    try:
        sched_setaffinity(0, {neigh1, neigh2, hyper1, hyper2})
    except OSError:
        print('Warning: unable to set CPU affinity.', file=stderr, flush=True)

def main():
    start_time = datetime.now()
    slot = environ.get('_CONDOR_SLOT')
    with now('rail-condor: slot=%s' % slot):

        # Condor is not currently configured to limit maximum memory or CPUs, so
        # limit explicitly so that the libraries don't try to spawn a large
        # amount of helper threads and processes.
        limit_memory(MAX_VIRTUAL_MEM)
        limit_cpus(int(slot.lstrip('slot')))
        environ['OMP_NUM_THREADS'] = str(MAX_CPUS)
        environ['ARROW_IO_THREADS'] = str(MAX_CPUS)
        environ['ARROW_DEFAULT_MEMORY_POOL'] = 'system'

        with now('sleep for 30 seconds (condor warm-up)'):
            sleep(30)

        procid = int(argv[1])
        algorithm = argv[2]
        paths = argv[3:]

        assert(len(paths) % 2 == 0)

        rail_estimate = which(RAIL_ESTIMATE)
        if not rail_estimate:
            raise RuntimeError('Program %s not found.' % RAIL_ESTIMATE)

        for input, output in pairwise(paths):
            with now('create output directory id=%d' % procid):
                makedirs(dirname(output), exist_ok=True)

            with now('run %s %s %s id=%d' % (RAIL_ESTIMATE, input, output, procid)):
                run([rail_estimate, '--bins=301', '--algorithm=%s' % algorithm,
                    input, output], check=True)
              
    end_time = datetime.now()
    duration = end_time - start_time
    if len(glob.glob('process_info.yaml')) > 0:    
        # Open the file in append & read mode ('a+')
        with open('process_info.yaml', "a+") as file_object:
            file_object.write(f'start_time:{start_time}')
            file_object.write("\n")
            file_object.write(f'end_time:{end_time}')
            file_object.write("\n")
            file_object.write(f'duration:{duration}')
            file_object.write("\n")
            # TBD: 
            # get configs from submission file 
            # get individual machines times from performance script that reads log file
            # print stats on screen
            # write stats in process info file
            # send notification email 
            
            
if __name__ == '__main__': main()
