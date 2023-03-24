#!/usr/bin/env python3

from datetime import datetime
from os import environ
from shutil import move, which
from subprocess import run
from sys import argv, stderr

def now(msg):
	print ('%s: %s' % (datetime.now(), msg), file=stderr, flush=True)

def main():
	now('multi-rail-estimate begin')
	jobs = int(argv[1])
	slots = int(argv[2])
	my_id = int(argv[3])

	assert my_id < slots

	begin = jobs * my_id // slots
	end = jobs * (my_id + 1) // slots

	rail_estimate = which('rail-estimate')

	scratch = environ.get('_CONDOR_SCRATCH_DIR') or '.'

	for i in range(begin, end):
			input = 'input/test-%d.hdf5' % i
			output_tmp = '%s/output-%d.hdf5' % (scratch, i)
			output_final = 'output/output-%d.hdf5' % i
			now('Starting rail-estimate id=%d' % i)
			run([rail_estimate, input, output_tmp])
			now('Finished rail-estimate id=%d' % i)
			now('Starting move file to storage id=%d' % i)
			move(output_tmp, output_final)
			now('Finished move file to storage id=%d' % i)
	now('multi-rail-estimate end')

if __name__ == '__main__': main()
