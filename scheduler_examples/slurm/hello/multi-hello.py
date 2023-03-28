#!/usr/bin/env python3

from datetime import datetime
from os import environ
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

	hello = './hello.sh'

	with open('log/hello-%d.out' % my_id, 'wb') as out, \
             open('log/hello-%d.err' % my_id, 'wb') as err:

            for i in range(begin, end):
                now('Starting hello id=%d' % i)
                run([hello], stdout=out, stderr=err)
                now('Finished hello id=%d' % i)
	now('multi-hello end')

if __name__ == '__main__': main()
