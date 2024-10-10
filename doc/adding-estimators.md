## How to add new photometric redshift estimation algorithms to pz-compute

RAIL supports having its functionality expanded with add-ons, including the
addition of new estimation algorithms. At any given moment, the RAIL
installation will be composed of the RAIL core package (`pz-rail-base`) and a
set of other packages with estimators, like `pz-rail-flexzboost` or
`pz-rail-bpz`. To add a new estimator that works with the pz-compute project,
the estimator must first have its own RAIL integration package, provided by some
upstream group of developers. Considering a hypothetical example estimator
called "Estimator 1", its package must be provided, for example:

    $ pip install pz-rail-estimator1

Depending on the rhythm of the code evolution, or in case debugging will be
needed, a development version must be built from source and installed:

    $ # Install package dependencies with conda, pip, etc.
    $ git clone https://hostname.etc/pz-rail-estimator1
    $ pip install ./pz-rail-estimator1
    $ # Alternative command to install symbolic links to the local repository
    $ # pip install -e ./pz-rail-estimator1

The basic integration process to pz-compute is very simple if the new estimator
is well integrated with RAIL, it's just a matter of importing the class derived
from RAIL's `CatEstimator` class into pz-compute's `rail-estimate` program and
loading the class derived from `CatInformer` into `rail-train`. Both programs
have an appropriate function for loading the classes, called
`load_slow_modules()`. For `rail-estimator`, the class should be renamed as
`Estimator` and for `rail-train`, as `Trainer`.

Continuing the hypothetical example, assuming the new estimator was installed as
the module `rail.estimation.algos.estimator1`, with the estimator class called
`Estimator1Estimator` and the informer class called `Estimator1Informer`, the
code to be added is the following:

Add to `rail-estimate`:

```
def load_slow_modules(estimator):
    # (...)
    # There's an if-else sequence in the code
    # The string value 'estimator1' is user-visible
    elif estimator == 'estimator1':
        from rail.estimation.algos.estimator1 import Estimator1Estimator as Estimator
    # (...)
```

Add to `rail-train`:

```
def load_slow_modules(estimator):
    # (...)
    # There's an if-else sequence in the code
    # The string value 'estimator1' is user-visible
    elif estimator == 'estimator1':
        from rail.estimation.algos.estimator1 import Estimator1Informer as Trainer
    # (...)
```

If the new estimator is integrated with RAIL in a seamless way, this is enough
to make it work and the estimator is ready to use. This was the case, for
example, of the trivial Gaussian-fit GPZ algorithm. Additionally, both programs
include in their docstrings and show in their help texts the list of algorithms
currently supported, so they should be expanded as well:

    # From the toplevel docstring
    """
    (...)
    Available algorithms: bpz, fzboost, tpz, gpz, lephare, estimator1"""

To run the programs with the new estimator, run with the string that was used to
name it as the algorithm parameter:

    $ rail-train --algorithm=estimator1 ref1.pq
    $ rail-estimate --algorithm=estimator1 input1.hdf5 output1.hdf5

If the new estimator is not integrated to RAIL in a seamless way, extra
setup code might be needed. Examples would be:

- Configuring environment variables before using the estimator
- Downloading and installing additional files
- Preparation of auxiliary datasets
- Installing dependency libraries and programs

In the case of the LePhare estimator, for example, the `lephare-data` repository
with the auxiliary datasets used by LePhare must be downloaded and the
`LEPHAREDIR` environment variable configured to point to the directory. This
configuration should be made in some place in the pz-compute script chain, or
alternatively, in the user's environment configuration files. Some hints to help
choosing the proper place to a configuration:

- If the configuration is essential to the majority of use cases and does not
  depend on the configuration of the LineA cluster (no hardcoded paths, host
  names, etc.): place it in `rail-estimate`, in the function
  `setup_estimator()`. An example is the calling of
  `create_column_mapping_dict()`, which creates all the parameters that
  configure the names of the columns from the input data files.
- If the configuration is specific to the configuration of the LineA cluster,
  like a directory in the Lustre storage, then add it to the `pz-compute.yaml`
  configuration file, with, as default value, the LineA-specific value. For
  example, a `lepharedir` configuration may be added to `pz-compute.yaml`, with
  default value of `/lustre/t1/cl/lsst/pz_project/lephare-data`, which is then
  used by `pz-compute.py` to set the `LEPHAREDIR` environment variable. If
  necessary, `pz-compute.py` should forward the configuration to `rail-estimate`
  with a command-line parameter (the `param_file` configuration was implemented
  this way and translates to the `-p` parameter in `rail-estimate`).
- If there are large auxiliary datasets, like `lephare-data`, placing it in a
  public read-only location in the cluster storage should be preferred over
  having multiple copies of it. Users will then have a choice of cloning the
  dataset or using the shared copy.
- If some configuration must be generated per execution slot in the cluster, it
  should be implemented in `pz-compute.run`, which is the script that calls
  `rail-estimate` after doing per-slot configuration. Examples would be
  configurations that require a slot ID or task ID value, like creating a
  numbered log file, for example.
- If it's difficult or not worthy to have default configurations specific to an
  estimator, then the users should be instructed to configure them in their
  personal area, the most common example being configuring environment variables
  in their profile shell script (`.bashrc`).

### Test with rail-train
Testing the new estimation algorithm starts with creating a calibration file
with `rail-train`. Testing depends on a reference file that contains well-known
redshift values for a collection of objects in the sky. There are a few
reference files readily available in the LineA cluster. The simplest one comes
with the core RAIL distribution and is called `test_dc2_training_9816.hdf5`.
Since it has an internal data organization different than what's expected by
`rail-train` (like different column names), reshape it with `hdf5-linea` and
then run the training with default parameters:

    $ hdf5-linea test_dc2_training_9816.hdf5 linea_dc2.hdf5
    $ rail-train -a estimator1 linea_dc2.hdf5

This should run without errors because of the simplicity of the reference file.
It will then generate the calibration file `estimator_estimator1.pkl`. If there
are errors, it's very likely that there are bugs in the upstream code. Debugging
and opening bug reports will be necessary.

If the calibration process is very heavy and takes many hours, it might not be
possible to run in LineA's login machine. If necessary, create a
`pz-train.yaml` file with `algorithm: estimator1` and call `pz-train` to execute
the calibration in a cluster node.

Other files are available as reference files. There's a reference file based on
the LSST DP0.2 simulated dataset that has been used for testing all the
estimators and that caught some bugs, called `training_set_dp0.2.pq`. Comparing
to the RAIL's example reference file, this file has ill-defined physical
quantities (like floating-point NaNs and infinities), that may be used to test
exceptional cases in the estimator's code. For example, an infinite recursion
error in TPZ was caught when calibrating with this reference file. It doesn't
need any preprocessing to be used and simply calling `rail-train` with it is
enough:

    $ rail-train -a estimator1 training_set_dp0.2.pq

To test with physically well-defined simulated data from the DP0.2 dataset, some
reference files are also ready. They should be requested to the LineA team based
on the required characteristics.

### Test with rail-estimate
After `rail-train` succeeds creating the calibration file, it should be used for
estimations of individual test files with `rail-estimate`. The `rail-estimate`
script prints the location of the calibration file that it will use before
running the estimation. Any file from the DP0.2 dataset may be used for the
test, but it needs to be preprocessed into skinny tables to have the flux
columns converted to magnitude columns:

    $ rail-preprocess-parquet $DP02/objectTable_(...).parq outdir
    $ rail-estimate -a estimator1 outdir/objectTable_(...)_part1.hdf5 output1.hdf5

This will run an estimation in LineA's login machine. If the estimation takes
too long and uses too much CPU it might be necessary to run it on a cluster node
instead. The `pz-compute` script might be used, but it might be easier to use
`slurm-dispatch.batch` to run the single task:

    $ sbatch -N1 -n1 --ntasks-per-node=1 slurm-dispatch.batch 1 \
            rail-estimate -a estimator1 input1.hdf5 output1.hdf5

The estimation should execute successfully, but if it does not, there might be a
bug coming from the upstream code. Debugging and a bug report might be
necessary. For estimators that are either not tightly integrated with RAIL, or
that have spent some time without being updated, common errors that are expected
are incompatibilities with newer versions (like missing/invalid function call
parameters) not recognizing column names, requiring unnecessary missing columns
and so on. These should be fixed on the upstream code, if possible, or
workarounds added to the LineA code, if not. An example problem from multiple
estimators is that each one receives the column names in a differently named
parameter (but they all do the same thing). When testing the GPZ estimator, it
did not accept magnitudes with non-finite data (unlike other estimators), so
after reporting it to upstream developers, they added a preprocessing step to
GPZ.

Basic inspection of the output files should be done. The output files generated
by RAIL are hardcoded to the HDF5 file format. The file may be inspected by
loading it with some Python code, but it's easier to use the `h5dump` tool, from
the HDF5 package:

    $ h5dump -H output1.hdf5    # Show only the headers
    $ h5dump output1.hdf5       # Dump all data

At a minimum, one dataset representing the resulting probability density
functions for the estimated redshift values should be present. For algorithms
that generate a PDF shaped as an interpolated grid, there will be one array per
input object, by default with 301 points each.

### Monitoring the execution with Grafana
The LineA lab has real-time monitoring for CPU, memory and storage usage, which
is useful for checking if long executions are behaving as expected. Tests with
single-threaded estimators running in an empty node will result in a small
increase of the CPU plot (less than 2% in the case of the LineA cluster), while
multi-threaded estimators will use up to (and ideally) 100%. Memory usage might
vary a lot and might reveal problems with the design of the algorithms related
to unconstrained memory usage and memory leaks. The storage time-series plot
might show a few spikes during usage, tied to the reading and writing during the
estimation. Too long periods without I/O, or too much I/O might indicate
problems.

### Testing with pz-compute
After small estimations of individual files, estimation should be tested with a
large dataset as input, running on LineA's cluster. A test with the DP0.2
dataset, composed of around 278 million objects, should be done with the dataset
preprocessed into skinny tables. Ready-to-use skinny tables are available at:
`/lustre/t1/cl/lsst/dp02/secondary/catalogs/skinny/hdf5`. To recreate skinny
tables for the whole DP0.2 dataset, call `rail-preprocess-parquet`, looping over
all files, or run it on the cluster with `rail-slurm-preprocess.batch`:

    $ # Runs on the local machine
    $ # for i in $DP02; do rail-preprocess-parquet "$i" skinnydir; done
    $ # Runs on the LineA cluster
    $ sbatch -N10 -n100 rail-slurm-preprocess.batch $DP02 skinnydir $DP02/*

Execution with pz-compute requires a YAML configuration file, for example:

    inputdir: skinnydir
    algorithm: estimator1
    # Reduce the number of allocated machines to 20 if the cluster is busy
    # sbatch_args: -N 20 -n 1552

Run `pz-compute` passing the configuration file as a parameter:

    $ pz-compute estimator1-dp02-sample-test.yaml

This should result in the whole cluster being filled with parallel executions of
`rail-estimate`, one per file, until all files are successfully processed.
Multiple log files will be created, one main log file being the one created by
Slurm, with the template name `slurm-{jobid}.out`. It will have top-level
information about the execution and any existing problems will appear in this
file. Inside the `log/00000` directory there will be two log files (standard
output and standard error) for each `rail-estimate` task, which must be checked
for any warnings or errors. To efficiently inspect the large amount of files,
`grep` and `sort` may be used with summarization parameters:

    $ # List log files containing the words error, warn, traceback, oom, memory
    $ grep -ilE 'error|warn|traceback|oom|memory' *
    $ # Show all lines of the standard error files without repetition
    $ sort -u *.err

Problems to look for are out-of-memory situations and some of the files failing
to be estimated. The problems may or may not be caused by upstream bugs. If the
algorithm uses a large amount of memory (more than the usual 2.140 MiB reserved
per parallel execution slot), the Slurm execution parameters should be modified
to request less execution slots per node (`sbatch_args` in the YAML file):

    # Allocate more hardware threads per execution slots (multi-threaded algorithms)
    sbatch_args: -N 26 -n 508 -c 4
    # Allocate more memory per execution slot (single-threaded algorithms)
    # sbatch_args: -N 26 -n 1316 --mem-per-cpu=3500M

The total number of parallel slots is set with `sbatch` `-n` parameter. With
fewer parallel slots, fewer parallel instances of `rail-estimate` will be
running and eventually there will be enough memory for the execution to
complete. If instead memory usage keeps increasing during the whole execution,
then a memory allocation leak might be happening.

### Scalability and performance tests
After estimations of the whole DP0.2 datasets are successfully working, larger
tests should be done to measure performance and detect bugs related to
scalability. Problems that might be caught here are more rare, like sudden
memory usage spikes, non-deterministic crashes and abnormal output file sizes.
If there's no dataset larger than DP0.2 available, estimations with multiple
copies of the DP0.2 skinny tables may be used instead. Estimations with at least
10 billion input objects are recommended (36 copies of DP0.2). When creating a
large amount of copies of the DP0.2 dataset in LineA's Lustre storage, it will
be much faster if it's done in parallel. An example that runs on the cluster
with `slurm-dispatch.batch`:

    # Run with 50 parallel slots, do 144 copies of DP0.2 (40 billion objects)
    $ sbatch -N 10 -n 50 slurm-dispatch.batch 144 cp -r skinnydir dp02/{task_id}

When using multiple copies of a dataset for benchmarking, symbolic or hard links
must not be used and the storage should not have deduplication support enabled
(LineA's storage doesn't have it enabled). Also note that estimating 40 billion
objects results in a total of 90 TiB of generated files with 301 point PDFs.

### Data validation and scientific usage
After running large tests with the new estimator, the integration of the
estimator with pz-compute is complete from the standpoint of the computational
pipeline. The next step is to validate the quality of the resulting data, a task
that should be done by the LineA team members working with the algorithm and/or
with validation. More tests may be done with non-default parameters that are
expected to match the scientific usage.
