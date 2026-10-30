#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 fzboost|bpz|dnf|bpz_test|all" >&2
}

selection=${1:-}
case "$selection" in
    fzboost|bpz|dnf|bpz_test) algorithms=("$selection") ;;
    all) algorithms=(fzboost bpz dnf) ;;
    *) usage; exit 2 ;;
esac

: "${PZ_RUN_ROOT:?source env-dp2-stage3-hats.sh first}"
: "${PZ_PY:?source env-dp2-stage3-hats.sh first}"
command -v sbatch >/dev/null
command -v pz-build-hats >/dev/null

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset}
PZ_HATS_MIN_WORKERS=${PZ_HATS_MIN_WORKERS:-20}
PZ_HATS_MAX_WORKERS=${PZ_HATS_MAX_WORKERS:-${PZ_HATS_WORKERS:-80}}
PZ_HATS_SCALE_DOWN_DELAY=${PZ_HATS_SCALE_DOWN_DELAY:-180}

case "$PZ_HATS_MIN_WORKERS" in
    ''|*[!0-9]*) echo "PZ_HATS_MIN_WORKERS must be a positive integer" >&2; exit 2 ;;
esac
case "$PZ_HATS_MAX_WORKERS" in
    ''|*[!0-9]*) echo "PZ_HATS_MAX_WORKERS must be a positive integer" >&2; exit 2 ;;
esac
case "$PZ_HATS_SCALE_DOWN_DELAY" in
    ''|*[!0-9]*) echo "PZ_HATS_SCALE_DOWN_DELAY must be a positive integer number of seconds" >&2; exit 2 ;;
esac
if [ "$PZ_HATS_MIN_WORKERS" -lt 1 ] || [ "$PZ_HATS_MAX_WORKERS" -lt 1 ] || \
   [ "$PZ_HATS_MIN_WORKERS" -gt "$PZ_HATS_MAX_WORKERS" ]; then
    echo "Require 1 <= PZ_HATS_MIN_WORKERS <= PZ_HATS_MAX_WORKERS" >&2
    exit 2
fi
if [ "$PZ_HATS_SCALE_DOWN_DELAY" -lt 1 ]; then
    echo "PZ_HATS_SCALE_DOWN_DELAY must be at least 1 second" >&2
    exit 2
fi

input_count=$(find "$PZ_DP2_INPUT_DATASET" -type f -name '*.parquet' | wc -l)
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
    if [ "$algorithm" = bpz_test ]; then
        run_tag=test-$(date -u +%Y%m%dT%H%M%SZ)
    else
        run_tag=production-$(date -u +%Y%m%dT%H%M%SZ)
    fi
    driver_log_dir=$stage3_run/log/driver-$run_tag
    job_log=$stage3_run/submitted-job-ids.tsv
    mkdir -p "$driver_log_dir" "$stage3_run/output" "$stage3_run/benchmark"
    "$PZ_PY" -m pip freeze > "$stage3_run/environment-freeze.txt"

    job_id=$(sbatch --parsable \
      --job-name="dp2-hats-$algorithm" \
      --partition=cpu_photoz \
      --account=hpc-photoz \
      --exclude='apl[27-28]' \
      --nodes=1 \
      --ntasks=1 \
      --cpus-per-task=2 \
      --mem=8G \
      --time=2-00:00:00 \
      --output="$driver_log_dir/slurm-%j.out" \
      --error="$driver_log_dir/slurm-%j.err" \
      --export=ALL,PZ_ALGORITHM="$algorithm",PZ_DP2_ROOT="$PZ_DP2_ROOT",PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_STAGE3_RUN_TAG="$run_tag",PZ_HATS_MIN_WORKERS="$PZ_HATS_MIN_WORKERS",PZ_HATS_MAX_WORKERS="$PZ_HATS_MAX_WORKERS",PZ_HATS_SCALE_DOWN_DELAY="$PZ_HATS_SCALE_DOWN_DELAY" \
      "$scripts_dir/run-one-hats.sbatch")
    job_id=${job_id%%;*}
    printf '%s\t%s\t%s\t%s\n' \
      "$(date --iso-8601=seconds)" "$algorithm" "$job_id" "$run_tag" >> "$job_log"
    echo "$algorithm: submitted Stage 3 driver job $job_id ($run_tag, workers $PZ_HATS_MIN_WORKERS-$PZ_HATS_MAX_WORKERS, scale-down ${PZ_HATS_SCALE_DOWN_DELAY}s)"
done
