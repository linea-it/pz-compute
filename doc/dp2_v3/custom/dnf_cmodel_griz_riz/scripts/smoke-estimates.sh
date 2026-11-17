#!/usr/bin/env bash
set -euo pipefail

usage() { echo "Usage: $0 griz|riz|all" >&2; }
selection=${1:-}
case "$selection" in
    griz|riz) variants=("$selection") ;;
    all) variants=(griz riz) ;;
    *) usage; exit 2 ;;
esac

: "${PZ_RUN_ROOT:?source env-dp2-gaap1p0.sh first}"
: "${PZ_COMPUTE_DIR:?source env-dp2-gaap1p0.sh first}"
: "${PZ_PY:?source env-dp2-gaap1p0.sh first}"

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$scripts_dir/variant-config.sh"
PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset}
PZ_SMOKE_ROWS=${PZ_SMOKE_ROWS:-10000}
export PZ_DP2_ROOT PZ_DP2_CUSTOM_ROOT PZ_DP2_INPUT_DATASET

case "$PZ_SMOKE_ROWS" in
    ''|*[!0-9]*|0) echo "PZ_SMOKE_ROWS must be a positive integer" >&2; exit 2 ;;
esac

PZ_DP2_ROOT="$PZ_DP2_ROOT" PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET" \
  "$PZ_COMPUTE_DIR/doc/dp2_v3/scripts/prepare-estimation-manifests.sh" all >/dev/null
manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
first_input=$(sed -n '1p' "$manifest")
smoke_dir=$PZ_DP2_CUSTOM_ROOT/common/smoke
smoke_input=$smoke_dir/smoke-input.parquet
mkdir -p "$smoke_dir"
temporary=$(mktemp "$smoke_dir/smoke-input.tmp.XXXXXX")
trap 'rm -f "$temporary"' EXIT

"$PZ_PY" - "$first_input" "$temporary" "$PZ_SMOKE_ROWS" <<'PY'
import sys
import pyarrow as pa
import pyarrow.parquet as pq
from rail_scripts.photometry import projected_input_columns

source, destination, row_limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
parquet = pq.ParquetFile(source)
required = []
for band in "griz":
    required.extend((f"{band}_cModelMag_sfd", f"{band}_cModelMagErr_sfd"))
required.append("objectId")
columns = projected_input_columns(parquet.schema_arrow.names, required, "ebv")
if "objectId" not in parquet.schema_arrow.names:
    raise RuntimeError(f"objectId is missing from smoke input: {source}")
if "objectId" not in columns:
    columns.append("objectId")
try:
    batch = next(parquet.iter_batches(batch_size=row_limit, columns=columns))
except StopIteration as error:
    raise RuntimeError(f"smoke input has no rows: {source}") from error
table = pa.Table.from_batches([batch]).slice(0, row_limit)
pq.write_table(table, destination, compression="zstd")
print(f"Smoke input: {table.num_rows} rows from {source}")
PY
mv "$temporary" "$smoke_input"
trap - EXIT

"$PZ_PY" "$scripts_dir/validate-models.py" "$selection"

# Refuse every selected destination before starting the first estimate.
for variant in "${variants[@]}"; do
    custom_dnf_variant_config "$variant"
    output=$PZ_CUSTOM_STAGE2/smoke/smoke-test.hdf5
    test ! -e "$output" || {
        echo "Refusing to overwrite smoke output: $output" >&2
        exit 1
    }
    test ! -e "$PZ_CUSTOM_STAGE2/smoke/READY" || {
        echo "Refusing to overwrite smoke marker: $PZ_CUSTOM_STAGE2/smoke/READY" >&2
        exit 1
    }
done

for variant in "${variants[@]}"; do
    custom_dnf_variant_config "$variant"
    output=$PZ_CUSTOM_STAGE2/smoke/smoke-test.hdf5
    mkdir -p "$PZ_CUSTOM_STAGE2/smoke" "$PZ_CUSTOM_STAGE2/log" "$PZ_CUSTOM_STAGE2/output"
    "$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" \
      "$smoke_input" "$output" \
      --algorithm=dnf \
      --calibration-file="$PZ_CUSTOM_MODEL" \
      --bins=601 \
      --bands="$PZ_CUSTOM_BANDS" \
      --param-file="$PZ_CUSTOM_ESTIMATE_CONFIG" \
      --sfd-deredden \
      --sfd-coefficients-file="$PZ_CUSTOM_SFD_CONFIG" \
      --column-template='{band}_cModelMag_sfd' \
      --column-template-error='{band}_cModelMagErr_sfd' \
      --row-id-column=objectId \
      --output-ancil-columns=DNF_ZN

    "$PZ_PY" "$scripts_dir/validate-stage2.py" \
      pair "$variant" "$smoke_input" "$output"
    sha256sum \
      "$PZ_CUSTOM_MODEL" \
      "$PZ_CUSTOM_ESTIMATE_CONFIG" \
      "$PZ_CUSTOM_SFD_CONFIG" \
      "$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" \
      "$scripts_dir/run-one-estimate.sbatch" \
      "$scripts_dir/validate-stage2.py" \
      > "$PZ_CUSTOM_STAGE2/smoke/READY"
done
