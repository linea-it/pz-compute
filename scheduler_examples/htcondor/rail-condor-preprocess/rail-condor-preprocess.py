#!/usr/bin/env python3

from contextlib import contextmanager
from datetime import datetime
from os import environ, makedirs
from os.path import dirname, join
from socket import gethostname
from shutil import which
from subprocess import run
from sys import argv, stderr
from time import sleep

PREPROCESS = 'rail-preprocess-parquet'

@contextmanager
def now(msg):
    print ('%s: Starting: %s' % (datetime.now(), msg), file=stderr, flush=True)
    yield
    print ('%s: Finished: %s' % (datetime.now(), msg), file=stderr, flush=True)

def main():
    h = gethostname()
    s = environ.get('_CONDOR_SLOT')
    procid = int(argv[1])

    with now('rail-condor-preprocess: host=%s slot=%s id=%d' % (h, s, procid)):
        with now('sleep for 30 seconds (condor warm-up)'):
            sleep(30)

        input_dir = argv[2]
        output_base_dir = argv[3]
        files = argv[4:]

        preprocess = which(PREPROCESS)

        if not preprocess:
            raise RuntimeError('Program %s not found.' % PREPROCESS)

        for file in files:
            output_dir = dirname(join(output_base_dir, file))
            file_path = join(input_dir, file)

            with now('create output directory id=%d' % procid):
                makedirs(output_dir, exist_ok=True)

            f = file_path
            o = output_dir

            with now('run %s %s %s id=%d' % (PREPROCESS, f, o, procid)):
                run([preprocess, '--rows=150000', f, o], check=True)

if __name__ == '__main__': main()
