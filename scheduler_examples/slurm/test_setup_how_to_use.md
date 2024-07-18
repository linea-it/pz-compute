   # How to use test_setup.py

Under construction but it can be used :)

For this first implementation, it works in pz-compute production env.

Feel free to copy, move and put the test-setup.py in your lustre dir where you are goint to execute pz-compute. 
Then you can run the following command to execute:

> `python test-setup.py`

Or do it specifying the -a|--algorithm, -c|--comment and -p|process_id being your diretory

>`python test-setup.py -a=fzboost -c=\"A GOOD PZ-COMPUTE TEST\" -p=my_first_pz_diretory`

After that you can put the files to be used in the input

then it will be necessary to copy or create a symbolic link for the file `slurm-analyze-host-performance.py` with the folowing command. This will be contaplated in the setup-script in the future. 

> `ln -s ~/software/Setups/slurm-analyze-host-performance.py`

Then you can execute the pz-compute to your run

and finally run the command

>`python slurm-analyze-host-performance.py`
