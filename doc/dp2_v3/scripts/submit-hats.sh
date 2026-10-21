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

: "${PZ_RUN_ROOT:?source env-dp2-stage3-hats.sh first}"
: "${PZ_PY:?source env-dp2-stage3-hats.sh first}"
command -v sbatch >/dev/null
command -v pz-build-hats >/dev/null

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/primary/catalogs/object}
PZ_HATS_WORKERS=${PZ_HATS_WORKERS:-82}

input_count=$(find "$PZ_DP2_INPUT_DATASET" -name '*.parq' | wc -l)
test "$input_count" -gt 0 || {
    echo "No input parquet files found under $PZ_DP2_INPUT_DATASET" >&2
    exit 1
}

for algorithm in "${algorithms[@]}"; do
    stage2_output=$PZ_DP2_ROOT/$algorithm/stage2/output
    output_count=$(find "$stage2_output" -name '*.hdf5' | wc -l)
    test "$input_count" -eq "$output_count" || {
        echo "$algorithm: expected $input_count Stage 2 outputs, found $output_count" >&2
        exit 1
    }

    stage3_run=$PZ_DP2_ROOT/$algorithm/stage3
    run_tag=production-$(date -u +%Y%m%dT%H%M%SZ)
    driver_log_dir=$stage3_run/log/driver-$run_tag
    job_log=$stage3_run/submitted-job-ids.tsv
    mkdir -p "$driver_log_dir" "$stage3_run/output" "$stage3_run/benchmark"
    "$PZ_PY" -m pip freeze > "$stage3_run/environment-freeze.txt"

    job_id=$(sbatch --parsable \
      --job-name="dp2-hats-$algorithm" \
      --partition=cpu_photoz \
      --account=hpc-photoz \
      --exclude='apl[26-28]' \
      --cpus-per-task=2 \
      --mem=8G \
      --time=2-00:00:00 \
      --output="$driver_log_dir/slurm-%j.out" \
      --error="$driver_log_dir/slurm-%j.err" \
      --export=ALL,PZ_ALGORITHM="$algorithm",PZ_DP2_ROOT="$PZ_DP2_ROOT",PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_STAGE3_RUN_TAG="$run_tag",PZ_HATS_WORKERS="$PZ_HATS_WORKERS" \
      "$scripts_dir/run-one-hats.sbatch")
    job_id=${job_id%%;*}
    printf '%s\t%s\t%s\t%s\n' \
      "$(date --iso-8601=seconds)" "$algorithm" "$job_id" "$run_tag" >> "$job_log"
    echo "$algorithm: submitted Stage 3 driver job $job_id ($run_tag)"
done
