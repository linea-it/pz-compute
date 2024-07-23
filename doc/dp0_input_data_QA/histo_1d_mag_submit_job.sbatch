#!/bin/bash
#SBATCH --job-name=histo_1d_mag     # Nome do job
#SBATCH --output=/lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/logs/histo_1d_mag_output_%j.log    # Nome do arquivo de saída (%j será substituído pelo ID do job)
#SBATCH --error=/lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/logs/histo_1d_mag_error_%j.log           # Nome do arquivo de erro (%j será substituído pelo ID do job)
#SBATCH --partition=cpu_small  # Substitua pelo nome da sua fila
#SBATCH --nodes=4              # Número de nós
#SBATCH --ntasks-per-node=28   # Número de tarefas por nó (equivalente ao número de processos Dask)
#SBATCH --cpus-per-task=2      # Número de threads por tarefa (2 threads por núcleo físico)
#SBATCH --mem=128GB            # Memória por nó
#SBATCH --time=01:00:00        # Tempo máximo de execução
#SBATCH --propagate

# Inicializar o Conda e ativar o ambiente pz_compute
export PATH="/lustre/t0/scratch/users/luigi.silva/miniconda3/bin:$PATH"
eval "$(conda shell.bash hook)"
conda activate pz_compute

# Verificar se o ambiente foi ativado corretamente
echo "Usando Python de: $(which python)"
echo "Versão do Python: $(python --version)"
echo "Pacotes instalados:"
pip list

# Executar o script Python
python /lustre/t0/scratch/users/<your-user>/lsst/combined-graphs-QA-notebook/histo_1d_mag_compute.py
