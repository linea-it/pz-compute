First of all, run the following commands to create the necessary folders:
```bash
cd $SCRATCH
mkdir -p random_from_files
cd random_from_files
mkdir output
mkdir logs
```

Then, still in the random_from_files directory, copy the scripts to this directory. If you had made the clone of the github repository, just run:
```bash
cp $SCRATCH/pz-compute/docs/notebooks/{DP02_step_1_random_training_set.py,DP02_step_1_random_training_set.sbatch} .
```

Run the script with:
```bash
sbatch DP02_step_1_random_training_set.sbatch
```

If you want to see info of the running job, use:
```bash
scontrol show job <your-job-number>
```