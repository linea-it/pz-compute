#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 fzboost|bpz|all" >&2
}

selection=${1:-}
case "$selection" in
    fzboost|bpz) algorithms=("$selection") ;;
    all) algorithms=(fzboost bpz) ;;
    *) usage; exit 2 ;;
esac

: "${PZ_RUN_ROOT:?source env-dp2-gaap1p0.sh first}"
: "${PZ_PY:?source env-dp2-gaap1p0.sh first}"
command -v sbatch >/dev/null

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
doc_dir=$(cd "$scripts_dir/.." && pwd)
PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
training_data=$PZ_DP2_ROOT/common/training/train_clipped_v3_gaap1p0.hdf5

test -f "$training_data" || { echo "Missing training data: $training_data" >&2; exit 1; }

for algorithm in "${algorithms[@]}"; do
    case "$algorithm" in
        fzboost)
            config=$doc_dir/config/fzboost-train.yaml
            basename=model_dp2_v3p1_fzboost_dp2_6band_gold
            resources=(--nodelist=apl[17-25] --cpus-per-task=98 --mem=231G --time=03:00:00)
            ;;
        bpz)
            config=$doc_dir/config/bpz-train.yaml
            basename=model_dp2_v3p1_bpz_dp2_6band_gold
            resources=(--cpus-per-task=1 --mem=8G --time=01:00:00)
            ;;
    esac
    stage_dir=$PZ_DP2_ROOT/$algorithm/stage1
    model_dir=$stage_dir/model
    log_dir=$stage_dir/log
    job_log=$stage_dir/submitted-job-ids.tsv
    mkdir -p "$model_dir" "$log_dir" "$stage_dir/benchmark"
    "$PZ_PY" -m pip freeze > "$stage_dir/environment-freeze.txt"
    raw_model=$model_dir/$basename.raw.pickle
    model=$model_dir/$basename.pickle
    job_id=$(sbatch --parsable \
      --job-name="dp2-train-$algorithm" \
      --output="$log_dir/train-$algorithm-%j.out" \
      --error="$log_dir/train-$algorithm-%j.err" \
      "${resources[@]}" \
      --export=ALL,PZ_ALGORITHM="$algorithm",PZ_TRAINING_DATA="$training_data",PZ_TRAIN_CONFIG="$config",PZ_RAW_MODEL="$raw_model",PZ_MODEL="$model",PZ_DP2_DOC_DIR="$doc_dir" \
      "$scripts_dir/run-one-train.sbatch")
    job_id=${job_id%%;*}
    printf '%s\t%s\t%s\n' "$(date --iso-8601=seconds)" "$algorithm" "$job_id" >> "$job_log"
    echo "$algorithm: submitted training job $job_id"
done
