#!/usr/bin/env bash
#SBATCH --job-name=dp2-pz
#SBATCH --partition=cpu_photoz
#SBATCH --account=hpc-photoz
#SBATCH --output=log/slurm-%A_%a.out
#SBATCH --error=log/slurm-%A_%a.err

set -euo pipefail

source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh

: "${PZ_ALGORITHM:?missing PZ_ALGORITHM}"
: "${PZ_RAIL_ALGORITHM:?missing PZ_RAIL_ALGORITHM}"
: "${PZ_DP2_INPUT_DATASET:?missing PZ_DP2_INPUT_DATASET}"
: "${PZ_MODEL:?missing PZ_MODEL}"
: "${PZ_ESTIMATE_CONFIG:?missing PZ_ESTIMATE_CONFIG}"
: "${PZ_SFD_CONFIG:?missing PZ_SFD_CONFIG}"
: "${PZ_OUTPUT_DIR:?missing PZ_OUTPUT_DIR}"
: "${PZ_FILE_LIST:?missing PZ_FILE_LIST}"

case "$PZ_ALGORITHM" in
    fzboost|bpz|dnf|bpz_test) ;;
    *) echo "Unsupported PZ_ALGORITHM: $PZ_ALGORITHM" >&2; exit 2 ;;
esac

input_file=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$PZ_FILE_LIST")
if [ -z "$input_file" ]; then
    echo "No input for array index $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

relative_path=${input_file#"$PZ_DP2_INPUT_DATASET"/}
output_file=$PZ_OUTPUT_DIR/${relative_path%.parquet}.hdf5
mkdir -p "$(dirname "$output_file")"

if [ -f "$output_file" ]; then
    if "$PZ_PY" "$PZ_COMPUTE_DIR/doc/dp2_v3/scripts/validate-stage2.py" \
      "$PZ_ALGORITHM" --file "$output_file" --sfd-config "$PZ_SFD_CONFIG"
    then
        echo "Complete output already exists: $output_file"
        exit 0
    fi
    backup=$output_file.rejected-${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID}
    test ! -e "$backup"
    mv "$output_file" "$backup"
    echo "Moved invalid or incompatible output to $backup"
fi

echo "algorithm=$PZ_ALGORITHM"
echo "input=$input_file"
echo "output=$output_file"
echo "model=$PZ_MODEL"
echo "config=$PZ_ESTIMATE_CONFIG"
echo "sfd_config=$PZ_SFD_CONFIG"

estimator_args=()
if [ "$PZ_RAIL_ALGORITHM" = bpz ]; then
    : "${PZ_BPZ_DATA_ROOT:?missing PZ_BPZ_DATA_ROOT}"
    echo "bpz_data_root=$PZ_BPZ_DATA_ROOT"
    estimator_args+=(--bpz-ref-data-path="$PZ_BPZ_DATA_ROOT")
elif [ "$PZ_RAIL_ALGORITHM" = dnf ]; then
    estimator_args+=(--dnf-stable-pdf --dnf-no-photometry-policy=nan)
fi

"$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" \
  "$input_file" \
  "$output_file" \
  --algorithm="$PZ_RAIL_ALGORITHM" \
  --calibration-file="$PZ_MODEL" \
  --bins=601 \
  --param-file="$PZ_ESTIMATE_CONFIG" \
  --sfd-deredden \
  --sfd-coefficients-file="$PZ_SFD_CONFIG" \
  --column-template='{band}_gaap1p0Mag_sfd' \
  --column-template-error='{band}_gaap1p0MagErr_sfd' \
  --row-id-column=objectId \
  --output-columns=i_gaap1p0Mag_sfd,refExtendedness \
  "${estimator_args[@]}"
