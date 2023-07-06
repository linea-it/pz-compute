# pz-compute (under construction)

Pipeline to compute photo-zs using public codes for large volumes of data in the Brazilian LSST IDAC infrastructure. 

This repository contains software developed and delivered as part of the in-kind contribution program BRA-LIN, from LIneA to the Rubin Observatory's LSST. An overview of this and other contributions is available [here](https://linea-it.github.io/pz-lsst-inkind-doc/).  

### Acknowledgement
The pipeline was built using modules from the DESC's open-source project RAIL. Please find the original code and documentation on [RAIL's GitHub repository](https://github.com/LSSTDESC/RAIL) and on [Read The Docs](https://lsstdescrail.readthedocs.io/) page.   


## rail-estimate
The `rail-estimate` program is the main standalone script used to
compute the PZ tables. The script accepts an input file containing raw
data and outputs the estimated photo-z values as a probability
distribution. Running `rail-estimate` depends on having a "pre-trained"
configuration file generated by `rail-train` (or some other procedure to
train the algorithms).

## rail-train
The `rail-train` program is a script to prepare a "pre-trained" file for
certain algorithms used to compute PZ tables (for example, the
calculated weights for a neural network). `rail-train` receives an input
file containing both the raw input data and reference output redshift
results, considered to be correct and accurate. The output is a Python
pickle file with the configuration data relevant to the estimator
algorithms. Training is slow, but can be done only once and used later
with `rail-estimate` for any production data that is expected to have
the same behavior as the reference file.

## install-pz-rail
The `install-pz-rail` is a trivial script to install RAIL in an environment with the conda package
manager. The script should be used by having an installed conda with a
preconfigured and active environment and then calling it to install all
the dependencies and RAIL.

## rail-preprocess-parquet
The `rail-preprocess-parquet` script may be used to read input data
in parquet format containing either flux or magnitude data and transform
it to a standard format. It does the following preprocessing steps:

- Limit number of rows per file to a maximum, splitting the file if necessary.
- Generate files only with necessary columns (magnitudes and errors).
- Convert infinite values to NaN.
- Convert flux to magnitude.

Note: dereddening is not implemented yet (TDB).

Preprocessing is done as efficiently as possible and memory usage is limited
even with arbitrarily large files. The resulting output files are a set
of parquet files, which are expected to be much smaller than the
original file and suitable to use with the pz-rail algorithms.

## Scheduler examples
The  [scheduler_examples](/scheduler_examples) directory contains examples
showing how to execute independent parallel tasks with the help of some
scheduler.  Currently, there are examples for 2 schedulers: HTCondor and Slurm.

## Utilities
The [utils](/utils) directory contains simple tools to help using the
cluster, the RAIL libraries and relevant data formats. The following
utilities are available:

- `condor-dispatch`: a trivial script for HTCondor that allows executing
  an arbitrary command in the cluster, possibly on multiple slots.
- `condor-slot-run`: a trivial script for HTCondor to run a single
  command on a specific condor slot.
- `parquet-count-rows`: count the total number of rows in a set of
  parquet files without loading all data in memory.


## Performance analysis
The [performance](/performance) directory contains performance analysis
scripts for the schedulers and cluster. The available scripts are the
following:

- `condor-analyze-host-performance`: parses the HTCondor log file and
  outputs the minimum and maximum execution time of each host in the
  cluster.
- `condor-analyze-host-allocation`: plots a time chart showing allocated
  time and dead time caused by the HTCondor scheduler.
- `rail-sum-execution-time`: calculates the total live time (excluding
  the scheduler dead time) of the rail scripts executed on some cluster.
- `benchmark-write-speed`: a set of scripts for HTCondor to test the
  cluster's I/O write speed by writing random data from each condor
  slot.

## LNCC
The directory [LNCC](/LNCC) contains information and configuration
necessary or useful when connecting to the LNCC supercomputer Santos
Dumont. Currently there are sample configuration files for configuring
the VPN routes required when connecting to the Cisco VPN server using
the [vpnc](https://github.com/streambinder/vpnc) client program. The
manually specified routes can be used to avoid configuring the default
route through the LNCC VPN, which would route all Internet traffic to
it.
