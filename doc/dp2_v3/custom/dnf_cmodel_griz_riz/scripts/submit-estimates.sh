#!/usr/bin/env bash
set -euo pipefail

usage() { echo "Usage: $0 griz|riz|all pilot|production" >&2; }
selection=${1:-}
scope=${2:-}
case "$selection" in
    griz|riz) variants=("$selection") ;;
    all) variants=(griz riz) ;;
    *) usage; exit 2 ;;
esac
case "$scope" in pilot|production) ;; *) usage; exit 2 ;; esac

: "${PZ_RUN_ROOT:?source env-dp2-gaap1p0.sh first}"
: "${PZ_COMPUTE_DIR:?source env-dp2-gaap1p0.sh first}"
: "${PZ_PY:?source env-dp2-gaap1p0.sh first}"
command -v sbatch >/dev/null

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$scripts_dir/variant-config.sh"
PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset}
export PZ_DP2_ROOT PZ_DP2_CUSTOM_ROOT PZ_DP2_INPUT_DATASET

PZ_DP2_ROOT="$PZ_DP2_ROOT" PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET" \
  "$PZ_COMPUTE_DIR/doc/dp2_v3/scripts/prepare-estimation-manifests.sh" all >/dev/null
if [ "$scope" = pilot ]; then
    manifest=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
    concurrency=${PZ_CUSTOM_PILOT_MAX_CONCURRENT:-5}
    memory=${PZ_CUSTOM_PILOT_MEMORY:-40G}
    walltime=${PZ_CUSTOM_PILOT_TIME:-02:00:00}
else
    manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
    : "${PZ_CUSTOM_DNF_MAX_CONCURRENT:?set from accepted pilot evidence}"
    : "${PZ_CUSTOM_DNF_MEMORY:?set from accepted pilot evidence}"
    : "${PZ_CUSTOM_DNF_TIME:?set from accepted pilot evidence}"
    concurrency=$PZ_CUSTOM_DNF_MAX_CONCURRENT
    memory=$PZ_CUSTOM_DNF_MEMORY
    walltime=$PZ_CUSTOM_DNF_TIME
fi
nfiles=$(wc -l < "$manifest")
test "$nfiles" -gt 0
case "$concurrency" in
    ''|*[!0-9]*|0) echo "concurrency must be a positive integer: $concurrency" >&2; exit 2 ;;
esac

# Validate every selected variant before the first submission.
for variant in "${variants[@]}"; do
    custom_dnf_variant_config "$variant"
    for path in "$PZ_CUSTOM_MODEL" "$PZ_CUSTOM_ESTIMATE_CONFIG" "$PZ_CUSTOM_SFD_CONFIG"; do
        test -f "$path" || { echo "Missing required file: $path" >&2; exit 1; }
    done
    smoke_ready=$PZ_CUSTOM_STAGE2/smoke/READY
    test -f "$smoke_ready" || {
        echo "Run $scripts_dir/smoke-estimates.sh $variant first" >&2
        exit 1
    }
    sha256sum --check --status "$smoke_ready" || {
        echo "$variant smoke inputs changed; rerun the smoke test" >&2
        exit 1
    }
    if [ "$scope" = production ]; then
        pilot_ready=$PZ_CUSTOM_STAGE2/pilot/READY
        test -f "$pilot_ready" || {
            echo "Validate the $variant pilot with --ready-scope pilot first" >&2
            exit 1
        }
        sha256sum --check --status "$pilot_ready" || {
            echo "$variant pilot contract changed; rerun and revalidate it" >&2
            exit 1
        }
    fi
done

for variant in "${variants[@]}"; do
    custom_dnf_variant_config "$variant"
    mkdir -p "$PZ_CUSTOM_STAGE2_OUTPUT" "$PZ_CUSTOM_STAGE2/log" \
      "$PZ_CUSTOM_STAGE2/benchmark"
    "$PZ_PY" -m pip freeze > "$PZ_CUSTOM_STAGE2/environment-freeze.txt"
    job_id=$(cd "$PZ_CUSTOM_STAGE2" && sbatch --parsable \
      --job-name="dp2c-dnf-$variant-$scope" \
      --nodes=1 \
      --ntasks=1 \
      --cpus-per-task=1 \
      --mem="$memory" \
      --time="$walltime" \
      --array="0-$((nfiles - 1))%$concurrency" \
      --export=ALL,PZ_CUSTOM_VARIANT="$variant",PZ_CUSTOM_BANDS="$PZ_CUSTOM_BANDS",PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_CUSTOM_MODEL="$PZ_CUSTOM_MODEL",PZ_CUSTOM_ESTIMATE_CONFIG="$PZ_CUSTOM_ESTIMATE_CONFIG",PZ_CUSTOM_SFD_CONFIG="$PZ_CUSTOM_SFD_CONFIG",PZ_CUSTOM_STAGE2_OUTPUT="$PZ_CUSTOM_STAGE2_OUTPUT",PZ_FILE_LIST="$manifest",PZ_CUSTOM_PROJECT_DIR="$PZ_CUSTOM_PROJECT_DIR" \
      "$scripts_dir/run-one-estimate.sbatch")
    job_id=${job_id%%;*}
    printf '%s\t%s\t%s\t%s\n' \
      "$(date --iso-8601=seconds)" "$variant" "$scope" "$job_id" \
      >> "$PZ_CUSTOM_STAGE2/submitted-job-ids.tsv"
    echo "$variant: submitted $scope array $job_id ($nfiles files, max $concurrency concurrent)"
done
