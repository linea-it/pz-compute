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

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$scripts_dir/algorithm-config.sh"

PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/primary/catalogs/object}
manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt

PZ_DP2_ROOT="$PZ_DP2_ROOT" PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET" \
  "$scripts_dir/prepare-estimation-manifests.sh" full >/dev/null
first_input=$(sed -n '1p' "$manifest")

for algorithm in "${algorithms[@]}"; do
    dp2_algorithm_config "$algorithm"
    model=$PZ_DP2_ROOT/$algorithm/stage1/model/$PZ_MODEL_BASENAME
    test -f "$model" || {
        echo "Missing model: $model" >&2
        exit 1
    }
done

for algorithm in "${algorithms[@]}"; do
    dp2_algorithm_config "$algorithm"
    model=$PZ_DP2_ROOT/$algorithm/stage1/model/$PZ_MODEL_BASENAME
    run_dir=$PZ_DP2_ROOT/$algorithm/stage2
    output=$run_dir/smoke/smoke-test.hdf5
    mkdir -p "$run_dir/smoke" "$run_dir/log" "$run_dir/output"
    if [ -e "$output" ]; then
        mv "$output" "$output.before-$(date +%s)"
    fi
    rm -f "$run_dir/smoke/READY"

    echo "Smoke test: $algorithm"
    "$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" \
      "$first_input" \
      "$output" \
      --algorithm="$algorithm" \
      --calibration-file="$model" \
      --bins=601 \
      --param-file="$PZ_ESTIMATE_CONFIG" \
      --sfd-deredden \
      --column-template='{band}_gaap1p0Mag_sfd' \
      --column-template-error='{band}_gaap1p0MagErr_sfd' \
      --row-id-column=objectId \
      --output-columns=i_gaap1p0Mag_sfd

    "$PZ_PY" - "$output" <<'PY'
import h5py
import sys

with h5py.File(sys.argv[1], "r") as handle:
    rows, bins = handle["data/yvals"].shape
    assert bins == 601
    assert handle["ancillary/i_gaap1p0Mag_sfd"].shape == (rows,)
    marker = handle["pz_compute"].attrs
    assert bool(marker["complete"])
    assert int(marker["row_count"]) == rows
    assert marker["row_id_column"] == "objectId"
print("valid:", sys.argv[1], rows)
PY
    sha256sum "$model" "$PZ_ESTIMATE_CONFIG" > "$run_dir/smoke/READY"
done
