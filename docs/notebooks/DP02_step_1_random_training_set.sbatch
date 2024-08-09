#!/bin/bash
#SBATCH --job-name=dask_make_random_train     # Nome do job
#SBATCH --output=./logs/output_%j.log   # Nome do arquivo de saída (%j será substituído pelo ID do job)
#SBATCH --error=./logs/error_%j.log           # Nome do arquivo de erro (%j será substituído pelo ID do job)
#SBATCH --partition=cpu_small  # Substitua pelo nome da sua fila
#SBATCH --nodes=6              # Número de nós
#SBATCH --ntasks-per-node=56   # Número de tarefas por nó (equivalente ao número de processos Dask)
#SBATCH --cpus-per-task=1      # Número de threads por tarefa (1 thread por núcleo)
#SBATCH --mem=128GB            # Memória por nó
#SBATCH --time=01:00:00        # Tempo máximo de execução
#SBATCH --propagate

# Inicializar o Conda e ativar o ambiente pz_compute
export PATH="/lustre/t0/scratch/users/`whoami`/miniconda3/bin:$PATH"
eval "$(conda shell.bash hook)"
conda activate pz_compute

# Verificar se o ambiente foi ativado corretamente
echo "Usando Python de: $(which python)"
echo "Versão do Python: $(python --version)"
echo "Pacotes instalados:"
pip list

# Executar o script Python
python /lustre/t0/scratch/users/`whoami`/github/linea-it/pz-compute/docs/notebooks/DP02_step_1_random_training_set.py

