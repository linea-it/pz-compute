from os import environ

LEPHAREDIR = '/lustre/t1/cl/lsst/pz_project/lephare-data'
LEPHAREWORK = 'lephare-work/train'

def get_lephare_dirs():
    lepharedir = environ.get('LEPHAREDIR', LEPHAREDIR)
    lepharework = environ.get('LEPHAREWORK')
    cachedir = environ.get('XDG_CACHE_HOME')

    if not lepharework and not cachedir:
        lepharework = LEPHAREWORK

    return lepharedir, lepharework
