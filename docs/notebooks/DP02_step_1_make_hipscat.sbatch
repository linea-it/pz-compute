#!/bin/bash
#SBATCH --job-name=dask_make_hipscat    # Nome do job
#SBATCH --output=/lustre/t1/cl/lsst/dp01/secondary/catalogs/hipscat/logs_truth/submission_job_%j.out    # Nome do arquivo de saída (%j será substituído pelo ID do job)
#SBATCH --error=/lustre/t1/cl/lsst/dp01/secondary/catalogs/hipscat/logs_truth/submission_job_%j.err           # Nome do arquivo de erro (%j será substituído pelo ID do job)
#SBATCH --partition=cpu_small      # Substitua pelo nome da sua fila
#SBATCH --time=05:00:00            # Tempo máximo de execução
#SBATCH --nodes=1                  # Número de nós (apenas 1 para iniciar o script Python)

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
python /lustre/t0/scratch/users/luigi.silva/lsst/dp0.2-xmatching-tests/DP02_step_1_make_hipscat.py