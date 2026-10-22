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
: "${PZ_COMPUTE_DIR:?source env-dp2-gaap1p0.sh first}"
: "${PZ_PY:?source env-dp2-gaap1p0.sh first}"
command -v sbatch >/dev/null

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$scripts_dir/algorithm-config.sh"

PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset}
default_manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
manifest=${PZ_INPUT_MANIFEST:-$default_manifest}

PZ_DP2_ROOT="$PZ_DP2_ROOT" PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET" \
  "$scripts_dir/prepare-estimation-manifests.sh" full >/dev/null
if [ -n "${PZ_INPUT_MANIFEST:-}" ]; then
    test -f "$manifest" || { echo "Missing PZ_INPUT_MANIFEST: $manifest" >&2; exit 1; }
fi
nfiles=$(wc -l < "$manifest")
if [ "$nfiles" -eq 0 ]; then
    echo "No .parquet files found below $PZ_DP2_INPUT_DATASET" >&2
    exit 1
fi

for algorithm in "${algorithms[@]}"; do
    dp2_algorithm_config "$algorithm"
    model=$PZ_DP2_ROOT/$algorithm/stage1/model/$PZ_MODEL_BASENAME
    run_dir=$PZ_DP2_ROOT/$algorithm/stage2
    test -f "$model" || { echo "Missing model: $model" >&2; exit 1; }
    test -f "$run_dir/smoke/READY" || {
        echo "Run $scripts_dir/smoke-estimates.sh $algorithm first" >&2
        exit 1
    }
    sha256sum --check --status "$run_dir/smoke/READY" || {
        echo "Model or config changed; rerun the $algorithm smoke test" >&2
        exit 1
    }
done

for algorithm in "${algorithms[@]}"; do
    dp2_algorithm_config "$algorithm"
    model=$PZ_DP2_ROOT/$algorithm/stage1/model/$PZ_MODEL_BASENAME
    run_dir=$PZ_DP2_ROOT/$algorithm/stage2
    output_dir=$run_dir/output
    job_log=$run_dir/submitted-job-ids.tsv
    mkdir -p "$output_dir" "$run_dir/log" "$run_dir/benchmark"
    "$PZ_PY" -m pip freeze > "$run_dir/environment-freeze.txt"

    upper=${algorithm^^}
    concurrency_name=PZ_${upper}_MAX_CONCURRENT
    memory_name=PZ_${upper}_MEMORY
    time_name=PZ_${upper}_TIME
    concurrency=${!concurrency_name:-$PZ_DEFAULT_MAX_CONCURRENT}
    memory=${!memory_name:-$PZ_DEFAULT_MEMORY}
    walltime=${!time_name:-$PZ_DEFAULT_TIME}

    job_id=$(cd "$run_dir" && sbatch --parsable \
      --job-name="dp2-$algorithm" \
      --mem="$memory" \
      --time="$walltime" \
      --array="0-$((nfiles - 1))%$concurrency" \
      --export=ALL,PZ_ALGORITHM="$algorithm",PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_MODEL="$model",PZ_ESTIMATE_CONFIG="$PZ_ESTIMATE_CONFIG",PZ_OUTPUT_DIR="$output_dir",PZ_FILE_LIST="$manifest" \
      "$scripts_dir/run-one-estimate.sbatch")
    job_id=${job_id%%;*}
    printf '%s\t%s\t%s\n' "$(date --iso-8601=seconds)" "$algorithm" "$job_id" >> "$job_log"
    echo "$algorithm: submitted array $job_id ($nfiles files, max $concurrency concurrent)"
done

echo "Submission records are stored in each algorithm's stage2 directory."
