#!/bin/bash
#SBATCH --job-name=GAIA-DR3-vs-DES-DR2     # Nome do job
#SBATCH --output=/lustre/t0/scratch/users/%u/report_hats/GAIA-DR3-vs-DES-DR2/margin_cache_output_%j.log    # Nome do arquivo de saída (%j será substituído pelo ID do job)
#SBATCH --error=/lustre/t0/scratch/users/%u/report_hats/GAIA-DR3-vs-DES-DR2/margin_cache_error_%j.log      # Nome do arquivo de erro (%j será substituído pelo ID do job)
#SBATCH --partition=cpu_small              # Substitua pelo nome da sua fila
#SBATCH --account="hpc-bpglsst"
#SBATCH --time=08:00:00                    # Tempo máximo de execução
#SBATCH --nodes=1                          # Requisitar 1 nó
#SBATCH --cpus-per-task=50                # Número total de CPUs requisitadas
#SBATCH --mem=100G                         # Memória total do nó (256 GB)

# Inicializar o Conda e ativar o ambiente dp02_qa
export PATH="/lustre/t0/scratch/users/$USER/miniconda3/bin:$PATH"
eval "$(conda shell.bash hook)"
conda activate /lustre/t0/scratch/users/luigi.silva/hats_env_081124

# Verificar se o ambiente foi ativado corretamente
echo "Usando Python de: $(which python)"
echo "Versão do Python: $(python --version)"
echo "Pacotes instalados:"
pip list

# Executar o script Python
python /lustre/t0/scratch/users/$USER/report_hats/GAIA-DR3-vs-DES-DR2/GAIA-DR3-vs-DES-DR2-crossmatching.py
