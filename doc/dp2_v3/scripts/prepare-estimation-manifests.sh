#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 full|all" >&2
}

mode=${1:-all}
case "$mode" in
    full|all) ;;
    *) usage; exit 2 ;;
esac

: "${PZ_RUN_ROOT:?source env-dp2-gaap1p0.sh first}"

PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
PZ_DP2_INPUT_DATASET=${PZ_DP2_INPUT_DATASET:-/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset}
manifest_dir=$PZ_DP2_ROOT/common/manifests
full_manifest=$manifest_dir/input-parquet-files.txt
pilot_manifest=$manifest_dir/pilot-parquet-files.txt

mkdir -p "$manifest_dir"
full_tmp=$(mktemp "$manifest_dir/input-parquet-files.tmp.XXXXXX")
find "$PZ_DP2_INPUT_DATASET" -type f -name '*.parquet' | LC_ALL=C sort > "$full_tmp"
if [ ! -s "$full_tmp" ]; then
    rm -f "$full_tmp"
    echo "No .parquet files found below $PZ_DP2_INPUT_DATASET" >&2
    exit 1
fi
mv "$full_tmp" "$full_manifest"
echo "full manifest: $full_manifest ($(wc -l < "$full_manifest") files)"

if [ "$mode" = all ]; then
    pilot_tmp=$(mktemp "$manifest_dir/pilot-parquet-files.tmp.XXXXXX")
    while IFS= read -r path; do
        printf '%s\t%s\n' "$(stat --format='%s' "$path")" "$path"
    done < "$full_manifest" | LC_ALL=C sort -t $'\t' -k1,1nr -k2,2 |
      awk -F '\t' 'NR <= 5 {sub(/^[^\t]*\t/, ""); print}' > "$pilot_tmp"
    mv "$pilot_tmp" "$pilot_manifest"
    echo "pilot manifest: $pilot_manifest ($(wc -l < "$pilot_manifest") files)"
fi
