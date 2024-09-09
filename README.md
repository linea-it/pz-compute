# pz-compute 

Pipeline to compute photo-zs using public codes for large volumes of data in the Brazilian LSST IDAC infrastructure. 

This repository contains software developed and delivered as part of the in-kind contribution program BRA-LIN, from LIneA to the Rubin Observatory's LSST. An overview of this and other contributions is available [here](https://linea-it.github.io/pz-lsst-inkind-doc/).  

### Acknowledgement
`pz-compute` has strong dependency on third-party software, especially Python modules from the DESC's open-source project RAIL. Please find the source code and documentation on [RAIL's GitHub repository](https://github.com/LSSTDESC/rail) and on [Read The Docs](https://lsstdescrail.readthedocs.io/) page. The `pz-compute` pipeline consists of a software layer to connect RAIL's user interface to the Brazilian IDAC's HPC infrastructure (HPE Apollo Cluster and Lustre file system) and extract the maximum performance of it to allow the production of photo-z tables in large scale for LSST data releases.      

## Documentation 
Tutorials and examples are available in [doc](./doc) directory to guide new users. 