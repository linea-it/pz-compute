{
 "cells": [
  {
   "cell_type": "markdown",
   "id": "ca48092c-e54f-4520-a1db-a496f3497f0d",
   "metadata": {},
   "source": [
    "# How to use test_setup.py\n",
    "\n",
    "Under construction but it can be used :)\n",
    "\n",
    "For this first implementation, it works in pz-compute production env.\n",
    "\n",
    "Feel free to copy, move and put the test-setup.py in your lustre dir where you are goint to execute pz-compute. \n",
    "Then you can run the following command to execute:\n",
    "\n",
    "> `python test-setup.py`\n",
    "\n",
    "Or do it specifying the -a|--algorithm, -c|--comment and -p|process_id being your diretory\n",
    "\n",
    ">`python test-setup.py -a=fzboost -c=\"A GOOD PZ-COMPUTE TEST\" -p=my_first_pz_diretory`\n",
    " \n",
    "\n",
    "After that you can put the files to be used in the input\n",
    "\n",
    "then it will be necessary to copy or create a symbolic link for the file `slurm-analyze-host-performance.py` with the folowing command. This will be contaplated in the setup-script in the future. \n",
    "\n",
    "> `ln -s ~/software/Setups/slurm-analyze-host-performance.py`\n",
    " \n",
    "\n",
    "Then you can execute the pz-compute to your run\n",
    "\n",
    "and finally run the command\n",
    "\n",
    ">`python slurm-analyze-host-performance.py`"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3 (ipykernel)",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.10.10"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
