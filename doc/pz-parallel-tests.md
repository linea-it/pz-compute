# Photo-z Compute Parallel Tests

The `rail-condor` is a simple command-line script to submit `rail-estimate` processes in parallel on the Apollo cluster. See the tutorial [rail-estimate-getting-started](./rail-estimate-getting-started.md) before this one. 

## Setup environment

``` bash
export CONDAPATH=<path> # full path to conda bin directory 
source $CONDAPATH/activate 
conda activate [rail env]  
export RAILPATH=<path> # full path to RAIL repository clone directory
export RAILSCRIPTS=<path> # <full path to rail_scrips in pz-compute repository
export HTCONDOR=<path> # <full path to scheduler_examples/htcondor in pz-compute repository
export PATH=$PATH:$RAILPATH
export PATH=$PATH:$RAILSCRIPTS
export PATH=$PATH:$HTCONDOR
```

## Prepare process directory

The command `prepare-pz-test` creates and fills in the subdirectories tree necessary to run repeated tests using `rail-condor`. It attributes a Process ID to each test and copies the template of the submission file **rail-condor.sub** to the test directory. 

Usage:
``` bash
   prepare-pz-test [options] [--] <process_id> <comment> 
   prepare-pz-test -h | --help
   prepare-pz-test --version
                           
   Options:
   -h --help   Show help text.
   --version   Show version.
   -p <process id>, --process_id=<process id> Integer or short string without 
                                               blank spaces to identify the 
                                               process. There is no warranty of
                                               uniqueness, only if in the same 
                                               parent directory. If empty, 
                                               attribute test_pz_compute_x where
                                               x is an incremental integer.
   -c <comment>, --comment=<comment> Long string (enclosed in quotes) with the 
                                     process description. (optional) 
``` 

After running the `prepare-pz-test`, populate the **input** directory with input data files (ideally, the outputs of the pre-processing step). Alternatively, add symbolic links to files (or replace the **input** directory with a link to another directory containing the input files, keeping its name as **input**. If not using all files inside the directory, adding the link to files individually is recommended. 


## Run Photo-z Training procedure

Script `rail-train`: 

```bash
Usage:
    rail-train [options] [--] <input> [<output>]
    rail-train -h | --help
    rail-train --version

Options:
    -h --help   Show help text.
    --version   Show version.
    -a <name>, --algorithm=<name>  Select estimation algorithm
                                   [default: fzboost].
    -b <bins>, --bins=<bins>       Set number of bins (columns) in the resulting
                                   tables [default: 301].
    -g <group>, --group=<group>    For HDF5 input, sets the group name (section)
                                   where input data is stored [default: ]
    --column-template=<template>   Set the names of the input columns
                                   [default: mag_{band}]
    --column-template-error=<template-error>  Set the names of the input error
                                              columns [default: magerr_{band}]

```

The output of `rail-train` must follow the pattern **estimator_<algorithm>.pkl**. Available algorithms: bpz, fzboost. 
If it lives in `~/.local/share/rail_scripts/`, the photo-z estimator will find it implicitly.


```bash
mkdir -p ~/.local/share/rail_scripts
rail-train <full path to training input file> ~/.local/share/rail_scripts/estimator_fzboost.pkl
```

For differnent training options, write the **estimator_fzboost.pkl** or **estimator_bpz.pkl** inside the process directory. 

```bash
rail-train <full path to training input file> . 
```

Example using test files from RAIL's examples folder: 
    
```bash
./rail-train  $RAILPATH/examples/testdata/test_dc2_training_9816.hdf5 \
    ~/.local/share/rail_scripts/estimator_fzboost.pkl \
    --algorithm=fzboost --group=photometry \
    --column-template=mag_{band}_lsst \
    --column-template-error=mag_err_{band}_lsst
./rail-train \
    $RAILPATH/examples/testdata/test_dc2_training_9816.hdf5 \
    ~/.local/share/rail_scripts/estimator_bpz.pkl \
    --algorithm=bpz --group=photometry \
    --column-template=mag_{band}_lsst \
    --column-template-error=mag_err_{band}_lsst
```

To avoid using the local machine's memory, dispatch the training script to the cluster: 
```bash
condor_run rail-train [options] [--] <input> [<output>] & 
``` 


## Edit submission file **rail-condor.sub**

The submission file **rail-condor.sub** must be updated before each run. It will serve to set the process configuration parameters and also to feed the provenance file. Therefore, it is **not recommended** to let the template as original and set the parameters via command-line arguments of `rail-condor`. 

Submission file contents:
    
```bash
executable = rail-condor.py
log = rail-condor.log
input_dir1 = $(input_dir:input)
output_dir1 = $(output_dir:output)
output = log/rail-condor-$(Process).out
error = log/rail-condor-$(Process).err
should_transfer_files = IF_NEEDED
when_to_transfer_output = ON_EXIT
getenv = True
rank = -slotid
# Requirements = (Machine == "apl11.ib0.cm.linea.gov.br")
+RequiresWholeMachine = False
queue arguments from ./rail-condor-configure-paths.py $(input_dir1) $(output_dir1) $(algorithm:fzboost) |
```

**WARNING:** Do not replace the value of "Process". It will be generated automatically by the parallelization script (not to be confused with the process ID).  

    
## Run the Photo-z Estimator 

After setting up the inputs and submission file, submit the process to the cluster. From inside the process directory, run:
    
```bash
condor_submit rail-condor.sub 
``` 

## Get results and provenance info from the **process_info.txt** file 

After all the subprocesses are finished, the runtime statistics and relevant metadata will be available in file <process_id>_process_info.txt inside the process directory. From inside the process directory, run:

```bash
cat <process_id>_process_info.txt
``` 
    
    
 
