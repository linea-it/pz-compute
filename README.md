# pz-compute (under construction)

Pipeline to compute photo-zs using public codes for large volumes of data in the Brazilian's LSST IDAC infrastructure. 

This repository contains software developed and delivered as part of the in-kind contribution program BRA-LIN, from LIneA to the Rubin Observatory's LSST. An overview of this and other contributions is available [here](https://linea-it.github.io/pz-lsst-inkind-doc/).  

## rail-estimate
The `rail-estimate` program is the main standalone script used to
compute the PZ tables. The script accepts an input file containing raw
data and outputs the estimated photo-z values as a probability
distribution.
