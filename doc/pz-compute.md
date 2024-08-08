# Pipeline `pz-compute`

The pipeline `pz-compute` is set up to work at LIneA's HPC environment. For those with appropriate permission, the access is done via Open OnDemand platform or from a Terminal on LIneA JupyterHub, via SSH: 

```shell
ssh loginapl01 
``` 


## Production mode 


### Quick setup 

1. Add the following block to your `~/.bashrc` file:
    
    ```shell
    if [[ -d ~app.photoz ]]
    then
        source ~app.photoz/conf-pz-compute-user.sh
    fi
    ```

2. Logout and login again to **loginapl01**. 


### Execution  

1. In your scracth area, create a new directory for your process and create a subdirectory `input` inside it:     

    ```shell
    cd $SCRATCH
    mkdir <process_name>
    cd <process_name>
    mkdir input
    ```

2. Fill in your `input` dir with input files, or symbolic links to them. For instance, for the complete LSST DP0.2 dataset, the default input files are the skinny tables available in Lustre T1:

    ```shell
    ln -s /lustre/t1/cl/lsst/dp0.2/secondary/catalogs/skinny/*.hdf5 ./input/
    ```

3. Run the pipeline 

    Default configuration: 

    ```shell
    pz-compute
    ```
    
    For custom configuration, make a copy of the template yaml configuration file to the process directory and update the default values of the configuration parameters. 




## Developer/revisor mode 

### Quick setup 


1. Create a new development environment:  
    
    ```shell
    conda create --name pz_compute
    conda activate pz_compute
    ```

2. In your scracth area, clone the `pz-compute` repository and checkout to your development branch: 

    ```shell
    cd $SCRATCH
    git clone https://github.com/linea-it/pz-compute.git # for HTTPS clone
    ```
    or

    ```shell
    git clone git@github.com:linea-it/pz-compute.git # for SSH clone
    ```
    then

    ```shell
    cd pz-compute
    git checkout <dev-branch-name>
    ```



3. Still in your scracth area, create a directory (e.g., "bin") to host a symbolic link to the pipeline executable file and name it as `pz-compute-dev`: 
    
    ```shell
    cd $SCRATCH
    mkdir bin
    cd bin
    ln -s $SCRATCH/pz-compute/scheduler_scripts/slurm/pz-compute ./pz-compute-dev
    chmod +x pz-compute-dev
    ```

4. Add two environment variables to your `~/.bashrc` file: (i) add the directory with the link to executable file to your environment variable `$PATH`; (ii) add the directory to save the dust maps files to `DUSTMAPS_CONFIG_FNAME` :
    
    ```shell
    export PATH=$PATH:$SCRATCH/bin
    export DUSTMAPS_CONFIG_FNAME=$SCRATCH/pz-compute/rail_scripts/dustmaps_config.json
    ```

5. Logout and login again to **loginapl01**, or execute: 
    
    ```shell
    source ~/.bashrc
    ```

5. Install the pipeline: 

    ```shell
    conda activate pz_compute
    mkdir -p $ALTHOME/data
    cd $SCRATCH/pz-compute/rail_scripts 
    ./install-pz-rail  # for now, it is mandatory to execute this script from inside the rail_scripts dir 
    ```

### Execution  

(steps 1 and 2 are identical to _production mode_)

1. In your scracth area, create a new directory for your process and create a subdirectory `input` inside it:     

    ```shell
    cd $SCRATCH
    mkdir <process_name>
    cd <process_name>
    mkdir input
    ```

2. Fill in your `input` dir with input files, or symbolic links to them. For instance, for the complete LSST DP0.2 dataset, the default input files are the skinny tables available in Lustre T1:

    ```shell
    ln -s /lustre/t1/cl/lsst/dp0.2/secondary/catalogs/skinny/*.hdf5 ./input/
    ```

3. Run the pipeline 

    Default configuration: 

    ```shell
    pz-compute-dev
    ```
    
    For custom configuration, make a copy of the template yaml configuration file to the process directory and update the default values of the configuration parameters. 
