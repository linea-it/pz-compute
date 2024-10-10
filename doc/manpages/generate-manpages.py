#!/usr/bin/env python3
from glob import glob
from os import environ, makedirs, system, umask
from os.path import isdir
from shlex import join
from shutil import which
from subprocess import CalledProcessError, run
from sys import argv, stderr

PATH = environ.get('PATH')

def fatal(msg):
    print(msg, file=stderr, flush=True)
    raise SystemExit(1)

def main():
    A2X = environ.get('A2X', 'a2x')
    CONDA_PREFIX = environ.get('CONDA_PREFIX', '')
    XSLPATH = '%s/share/docbook-xsl/manpages' % CONDA_PREFIX
    XSLTPROCFLAGS = '--xsltproc-opts=--path "%s"' % XSLPATH
    A2XFLAGS = ['-L', '-f', 'manpage']

    if len(argv) < 3:
        fatal('Usage: %s <input_dir> <output_dir>' % argv[0])

    print('Looking for a2x...')
    a2x = which(A2X)

    if a2x:
        print('Ok')
    else:
        fatal('which: no %s in (%s)' % (prog, PATH))

    print('Looking for docbook-xsl...')

    if isdir(XSLPATH):
        A2XFLAGS += [XSLTPROCFLAGS]
        print('Ok.')
    else:
        print('Warning: docbook-xsl doesn\'t seem to be installed.')

    print('Creating output directory...')
    makedirs(argv[2], exist_ok=True)
    print('Ok.')

    # Block executable flag set by a2x
    mask = umask(0)
    mask = mask | 0o111
    print('Calling umask %o...' % mask)
    umask(mask)
    print('Ok')

    print('Creating manpages')
    for src in glob('%s/*.adoc' % argv[1]):
        cmd = [a2x] + A2XFLAGS + ['-D', argv[2], src]
        print(join(cmd))
        try:
            run(cmd, check=True)
        except CalledProcessError as e:
            raise SystemExit(1)

    print('Done.')

if __name__ == '__main__': main()
