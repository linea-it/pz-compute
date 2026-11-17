#!/usr/bin/env bash
#SBATCH --job-name=dp2c-dnf-estimate
#SBATCH --partition=cpu_photoz
#SBATCH --account=hpc-photoz
#SBATCH --output=log/slurm-%A_%a.out
#SBATCH --error=log/slurm-%A_%a.err

set -euo pipefail

source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh

for name in PZ_CUSTOM_VARIANT PZ_CUSTOM_BANDS PZ_DP2_INPUT_DATASET \
  PZ_CUSTOM_MODEL PZ_CUSTOM_ESTIMATE_CONFIG PZ_CUSTOM_SFD_CONFIG \
  PZ_CUSTOM_STAGE2_OUTPUT PZ_FILE_LIST PZ_CUSTOM_PROJECT_DIR; do
    test -n "${!name:-}" || { echo "missing $name" >&2; exit 1; }
done

case "$PZ_CUSTOM_VARIANT" in
    griz|riz) ;;
    *) echo "Unsupported variant: $PZ_CUSTOM_VARIANT" >&2; exit 2 ;;
esac

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

input_file=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$PZ_FILE_LIST")
test -n "$input_file" || {
    echo "No input for array index $SLURM_ARRAY_TASK_ID" >&2
    exit 1
}
case "$input_file" in
    "$PZ_DP2_INPUT_DATASET"/*) ;;
    *) echo "Input is outside PZ_DP2_INPUT_DATASET: $input_file" >&2; exit 1 ;;
esac

relative_path=${input_file#"$PZ_DP2_INPUT_DATASET"/}
output_file=$PZ_CUSTOM_STAGE2_OUTPUT/${relative_path%.parquet}.hdf5
mkdir -p "$(dirname "$output_file")"
validator=$PZ_CUSTOM_PROJECT_DIR/scripts/validate-stage2.py

if [ -f "$output_file" ]; then
    if "$PZ_PY" "$validator" pair "$PZ_CUSTOM_VARIANT" "$input_file" "$output_file"; then
        echo "Complete output already exists: $output_file"
        exit 0
    fi
    backup=$output_file.incomplete-${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID}
    mv "$output_file" "$backup"
    echo "Moved incomplete output to $backup"
fi

echo "variant=$PZ_CUSTOM_VARIANT"
echo "input=$input_file"
echo "output=$output_file"
echo "model=$PZ_CUSTOM_MODEL"
echo "config=$PZ_CUSTOM_ESTIMATE_CONFIG"

"$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" \
  "$input_file" \
  "$output_file" \
  --algorithm=dnf \
  --calibration-file="$PZ_CUSTOM_MODEL" \
  --bins=601 \
  --bands="$PZ_CUSTOM_BANDS" \
  --param-file="$PZ_CUSTOM_ESTIMATE_CONFIG" \
  --sfd-deredden \
  --sfd-coefficients-file="$PZ_CUSTOM_SFD_CONFIG" \
  --column-template='{band}_cModelMag_sfd' \
  --column-template-error='{band}_cModelMagErr_sfd' \
  --row-id-column=objectId \
  --dnf-stable-pdf \
  --output-ancil-columns=DNF_ZN

"$PZ_PY" "$validator" pair "$PZ_CUSTOM_VARIANT" "$input_file" "$output_file"
