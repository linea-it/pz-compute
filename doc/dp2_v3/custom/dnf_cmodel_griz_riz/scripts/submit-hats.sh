#!/usr/bin/env bash
set -euo pipefail

usage() { echo "Usage: $0 griz|riz|all" >&2; }
selection=${1:-}
case "$selection" in
    griz|riz) variants=("$selection") ;;
    all) variants=(griz riz) ;;
    *) usage; exit 2 ;;
esac

: "${PZ_RUN_ROOT:?source env-dp2-stage3-hats.sh first}"
: "${PZ_PY:?source env-dp2-stage3-hats.sh first}"
: "${PZ_COMPUTE_DIR:?source env-dp2-stage3-hats.sh first}"
command -v sbatch >/dev/null

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$scripts_dir/variant-config.sh"
PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset}
PZ_HATS_MIN_WORKERS=${PZ_HATS_MIN_WORKERS:-1}
PZ_HATS_MAX_WORKERS=${PZ_HATS_MAX_WORKERS:-80}
PZ_HATS_SCALE_DOWN_DELAY=${PZ_HATS_SCALE_DOWN_DELAY:-180}
PZ_HATS_MARGIN_ARCSEC=${PZ_HATS_MARGIN_ARCSEC:-5}
PZ_HATS_WORKER_CORES=${PZ_HATS_WORKER_CORES:-2}
PZ_HATS_WORKER_MEMORY=${PZ_HATS_WORKER_MEMORY:-40GiB}
PZ_HATS_WORKER_TIME=${PZ_HATS_WORKER_TIME:-12:00:00}
export PZ_DP2_ROOT PZ_DP2_CUSTOM_ROOT PZ_DP2_INPUT_DATASET
export PZ_HATS_MARGIN_ARCSEC

for value in PZ_HATS_MIN_WORKERS PZ_HATS_MAX_WORKERS \
  PZ_HATS_SCALE_DOWN_DELAY PZ_HATS_WORKER_CORES; do
    case "${!value}" in
        ''|*[!0-9]*|0) echo "$value must be a positive integer" >&2; exit 2 ;;
    esac
done
if [ "$PZ_HATS_MIN_WORKERS" -gt "$PZ_HATS_MAX_WORKERS" ]; then
    echo "Require PZ_HATS_MIN_WORKERS <= PZ_HATS_MAX_WORKERS" >&2
    exit 2
fi
if ! awk -v value="$PZ_HATS_MARGIN_ARCSEC" \
  'BEGIN { exit !(value ~ /^([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$/ && value > 0) }'; then
    echo "PZ_HATS_MARGIN_ARCSEC must be a positive number" >&2
    exit 2
fi

# Preflight both variants before submitting the first driver.
for variant in "${variants[@]}"; do
    custom_dnf_variant_config "$variant"
    ready=$PZ_CUSTOM_STAGE2/production/READY
    test -f "$ready" || {
        echo "Missing validated Stage 2 production marker: $ready" >&2
        exit 1
    }
    sha256sum --check --status "$ready" || {
        echo "$variant Stage 2 production contract changed" >&2
        exit 1
    }
    for target in "$PZ_CUSTOM_HATS_DIR" \
      "$PZ_CUSTOM_HATS_DIR.parquet_staging" "$PZ_CUSTOM_HATS_DIR.pdf" \
      "$PZ_CUSTOM_STAGE3/production/READY" \
      "$PZ_CUSTOM_STAGE3/production/VALIDATION.json"; do
        test ! -e "$target" || {
            echo "Refusing to overwrite Stage 3 artifact: $target" >&2
            exit 1
        }
    done
done

for variant in "${variants[@]}"; do
    custom_dnf_variant_config "$variant"
    run_tag=production-$(date -u +%Y%m%dT%H%M%SZ)
    driver_log_dir=$PZ_CUSTOM_STAGE3/log/driver-$run_tag
    mkdir -p "$driver_log_dir" "$PZ_CUSTOM_STAGE3/output" \
      "$PZ_CUSTOM_STAGE3/benchmark"
    "$PZ_PY" -m pip freeze > "$PZ_CUSTOM_STAGE3/environment-freeze.txt"
    job_id=$(sbatch --parsable \
      --job-name="dp2c-hats-$variant" \
      --partition=cpu_photoz \
      --account=hpc-photoz \
      --nodes=1 \
      --ntasks=1 \
      --cpus-per-task=2 \
      --mem=8G \
      --time=2-00:00:00 \
      --output="$driver_log_dir/slurm-%j.out" \
      --error="$driver_log_dir/slurm-%j.err" \
      --export=ALL,PZ_CUSTOM_VARIANT="$variant",PZ_DP2_ROOT="$PZ_DP2_ROOT",PZ_DP2_CUSTOM_ROOT="$PZ_DP2_CUSTOM_ROOT",PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_CUSTOM_STAGE2_OUTPUT="$PZ_CUSTOM_STAGE2_OUTPUT",PZ_CUSTOM_STAGE3="$PZ_CUSTOM_STAGE3",PZ_CUSTOM_HATS_DIR="$PZ_CUSTOM_HATS_DIR",PZ_CUSTOM_PROJECT_DIR="$PZ_CUSTOM_PROJECT_DIR",PZ_STAGE3_RUN_TAG="$run_tag",PZ_HATS_MIN_WORKERS="$PZ_HATS_MIN_WORKERS",PZ_HATS_MAX_WORKERS="$PZ_HATS_MAX_WORKERS",PZ_HATS_SCALE_DOWN_DELAY="$PZ_HATS_SCALE_DOWN_DELAY",PZ_HATS_MARGIN_ARCSEC="$PZ_HATS_MARGIN_ARCSEC",PZ_HATS_WORKER_CORES="$PZ_HATS_WORKER_CORES",PZ_HATS_WORKER_MEMORY="$PZ_HATS_WORKER_MEMORY",PZ_HATS_WORKER_TIME="$PZ_HATS_WORKER_TIME" \
      "$scripts_dir/run-one-hats.sbatch")
    job_id=${job_id%%;*}
    printf '%s\t%s\t%s\t%s\n' \
      "$(date --iso-8601=seconds)" "$variant" "$job_id" "$run_tag" \
      >> "$PZ_CUSTOM_STAGE3/submitted-job-ids.tsv"
    echo "$variant: submitted Stage 3 driver $job_id ($run_tag)"
done
