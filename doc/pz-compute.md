# Pipeline `pz-compute`

The pipeline `pz-compute` is set up to work at LIneA's HPC environment. For those with appropriate permission, the access is done via Open OnDemand platform or from a Terminal on LIneA JupyterHub, via SSH: 

```shell
ssh loginapl01 
``` 


## Production mode 


### Quick setup 

0. Copy the file 

   ```shell
    cp <path-to-y=pz-compute>/pz-compute/scheduler_examples/slurm/setup/prod-config ~/.prod-config"
    ```

1. Add the following block to your `~/.bashrc` file:
    
    ```shell
    alias pz-prod=". ~/.prod-config"
    ```

2. Logout and login again to **loginapl01**. 

3. Type pz-prod. This configures the production environment and sends you to
   `$PZ_RUN_ROOT`, which defaults to `$SCRATCH/pz-compute-runs`. Run
   directories created from this point will stay under scratch.

    ```shell
    pz-prod
    ```


### Execution  


1. Create the run directory from `$PZ_RUN_ROOT`:
     ```shell
    python pz_run_setup.py -a=algorithm -c="comments" -p=dir-process
    ```


2. Run the pipeline inside the created dir

    Default configuration: 

    ```shell
        pz-compute
    ```
    
    For custom configuration, make a copy/edit of the template yaml configuration file to the process directory and update the default values of the configuration parameters. 


## Developer/revisor mode 

### Quick setup 

0. Copy the file 

   ```shell
    cp <path-to-y=pz-compute>/pz-compute/scheduler_examples/slurm/setup/dev-config ~/.dev-config
    ```

1. Add the following block to your `~/.bashrc` file:
    
    ```shell
    alias pz-dev=". ~/.dev-config"
    ```
    
2. Logout and login again to **loginapl01**. 

3. Type pz-dev. The first time that you run it, it will create the
   pz-compute-dev env under `$PZ_INSTALL_ROOT`, install and set up pz-compute,
   then send you to `$PZ_RUN_ROOT`, which defaults to
   `$SCRATCH/pz-compute-runs`. Ps: make sure that your bashrc is configured to
   use the miniconda path installed inside the lustre env. Once you are here,
   everytime you login, just need to run this command.

    ```shell
    pz-dev
    ```

### Execution  

1. Create the run directory from `$PZ_RUN_ROOT`:
     ```shell
    python pz_run_setup.py -a=algorithm -c="comments" -p=dir-process
    ```
    
2. Remember to add a estimate.pkl file for the algorithm that you are going to run, or train the algorithm.


3. Run the pipeline inside the created dir

    Default configuration: 

    ```shell
    pz-compute-dev
    ```
    
    For custom configuration, make a copy/edit of the template yaml configuration file to the process directory and update the default values of the configuration parameters. 
