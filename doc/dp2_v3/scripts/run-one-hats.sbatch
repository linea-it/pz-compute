#!/usr/bin/env bash
set -euo pipefail
set -o pipefail

: "${PZ_ALGORITHM:?missing PZ_ALGORITHM}"
: "${PZ_DP2_ROOT:?missing PZ_DP2_ROOT}"
: "${PZ_DP2_INPUT_DATASET:?missing PZ_DP2_INPUT_DATASET}"
: "${PZ_STAGE3_RUN_TAG:?missing PZ_STAGE3_RUN_TAG}"
: "${PZ_HATS_WORKERS:?missing PZ_HATS_WORKERS}"
: "${PZ_COMPUTE_DIR:?missing PZ_COMPUTE_DIR}"
: "${PZ_PY:?missing PZ_PY}"
command -v pz-build-hats >/dev/null

case "$PZ_ALGORITHM" in
    fzboost|bpz|bpz_test) ;;
    *) echo "Unsupported PZ_ALGORITHM: $PZ_ALGORITHM" >&2; exit 2 ;;
esac

stage2_output=$PZ_DP2_ROOT/$PZ_ALGORITHM/stage2/output
stage3_run=$PZ_DP2_ROOT/$PZ_ALGORITHM/stage3
hats_dir=$stage3_run/output/pz-$PZ_ALGORITHM-gaap1p0-clipped-hats
benchmark_dir=$stage3_run/benchmark/$PZ_STAGE3_RUN_TAG
worker_log_dir=$stage3_run/log/dask-$PZ_STAGE3_RUN_TAG
driver_log_dir=$stage3_run/log/driver-$PZ_STAGE3_RUN_TAG

mkdir -p "$benchmark_dir" "$worker_log_dir" "$driver_log_dir" "$stage3_run/output"

{
    date --iso-8601=seconds
    hostname
    "$PZ_PY" --version
    git -C "$PZ_COMPUTE_DIR" rev-parse HEAD
} > "$benchmark_dir/run-context.log"

driver_start=$(date --iso-8601=seconds)
status=0
TIMEFORMAT=$'wall_seconds=%R\nuser_cpu_seconds=%U\nsystem_cpu_seconds=%S'
set +e
{
    time pz-build-hats \
      --overwrite \
      --require-complete-marker \
      --pdf-dtype=float32 \
      --fast-path-size-mb=0 \
      --use-hats-import \
      --dask-cluster=slurm \
      --slurm-queue=cpu_photoz \
      --slurm-account=hpc-photoz \
      --slurm-exclude='apl[26-28]' \
      --slurm-cores=8 \
      --slurm-processes=1 \
      --slurm-memory=40GiB \
      --slurm-walltime=12:00:00 \
      --slurm-minimum-jobs="$PZ_HATS_WORKERS" \
      --slurm-maximum-jobs="$PZ_HATS_WORKERS" \
      --slurm-log-dir="$worker_log_dir" \
      "$PZ_DP2_INPUT_DATASET" \
      "$stage2_output" \
      "$hats_dir" 2>&1 | tee "$driver_log_dir/driver.log"
    status=${PIPESTATUS[0]}
} 2> "$driver_log_dir/driver-resource-usage.log"
set -e

{
    printf 'start_time=%s\n' "$driver_start"
    printf 'end_time=%s\n' "$(date --iso-8601=seconds)"
    printf 'driver_exit_code=%s\n' "$status"
} >> "$driver_log_dir/driver-resource-usage.log"
printf '%s\n' "$status" > "$driver_log_dir/driver-exit-code.txt"
exit "$status"
