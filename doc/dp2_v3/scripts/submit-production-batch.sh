#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: submit-production-batch.sh

Submit the official DP2 v3 algorithms as one serial, fail-fast workflow:
fzboost, then dnf, then bpz. Each algorithm completes Stages 1, 2, and 3,
including validation and Slurm profiling, before the next algorithm starts.

Optional environment overrides:
  PZ_BATCH_ALGORITHMS              comma-separated subset/order
  PZ_BATCH_CONTROLLER_TIME         controller Slurm walltime (default 14 days)
  PZ_BATCH_JOB_TIMEOUT_SECONDS     per-child wait timeout (default 10 days)
  PZ_BATCH_POLL_SECONDS            accounting poll interval (default 30)
  PZ_BATCH_MIN_FREE_GIB            initial free scratch space (default 8192 per selected algorithm)
  PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB  recheck before each algorithm (default 8192)
  PZ_HATS_MIN_WORKERS              Stage 3 adaptive minimum (default 1)
  PZ_HATS_MAX_WORKERS              Stage 3 adaptive maximum (default 80)
  PZ_HATS_SCALE_DOWN_DELAY         Stage 3 idle delay in seconds (default 180)
  PZ_HATS_MARGIN_ARCSEC            Stage 3 default margin width (default 5)
EOF
}

if [ "${1:-}" = --help ] || [ "${1:-}" = -h ]; then
    usage
    exit 0
fi
if [ "$#" -ne 0 ]; then
    usage
    exit 2
fi

: "${PZ_RUN_ROOT:?source env-dp2-gaap1p0.sh first}"
: "${PZ_COMPUTE_DIR:?source env-dp2-gaap1p0.sh first}"
command -v sbatch >/dev/null

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset}
PZ_BATCH_ALGORITHMS=${PZ_BATCH_ALGORITHMS:-fzboost,dnf,bpz}
PZ_BATCH_CONTROLLER_TIME=${PZ_BATCH_CONTROLLER_TIME:-14-00:00:00}
PZ_BATCH_JOB_TIMEOUT_SECONDS=${PZ_BATCH_JOB_TIMEOUT_SECONDS:-864000}
PZ_BATCH_POLL_SECONDS=${PZ_BATCH_POLL_SECONDS:-30}
PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB=${PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB:-8192}
IFS=',' read -r -a batch_algorithms_for_storage <<< "$PZ_BATCH_ALGORITHMS"
PZ_BATCH_MIN_FREE_GIB=${PZ_BATCH_MIN_FREE_GIB:-$((${#batch_algorithms_for_storage[@]} * 8192))}
PZ_HATS_MIN_WORKERS=${PZ_HATS_MIN_WORKERS:-1}
PZ_HATS_MAX_WORKERS=${PZ_HATS_MAX_WORKERS:-80}
PZ_HATS_SCALE_DOWN_DELAY=${PZ_HATS_SCALE_DOWN_DELAY:-180}
PZ_HATS_MARGIN_ARCSEC=${PZ_HATS_MARGIN_ARCSEC:-5}
controller_algorithms=${PZ_BATCH_ALGORITHMS//,/:}

run_tag=production-$(date -u +%Y%m%dT%H%M%SZ)
batch_root=$PZ_DP2_ROOT/batch
run_dir=$batch_root/$run_tag
controller_log=$run_dir/controller.log
controller_error=$run_dir/controller.err
ledger=$batch_root/submitted-controller-job-ids.tsv
mkdir -p "$batch_root"
mkdir "$run_dir"

job_id=$(sbatch --parsable \
  --job-name=dp2-production-batch \
  --partition=cpu_photoz \
  --account=hpc-photoz \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=2 \
  --mem=8G \
  --time="$PZ_BATCH_CONTROLLER_TIME" \
  --output="$controller_log" \
  --error="$controller_error" \
  --export=ALL,PZ_DP2_ROOT="$PZ_DP2_ROOT",PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_BATCH_RUN_TAG="$run_tag",PZ_BATCH_RUN_DIR="$run_dir",PZ_BATCH_ALGORITHMS="$controller_algorithms",PZ_BATCH_JOB_TIMEOUT_SECONDS="$PZ_BATCH_JOB_TIMEOUT_SECONDS",PZ_BATCH_POLL_SECONDS="$PZ_BATCH_POLL_SECONDS",PZ_BATCH_MIN_FREE_GIB="$PZ_BATCH_MIN_FREE_GIB",PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB="$PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB",PZ_HATS_MIN_WORKERS="$PZ_HATS_MIN_WORKERS",PZ_HATS_MAX_WORKERS="$PZ_HATS_MAX_WORKERS",PZ_HATS_SCALE_DOWN_DELAY="$PZ_HATS_SCALE_DOWN_DELAY",PZ_HATS_MARGIN_ARCSEC="$PZ_HATS_MARGIN_ARCSEC" \
  "$scripts_dir/run-production-batch.sh")
job_id=${job_id%%;*}

printf '%s\t%s\t%s\t%s\n' \
  "$(date --iso-8601=seconds)" "$job_id" "$run_tag" "$PZ_BATCH_ALGORITHMS" >> "$ledger"
printf '%s\n' "$job_id" > "$run_dir/controller-job-id.txt"

echo "submitted serial DP2 v3 production controller: $job_id"
echo "algorithm order: $PZ_BATCH_ALGORITHMS"
echo "run directory: $run_dir"
echo "monitor: squeue -j $job_id"
echo "follow: tail -F $controller_log $controller_error"
