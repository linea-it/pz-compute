#!/usr/bin/env bash
set -euo pipefail

: "${PZ_PY:?source env-dp2-stage3-hats.sh first}"
: "${PZ_COMPUTE_DIR:?source env-dp2-stage3-hats.sh first}"
: "${PZ_DP2_ROOT:?set PZ_DP2_ROOT first}"
: "${PZ_DP2_CUSTOM_ROOT:?set PZ_DP2_CUSTOM_ROOT first}"
: "${PZ_DP2_INPUT_DATASET:?set PZ_DP2_INPUT_DATASET first}"

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source_notebook=$script_dir/dnf_cmodel_griz_riz_qa.ipynb
output_dir=${PZ_QA_OUTPUT_DIR:-$PZ_DP2_CUSTOM_ROOT/qa/delivery}
output_name=dnf_cmodel_griz_riz_qa

test -f "$source_notebook"
mkdir -p "$output_dir"
export PZ_QA_OUTPUT_DIR=$output_dir

"$PZ_PY" -c 'import nbclient, nbconvert, nbformat, distributed, dask_jobqueue' 2>/dev/null || {
    echo "The selected PZ_PY environment needs nbclient, nbconvert, nbformat, distributed, and dask-jobqueue to render QA." >&2
    exit 1
}

for path in \
  "$output_dir/$output_name.ipynb" \
  "$output_dir/$output_name.html" \
  "$output_dir/qa_summary.json" \
  "$output_dir/SHA256SUMS"; do
    test ! -e "$path" || {
        echo "Refusing to overwrite QA artifact: $path" >&2
        exit 1
    }
done

"$PZ_PY" -m jupyter nbconvert \
  --to notebook \
  --execute \
  --ExecutePreprocessor.timeout=-1 \
  --output-dir="$output_dir" \
  --output="$output_name" \
  "$source_notebook"

"$PZ_PY" -m jupyter nbconvert \
  --to html \
  --no-input \
  --output-dir="$output_dir" \
  --output="$output_name" \
  "$output_dir/$output_name.ipynb"

(
  cd "$output_dir"
  sha256sum \
    "$output_name.ipynb" \
    "$output_name.html" \
    qa_summary.json > SHA256SUMS
)

printf 'QA delivery written to %s\n' "$output_dir"
