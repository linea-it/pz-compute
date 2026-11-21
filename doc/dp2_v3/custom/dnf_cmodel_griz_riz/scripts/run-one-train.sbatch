#!/usr/bin/env bash
#SBATCH --job-name=dp2c-dnf-train
#SBATCH --partition=cpu_photoz
#SBATCH --account=hpc-photoz

set -euo pipefail

source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh

: "${PZ_CUSTOM_VARIANT:?missing PZ_CUSTOM_VARIANT}"
: "${PZ_CUSTOM_BANDS:?missing PZ_CUSTOM_BANDS}"
: "${PZ_CUSTOM_TRAINING_DATA:?missing PZ_CUSTOM_TRAINING_DATA}"
: "${PZ_CUSTOM_TRAIN_CONFIG:?missing PZ_CUSTOM_TRAIN_CONFIG}"
: "${PZ_CUSTOM_RAW_MODEL:?missing PZ_CUSTOM_RAW_MODEL}"
: "${PZ_CUSTOM_MODEL:?missing PZ_CUSTOM_MODEL}"
: "${PZ_CUSTOM_PROJECT_DIR:?missing PZ_CUSTOM_PROJECT_DIR}"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

"$PZ_COMPUTE_DIR/rail_scripts/rail-train" \
  "$PZ_CUSTOM_TRAINING_DATA" \
  "$PZ_CUSTOM_RAW_MODEL" \
  --algorithm=dnf \
  --bins=601 \
  --bands="$PZ_CUSTOM_BANDS" \
  --column-template='{band}_cModelMag' \
  --column-template-error='{band}_cModelMagErr' \
  --param-file="$PZ_CUSTOM_TRAIN_CONFIG"

"$PZ_PY" "$PZ_CUSTOM_PROJECT_DIR/scripts/wrap-model.py" \
  "$PZ_CUSTOM_VARIANT" "$PZ_CUSTOM_RAW_MODEL" "$PZ_CUSTOM_MODEL"
