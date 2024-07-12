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

(steps 1 and 2 are identical to _production mode_)

1. Add the following block to your `~/.bashrc` file:
    
    ```shell
    if [[ -d ~app.photoz ]]
    then
        source ~app.photoz/conf-pz-compute-user.sh
    fi
    ```

2. Logout and login again to **loginapl01**. 

3. In your scracth area, clone the `pz-compute` repository and checkout to your development branch: 

    ```shell
    $SCRATCH
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

4. Still in your scracth area, create a directory (e.g., "bin") to host a symbolic link to the pipeline executable file and name it as `pz-compute-dev`: 
    
    ```shell
    $SCRATCH
    mkdir bin
    cd bin
    ln -s $SCRATCH/pz-compute/scheduler_scripts/slurm/pz-compute ./pz-compute-dev 
    ```

5. Add the directory with the link to executable file to your environment variable `$PATH` by adding the line below to your `~/.bashrc` file:
    
    ```shell
    export PATH=$PATH:$SCRATCH/bin
    ```

6. Logout and login again to **loginapl01**, or execute: 
    
    ```shell
    source ~/.bashrc
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
