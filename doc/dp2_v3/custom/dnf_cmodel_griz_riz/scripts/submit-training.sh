#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 griz|riz|all" >&2
}

selection=${1:-}
case "$selection" in
    griz|riz) variants=("$selection") ;;
    all) variants=(griz riz) ;;
    *) usage; exit 2 ;;
esac

: "${PZ_RUN_ROOT:?source env-dp2-gaap1p0.sh first}"
: "${PZ_PY:?source env-dp2-gaap1p0.sh first}"
: "${PZ_COMPUTE_DIR:?source env-dp2-gaap1p0.sh first}"
command -v sbatch >/dev/null

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$scripts_dir/variant-config.sh"
PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
export PZ_DP2_CUSTOM_ROOT

# Preflight every selected variant before submitting the first job. This keeps
# `all` atomic with respect to local validation and overwrite protection.
for variant in "${variants[@]}"; do
    custom_dnf_variant_config "$variant"
    test -f "$PZ_CUSTOM_TRAINING_DATA" || {
        echo "Missing $variant training data: $PZ_CUSTOM_TRAINING_DATA" >&2
        exit 1
    }
    test -f "$PZ_CUSTOM_TRAIN_CONFIG" || {
        echo "Missing $variant training config: $PZ_CUSTOM_TRAIN_CONFIG" >&2
        exit 1
    }

    model_dir=$PZ_CUSTOM_STAGE1/model
    log_dir=$PZ_CUSTOM_STAGE1/log
    raw_model=$model_dir/${PZ_CUSTOM_MODEL_BASENAME%.pickle}.raw.pickle
    model=$model_dir/$PZ_CUSTOM_MODEL_BASENAME
    for target in "$raw_model" "$model"; do
        test ! -e "$target" || {
            echo "Refusing to overwrite existing model artifact: $target" >&2
            exit 1
        }
    done
done

for variant in "${variants[@]}"; do
    custom_dnf_variant_config "$variant"
    model_dir=$PZ_CUSTOM_STAGE1/model
    log_dir=$PZ_CUSTOM_STAGE1/log
    raw_model=$model_dir/${PZ_CUSTOM_MODEL_BASENAME%.pickle}.raw.pickle
    model=$model_dir/$PZ_CUSTOM_MODEL_BASENAME
    mkdir -p "$model_dir" "$log_dir" "$PZ_CUSTOM_STAGE1/benchmark"
    "$PZ_PY" -m pip freeze > "$PZ_CUSTOM_STAGE1/environment-freeze.txt"
    job_id=$(sbatch --parsable \
      --job-name="dp2c-dnf-$variant-train" \
      --nodes=1 \
      --ntasks=1 \
      --cpus-per-task=1 \
      --mem=8G \
      --time=01:00:00 \
      --output="$log_dir/train-$variant-%j.out" \
      --error="$log_dir/train-$variant-%j.err" \
      --export=ALL,PZ_CUSTOM_VARIANT="$variant",PZ_CUSTOM_BANDS="$PZ_CUSTOM_BANDS",PZ_CUSTOM_TRAINING_DATA="$PZ_CUSTOM_TRAINING_DATA",PZ_CUSTOM_TRAIN_CONFIG="$PZ_CUSTOM_TRAIN_CONFIG",PZ_CUSTOM_RAW_MODEL="$raw_model",PZ_CUSTOM_MODEL="$model",PZ_CUSTOM_PROJECT_DIR="$PZ_CUSTOM_PROJECT_DIR" \
      "$scripts_dir/run-one-train.sbatch")
    job_id=${job_id%%;*}
    printf '%s\t%s\t%s\n' "$(date --iso-8601=seconds)" "$variant" "$job_id" \
      >> "$PZ_CUSTOM_STAGE1/submitted-job-ids.tsv"
    echo "$variant: submitted custom DNF training job $job_id"
done
