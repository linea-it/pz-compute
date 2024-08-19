# Pipeline `pz-compute`

The pipeline `pz-compute` is set up to work at LIneA's HPC environment. For those with appropriate permission, the access is done via Open OnDemand platform or from a Terminal on LIneA JupyterHub, via SSH: 

```shell
ssh loginapl01 
``` 


## Production mode 


### Quick setup 

0. Copy the file 

   ```shell
    cp <path-to-y=pz-compute>/pz-compute/scheduler_examples/slurm/prod-config ~/.prod-config"
    ```

1. Add the following block to your `~/.bashrc` file:
    
    ```shell
    alias pz-prod=". ~/.prod-config"
    ```

2. Logout and login again to **loginapl01**. 

3. Type pz-prod, this is going to send you to your t0 scratch area. Once you are here, everytime you login, just need to run this command.

    ```shell
    pz-prod
    ```


### Execution  


1. Add test setup where you are going to run pz-compute:
    ```shell
     ln -s ~app.photoz/pz-compute/scheduler_examples_slurm/test_setup.py
    ```

2. Execute 
     ```shell
    python test_setup.py -a=algorithm -c="comments" -p=dir-process
    ```


3. Run the pipeline inside the created dir

    Default configuration: 

    ```shell
        pz-compute
    ```
    
    For custom configuration, make a copy/edit of the template yaml configuration file to the process directory and update the default values of the configuration parameters. 


## Developer/revisor mode 

### Quick setup 

0. Copy the file 

   ```shell
    cp <path-to-y=pz-compute>/pz-compute/scheduler_examples/slurm/dev-config ~/.dev-config"
    ```

1. Add the following block to your `~/.bashrc` file:
    
    ```shell
    alias pz-dev=". ~/.dev-config"
    ```
    
2. Logout and login again to **loginapl01**. 

3. Type pz-dev, first time that you run it, it will create a pz-compute-dev env, do the installing and setup for pz-compute, then send you to your t0 scratch area. Ps: make sure that your bashrc is configured to use the miniconda path intalled inside the lustre env. Once you are here, everytime you login, just need to run this command.

    ```shell
    pz-dev
    ```

### Execution  

1. Inside the bin dir, there is a alias to test_setup.py. To create a run dir execute: 
     ```shell
    python test_setup.py -a=algorithm -c="comments" -p=dir-process
    ```
    
2. Remember to add a estimate.pkl file for the algorithm that you are going to run, or train the algorithm.


3. Run the pipeline 

    Default configuration: 

    ```shell
    pz-compute-dev
    ```
    
    For custom configuration, make a copy/edit of the template yaml configuration file to the process directory and update the default values of the configuration parameters. 
