#!/usr/bin/env python3

from contextlib import contextmanager
from datetime import datetime
from os import environ, makedirs
from os.path import dirname
from shutil import which
from subprocess import run
from sys import argv, stderr
from time import sleep

RAIL_ESTIMATE = 'rail-estimate'

@contextmanager
def now(msg):
    print ('%s: Starting: %s' % (datetime.now(), msg), file=stderr, flush=True)
    yield
    print ('%s: Finished: %s' % (datetime.now(), msg), file=stderr, flush=True)

def pairwise(iterable):
    a = iter(iterable)
    return zip(a, a)

def main():
    with now('rail-condor: slot=%s' % environ.get('_CONDOR_SLOT')):
        with now('sleep for 30 seconds (condor warm-up)'):
            sleep(30)

        procid = int(argv[1])
        paths = argv[2:]

        assert(len(paths) % 2 == 0)

        rail_estimate = which(RAIL_ESTIMATE)
        if not rail_estimate:
            raise RuntimeError('Program %s not found.' % RAIL_ESTIMATE)

        for input, output in pairwise(paths):
            with now('create output directory id=%d' % procid):
                makedirs(dirname(output), exist_ok=True)

            with now('run %s %s %s id=%d' % (RAIL_ESTIMATE, input, output, procid)):
                run([rail_estimate, '--bins=301', input, output], check=True)

if __name__ == '__main__': main()
