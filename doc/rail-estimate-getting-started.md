Getting started with the rail-estimate script
=============================================
The rail-estimate script is a simple command-line script to execute the
prodedure of estimating the redshift probabilities on input data. This
document describes its basic usage.

Prerequisites
-------------
A working instalation of the python packages pz-rail, pz-rail-flexzboost
and pz-rail-bpz is necessary. If using the miniconda package manager, an
[example instalation script](/rail_scripts/install-pz-rail) is available
in this repository. The main part of the instalation script is
replicated here:

    SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=True pip install sklearn
    CFLAGS="-L $CONDA_PREFIX/lib -I $CONDA_PREFIX/include" pip install fitsio
    pip install flexcode

    pip install pz-rail
    pip install pz-rail-bpz
    pip install pz-rail-flexzboost

Both the "flexzboost" and "bpz" estimation algorithms are supported and
require pre-trained data. Pre-trained data must be stored in files
called `estimator_fzboost.pkl` and `estimator_bpz.pkl`. The program will
accept these files placed in the current directory or placed in the
standard XDG data file paths, which by default are the following:

-  `/usr/local/share/rail_scripts`
- `/usr/share/rail_scripts`
- `~/.local/share/rail_scripts`

The script `rail-train` is available to generate pre-trained data from
test files that contain both raw magnitude input data and the resulting
redshift z value, pre-calculated and assumed to be accurate. If
necessary, an example reference file is available in the pz-rail package
and is usually installed together with the pz-rail library as
`examples/testdata/test_dc2_training_9816.hdf5`. So, a procedure to
generate and install initial pre-trained data is the following:

    mkdir -p ~/.local/share/rail_scripts
    ./rail-train \
        <pz-rail-path>/examples/testdata/test_dc2_training_9816.hdf5 \
        ~/.local/share/rail_scripts/estimator_fzboost.pkl \
        --algorithm=fzboost --group=photometry \
        --column-template=mag_{band}_lsst \
        --column-template-error=mag_err_{band}_lsst
    ./rail-train \
        <pz-rail-path>/examples/testdata/test_dc2_training_9816.hdf5 \
        ~/.local/share/rail_scripts/estimator_bpz.pkl \
        --algorithm=bpz --group=photometry \
        --column-template=mag_{band}_lsst \
        --column-template-error=mag_err_{band}_lsst

In the example, the pz-rail path must be substituted and the parameters
for the input file format (group and templates) must be configured
accordingly.

Running the estimator script from the repository
------------------------------------------------
The script can be called directly from its source repository, like the
following:

    ./rail-estimate input1.hdf5 output1.hdf5

The output file will be generated in HDF5 format. The input file may
be in other formats but current support is not uniform.

The script has many command-line parameters and can be viewed with the
following command:

    ./rail-estimate --help

There are some important parameters that might be required to correctly
read the input files:

- `--group`: only useful for HDF5 files, names the section where the
  input data is located.
- `--column-template`: describes the names of the columns containing
  magnitude data.
- `--column-template-error`: describes the names of the columns
  containing magnitude error data.

A simple way to inspect the input data to see the column and group names
is to use the `h5dump` tool (HDF5 only):

    $ h5dump -H <pz-rail-path>/examples/testdata/test_dc2_validation_9816.hdf5
    (...)
       GROUP "photometry" {
          DATASET "id" {
             DATATYPE  H5T_STD_I64LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
          DATASET "mag_err_g_lsst" {
             DATATYPE  H5T_IEEE_F32LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
          DATASET "mag_err_i_lsst" {
             DATATYPE  H5T_IEEE_F32LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
          DATASET "mag_err_r_lsst" {
             DATATYPE  H5T_IEEE_F32LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
          DATASET "mag_err_u_lsst" {
             DATATYPE  H5T_IEEE_F32LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
          DATASET "mag_err_y_lsst" {
             DATATYPE  H5T_IEEE_F32LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
          DATASET "mag_err_z_lsst" {
             DATATYPE  H5T_IEEE_F32LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
          DATASET "mag_g_lsst" {
             DATATYPE  H5T_IEEE_F32LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
          DATASET "mag_i_lsst" {
             DATATYPE  H5T_IEEE_F32LE
             DATASPACE  SIMPLE { ( 20449 ) / ( 20449 ) }
          }
    (...)

So, it's shown that the tables are inside the "`photometry`" group and
the column names are of the form "`mag_{band}_lsst`" and
"`mag_err_{band}_lsst`". The resulting command line to estimate input
files with this format is the following:

    ./rail-estimate input1.hdf5 output1.hdf5 --group=photometry \
                    --column-template=mag_{band}_lsst \
                    --column-template-error=mag_err_{band}_lsst

The following parameters are important for the output file:

- `--algorithm`: selects which estimation algorithm to use.
- `--bins`: chooses the number of points for the resulting redshift
  probability density p(z) function.

The list of available algorithms is shown in the help message. One
example of execution setting the algorithm to bpz and the number of bins
to 31 is the following:

    ./rail-estimate input1.hdf5 output.hdf5 --algorithm=bpz --bins=31

Installing the scripts
----------------------
Currently, installation, if desired, should be done manually. A simple
way is to keep the source code repository directory and just add a
symbolic link to the scripts:

    $ mkdir -p ~/.local/bin
    $ ln -s <rail-scripts-path>/rail-estimate ~/.local/bin
    $ ln -s <rail-scripts-path>/rail-train ~/.local/bin

The target directory should be placed in your `PATH` environment variable.

The scripts may also be installed (copied) to a system-wide location,
like /usr/local/bin. In this case, the script's package subdirectory
should be copied to Python's site-package directory.

    # cp rail-estimate /usr/local/bin
    # cp rail-train /usr/local/bin
    # cp -a rail_scripts /usr/local/lib/<python-path>/site-packages

