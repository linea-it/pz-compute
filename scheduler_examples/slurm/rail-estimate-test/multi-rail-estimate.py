#!/usr/bin/env python3

from datetime import datetime
from os import environ
from shutil import move, which
from subprocess import run
from sys import argv, stderr

def now(msg):
	print ('%s: %s' % (datetime.now(), msg), file=stderr, flush=True)

def main():
    now('multi-hello begin')
    jobs = int(argv[1])
    slots = int(environ['SLURM_NTASKS'])
    my_id = int(environ['SLURM_PROCID'])

    assert my_id < slots

    begin = jobs * my_id // slots
    end = jobs * (my_id + 1) // slots

    rail_estimate = which('rail-estimate')

    scratch = environ.get('SLURM_TMPDIR') or '.'

    now('Opening log files for task=%d' % my_id)
    with open('log/multi-rail-estimate-%d.out' % my_id, 'wb') as out, \
         open('log/multi-rail-estimate-%d.err' % my_id, 'wb') as err:
        now('Log files opened for task=%d' % my_id)

        for i in range(begin, end):
            input = 'input/test-%d.hdf5' % i
            output_tmp = '%s/output-%d.hdf5' % (scratch, i)
            output_final = 'output/output-%d.hdf5' % i
            args = ['--group=photometry',
                    '--column-template=mag_{band}_lsst',
                    '--column-template-error=mag_err_{band}_lsst',
                    '--bins=31']
            now('Starting rail-estimate id=%d' % i)
            run([rail_estimate, input, output_tmp] + args, stdout=out,
                stderr=err, check=True)
            now('Finished rail-estimate id=%d' % i)
            now('Starting move file to storage id=%d' % i)
            move(output_tmp, output_final)
            now('Finished move file to storage id=%d' % i)

        now('Closing log files for task=%d' % my_id)

    now('Log files closed for task=%d' % my_id)
    now('multi-hello end')

if __name__ == '__main__': main()
