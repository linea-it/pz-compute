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

: "${PZ_RUN_ROOT:?source env-dp2-gaap1p0.sh first}"
: "${PZ_COMPUTE_DIR:?source env-dp2-gaap1p0.sh first}"
: "${PZ_PY:?source env-dp2-gaap1p0.sh first}"

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$scripts_dir/algorithm-config.sh"

PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset}
PZ_SMOKE_ROWS=${PZ_SMOKE_ROWS:-10000}
manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt

case "$PZ_SMOKE_ROWS" in
    ''|*[!0-9]*|0)
        echo "PZ_SMOKE_ROWS must be a positive integer: $PZ_SMOKE_ROWS" >&2
        exit 2
        ;;
esac

PZ_DP2_ROOT="$PZ_DP2_ROOT" PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET" \
  "$scripts_dir/prepare-estimation-manifests.sh" full >/dev/null
first_input=$(sed -n '1p' "$manifest")
smoke_input_dir=$PZ_DP2_ROOT/common/smoke
smoke_input=$smoke_input_dir/smoke-input.parquet
mkdir -p "$smoke_input_dir"
smoke_tmp=$(mktemp "$smoke_input_dir/smoke-input.tmp.XXXXXX")
trap 'rm -f "$smoke_tmp"' EXIT

"$PZ_PY" - "$first_input" "$smoke_tmp" "$PZ_SMOKE_ROWS" <<'PY'
import sys

import pyarrow as pa
import pyarrow.parquet as pq

from rail_scripts.photometry import projected_input_columns


source, destination, row_limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
bands = "ugrizy"
required = [f"{band}_gaap1p0Mag_sfd" for band in bands]
required += [f"{band}_gaap1p0MagErr_sfd" for band in bands]

parquet = pq.ParquetFile(source)
columns = projected_input_columns(parquet.schema_arrow.names, required, "ebv")
if "objectId" not in parquet.schema_arrow.names:
    raise RuntimeError(f"objectId is missing from smoke-test input: {source}")
if "objectId" not in columns:
    columns.append("objectId")

try:
    batch = next(parquet.iter_batches(batch_size=row_limit, columns=columns))
except StopIteration as error:
    raise RuntimeError(f"smoke-test input has no rows: {source}") from error

table = pa.Table.from_batches([batch]).slice(0, row_limit)
pq.write_table(table, destination, compression="zstd")
print(f"Smoke input: {table.num_rows} rows from {source}")
PY

mv "$smoke_tmp" "$smoke_input"
trap - EXIT

for algorithm in "${algorithms[@]}"; do
    dp2_algorithm_config "$algorithm"
    model=$PZ_DP2_ROOT/$algorithm/stage1/model/$PZ_MODEL_BASENAME
    test -f "$model" || {
        echo "Missing model: $model" >&2
        exit 1
    }
    if [ "$PZ_RAIL_ALGORITHM" = bpz ]; then
        mkdir -p "$PZ_BPZ_DATA_ROOT/AB" || {
            echo "BPZ AB cache is not writable: $PZ_BPZ_DATA_ROOT/AB" >&2
            exit 1
        }
        test -w "$PZ_BPZ_DATA_ROOT/AB" || {
            echo "BPZ AB cache is not writable: $PZ_BPZ_DATA_ROOT/AB" >&2
            exit 1
        }
        "$scripts_dir/validate-bpz-reference-data.py" \
          "$PZ_BPZ_DATA_ROOT" "$PZ_BPZ_SPECTRA_FILE" "$PZ_BPZ_EXPECTED_SEDS"
    fi
done

for algorithm in "${algorithms[@]}"; do
    dp2_algorithm_config "$algorithm"
    model=$PZ_DP2_ROOT/$algorithm/stage1/model/$PZ_MODEL_BASENAME
    run_dir=$PZ_DP2_ROOT/$algorithm/stage2
    output=$run_dir/smoke/smoke-test.hdf5
    inprogress=$run_dir/smoke/inprogress_smoke-test.hdf5
    mkdir -p "$run_dir/smoke" "$run_dir/log" "$run_dir/output"
    if [ -e "$output" ]; then
        mv "$output" "$output.before-$(date +%s)"
    fi
    if [ -e "$inprogress" ]; then
        mv "$inprogress" "$inprogress.before-$(date +%s)"
    fi
    rm -f "$run_dir/smoke/READY"

    echo "Smoke test: $algorithm"
    bpz_args=()
    if [ "$PZ_RAIL_ALGORITHM" = bpz ]; then
        bpz_args+=(--bpz-ref-data-path="$PZ_BPZ_DATA_ROOT")
        echo "BPZ reference data: $PZ_BPZ_DATA_ROOT"
    fi

    "$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" \
      "$smoke_input" \
      "$output" \
      --algorithm="$PZ_RAIL_ALGORITHM" \
      --calibration-file="$model" \
      --bins=601 \
      --param-file="$PZ_ESTIMATE_CONFIG" \
      --sfd-deredden \
      --sfd-coefficients-file="$PZ_SFD_CONFIG" \
      --column-template='{band}_gaap1p0Mag_sfd' \
      --column-template-error='{band}_gaap1p0MagErr_sfd' \
      --row-id-column=objectId \
      --output-columns=i_gaap1p0Mag_sfd \
      "${bpz_args[@]}"

    "$PZ_PY" - "$output" "$PZ_SFD_CONFIG" <<'PY'
import h5py
import numpy as np
import sys
import yaml

with open(sys.argv[2], encoding="utf-8") as stream:
    expected_sfd = yaml.safe_load(stream)["sfd_a_ebv"]

with h5py.File(sys.argv[1], "r") as handle:
    rows, bins = handle["data/yvals"].shape
    assert bins == 601
    assert handle["ancillary/i_gaap1p0Mag_sfd"].shape == (rows,)
    marker = handle["pz_compute"].attrs
    assert bool(marker["complete"])
    assert int(marker["row_count"]) == rows
    assert marker["row_id_column"] == "objectId"
    assert marker["sfd_bands"] == "ugrizy"
    np.testing.assert_allclose(
        marker["sfd_a_ebv"],
        [expected_sfd[band] for band in "ugrizy"],
        rtol=0,
        atol=0,
    )
print("valid:", sys.argv[1], rows)
PY
    ready_files=("$model" "$PZ_ESTIMATE_CONFIG" "$PZ_SFD_CONFIG")
    if [ "$PZ_RAIL_ALGORITHM" = bpz ]; then
        mapfile -t bpz_reference_files < <(
            "$scripts_dir/validate-bpz-reference-data.py" \
              "$PZ_BPZ_DATA_ROOT" "$PZ_BPZ_SPECTRA_FILE" \
              "$PZ_BPZ_EXPECTED_SEDS" --list-files
        )
        ready_files+=("${bpz_reference_files[@]}")
    fi
    sha256sum "${ready_files[@]}" > "$run_dir/smoke/READY"
done
