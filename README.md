# pz-compute (under construction)

Pipeline to compute photo-zs using public codes for large volumes of data in the Brazilian's LSST IDAC infrastructure. 

This repository contains software developed and delivered as part of the in-kind contribution program BRA-LIN, from LIneA to the Rubin Observatory's LSST. An overview of this and other contributions is available [here](https://linea-it.github.io/pz-lsst-inkind-doc/).  

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
A trivial script to install RAIL in an environment with the conda package
manager. The script should be used by having an installed conda with a
preconfigured and active environment and then calling it to install all
the dependencies and RAIL.
