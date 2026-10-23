#!/usr/bin/env bash
#SBATCH --job-name=dp2-train
#SBATCH --partition=cpu_photoz
#SBATCH --account=hpc-photoz
#SBATCH --exclude=apl[26-28]

set -euo pipefail

source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh

: "${PZ_ALGORITHM:?missing PZ_ALGORITHM}"
: "${PZ_RAIL_ALGORITHM:?missing PZ_RAIL_ALGORITHM}"
: "${PZ_TRAINING_DATA:?missing PZ_TRAINING_DATA}"
: "${PZ_TRAIN_CONFIG:?missing PZ_TRAIN_CONFIG}"
: "${PZ_RAW_MODEL:?missing PZ_RAW_MODEL}"
: "${PZ_MODEL:?missing PZ_MODEL}"
: "${PZ_DP2_DOC_DIR:?missing PZ_DP2_DOC_DIR}"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

"$PZ_COMPUTE_DIR/rail_scripts/rail-train" \
  "$PZ_TRAINING_DATA" \
  "$PZ_RAW_MODEL" \
  --algorithm="$PZ_RAIL_ALGORITHM" \
  --bins=601 \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file="$PZ_TRAIN_CONFIG"

"$PZ_PY" "$PZ_DP2_DOC_DIR/scripts/wrap-model.py" \
  "$PZ_ALGORITHM" "$PZ_RAW_MODEL" "$PZ_MODEL"
