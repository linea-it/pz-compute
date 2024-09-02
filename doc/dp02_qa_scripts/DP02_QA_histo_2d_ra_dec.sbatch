#!/bin/bash
#SBATCH --job-name=histo_2d_ra_dec    # Nome do job
#SBATCH --output=/lustre/t0/scratch/users/%u/dp02_qa/logs/histo_2d_ra_dec_output_%j.log    # Nome do arquivo de saída (%j será substituído pelo ID do job)
#SBATCH --error=/lustre/t0/scratch/users/%u/dp02_qa/logs/histo_2d_ra_dec_error_%j.log      # Nome do arquivo de erro (%j será substituído pelo ID do job)
#SBATCH --partition=cpu_small      # Substitua pelo nome da sua fila
#SBATCH --time=01:00:00            # Tempo máximo de execução
#SBATCH --nodes=1                  # Número de nós (apenas 1 para iniciar o script Python)

# Inicializar o Conda e ativar o ambiente dp02_qa
export PATH="/lustre/t0/scratch/users/$USER/miniconda3/bin:$PATH"
eval "$(conda shell.bash hook)"
conda activate dp02_qa

# Verificar se o ambiente foi ativado corretamente
echo "Usando Python de: $(which python)"
echo "Versão do Python: $(python --version)"
echo "Pacotes instalados:"
pip list

# Executar o script Python
python /lustre/t0/scratch/users/$USER/dp02_qa/DP02_QA_histo_2d_ra_dec.py
