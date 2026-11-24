#!/usr/bin/env bash
set -euo pipefail
set -o pipefail

for name in PZ_CUSTOM_VARIANT PZ_DP2_ROOT PZ_DP2_CUSTOM_ROOT \
  PZ_DP2_INPUT_DATASET PZ_CUSTOM_STAGE2_OUTPUT PZ_CUSTOM_STAGE3 \
  PZ_CUSTOM_HATS_DIR PZ_CUSTOM_PROJECT_DIR PZ_STAGE3_RUN_TAG \
  PZ_HATS_MIN_WORKERS PZ_HATS_MAX_WORKERS PZ_HATS_SCALE_DOWN_DELAY \
  PZ_HATS_MARGIN_ARCSEC PZ_HATS_WORKER_CORES PZ_HATS_WORKER_MEMORY \
  PZ_HATS_WORKER_TIME PZ_COMPUTE_DIR PZ_PY; do
    test -n "${!name:-}" || { echo "missing $name" >&2; exit 1; }
done
: "${PZ_COMPUTE_REVISION:?missing PZ_COMPUTE_REVISION}"

case "$PZ_CUSTOM_VARIANT" in griz|riz) ;; *) exit 2 ;; esac

production_ready=$PZ_DP2_CUSTOM_ROOT/$PZ_CUSTOM_VARIANT/stage2/production/READY
test -f "$production_ready"
sha256sum --check --status "$production_ready" || {
    echo "Stage 2 production contract changed for $PZ_CUSTOM_VARIANT" >&2
    exit 1
}

benchmark_dir=$PZ_CUSTOM_STAGE3/benchmark/$PZ_STAGE3_RUN_TAG
worker_log_dir=$PZ_CUSTOM_STAGE3/log/dask-$PZ_STAGE3_RUN_TAG
driver_log_dir=$PZ_CUSTOM_STAGE3/log/driver-$PZ_STAGE3_RUN_TAG
worker_job_name=pz3c-${PZ_CUSTOM_VARIANT}-${PZ_STAGE3_RUN_TAG}
staging_dir=$PZ_CUSTOM_HATS_DIR.parquet_staging
pdf_dir=$PZ_CUSTOM_HATS_DIR.pdf

for target in "$PZ_CUSTOM_HATS_DIR" "$staging_dir" "$pdf_dir" \
  "$PZ_CUSTOM_STAGE3/production/READY" \
  "$PZ_CUSTOM_STAGE3/production/VALIDATION.json"; do
    test ! -e "$target" || {
        echo "Refusing to overwrite Stage 3 artifact: $target" >&2
        exit 1
    }
done
mkdir -p "$benchmark_dir" "$worker_log_dir" "$driver_log_dir" \
  "$PZ_CUSTOM_STAGE3/output"

{
    printf 'driver_start_time=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S)"
    date --iso-8601=seconds
    hostname
    "$PZ_PY" --version
    printf 'git_commit=%s\n' "$PZ_COMPUTE_REVISION"
    printf 'variant=%s\n' "$PZ_CUSTOM_VARIANT"
    printf 'pdf_layout=none\n'
    printf 'science_dtype=float64\n'
    printf 'summary_schema=rubin-dp2\n'
    printf 'summary_method=piecewise-linear\n'
    printf 'margin_threshold_arcsec=%s\n' "$PZ_HATS_MARGIN_ARCSEC"
} > "$benchmark_dir/run-context.log"
printf '%s\n' "$worker_job_name" > "$benchmark_dir/worker-job-name.txt"

driver_start=$(date --iso-8601=seconds)
status=0
TIMEFORMAT=$'wall_seconds=%R\nuser_cpu_seconds=%U\nsystem_cpu_seconds=%S'
set +e
{
    time "$PZ_COMPUTE_DIR/rail_scripts/pz-build-hats" \
      --require-complete-marker \
      --pdf-layout=none \
      --summary-prefix=dnf \
      --summary-schema=rubin-dp2 \
      --summary-dtype=float64 \
      --summary-method=piecewise-linear \
      --catalog-name=pz_summary \
      --margin-threshold="$PZ_HATS_MARGIN_ARCSEC" \
      --fast-path-size-mb=0 \
      --use-hats-import \
      --dask-cluster=slurm \
      --slurm-queue=cpu_photoz \
      --slurm-account=hpc-photoz \
      --slurm-cores="$PZ_HATS_WORKER_CORES" \
      --slurm-processes=1 \
      --slurm-memory="$PZ_HATS_WORKER_MEMORY" \
      --slurm-walltime="$PZ_HATS_WORKER_TIME" \
      --slurm-minimum-jobs="$PZ_HATS_MIN_WORKERS" \
      --slurm-maximum-jobs="$PZ_HATS_MAX_WORKERS" \
      --slurm-scale-down-delay="$PZ_HATS_SCALE_DOWN_DELAY" \
      --slurm-log-dir="$worker_log_dir" \
      --slurm-job-name="$worker_job_name" \
      "$PZ_DP2_INPUT_DATASET" \
      "$PZ_CUSTOM_STAGE2_OUTPUT" \
      "$PZ_CUSTOM_HATS_DIR" 2>&1 | tee "$driver_log_dir/driver.log"
    status=${PIPESTATUS[0]}
    if [ "$status" -eq 0 ]; then
        "$PZ_PY" "$PZ_CUSTOM_PROJECT_DIR/scripts/validate-hats.py" \
          "$PZ_CUSTOM_VARIANT" --write-ready 2>&1 | \
          tee -a "$driver_log_dir/driver.log"
        status=${PIPESTATUS[0]}
    fi
} 2> "$driver_log_dir/driver-resource-usage.log"
set -e

{
    printf 'start_time=%s\n' "$driver_start"
    printf 'end_time=%s\n' "$(date --iso-8601=seconds)"
    printf 'driver_exit_code=%s\n' "$status"
} >> "$driver_log_dir/driver-resource-usage.log"
printf '%s\n' "$status" > "$driver_log_dir/driver-exit-code.txt"
exit "$status"
