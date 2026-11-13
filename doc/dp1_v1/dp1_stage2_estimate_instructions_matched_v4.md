# DP1 GAaP 1.0 FlexZBoost Stage 2: Matched v4 Model

This document describes how to run photo-z estimation on Apollo/LIneA after
generating the DP1 GAaP 1.0 FlexZBoost pickle described in
`dp1_stage1_train_instructions_matched_v4.md`.

The input is the complete LSST DP1 Skinny Object Catalog with dereddened GAaP
1.0 magnitudes, stored on Apollo as a partitioned parquet tree:

```text
/data/cl/lsst/dp1/secondary/catalogs/skinny_collection/mag/gaap1p0/sfd/catalog/dataset
```

The parquet files are stored in subdirectories below that root. This workflow
discovers them recursively and preserves their relative paths in the output
tree.

All parquet files are expected to have the same schema, including:

```text
u_gaap1p0Mag_dered, g_gaap1p0Mag_dered, r_gaap1p0Mag_dered
i_gaap1p0Mag_dered, z_gaap1p0Mag_dered, y_gaap1p0Mag_dered
u_gaap1p0MagErr_dered, g_gaap1p0MagErr_dered, r_gaap1p0MagErr_dered
i_gaap1p0MagErr_dered, z_gaap1p0MagErr_dered, y_gaap1p0MagErr_dered
coord_ra, coord_dec, objectId
```

The magnitudes are already dereddened. Do not apply another extinction
correction. A representative input parquet was inspected with 461,140 rows,
no nulls in the required photometric columns, and `99.0` as the non-detection
sentinel.

## 0. Login

Access Apollo from a terminal or JupyterHub terminal:

```bash
ssh loginapl01
```

Load conda or miniconda if your shell does not already do it. The exact command
depends on your Apollo account configuration.

## 1. Prepare the Apollo environment

Use `/scripts` for source code, conda environments, package caches, and helper
scripts. Use `/scratch` for run directories, file lists, logs, temporary files,
and outputs.

```bash
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp1_gaap1p0

mkdir -p "$PZ_INSTALL_ROOT" "$PZ_SRC_DIR" "$PZ_RUN_ROOT" "$SCRIPTS/bin"
mkdir -p "$PZ_INSTALL_ROOT/conda_pkgs" "$PZ_INSTALL_ROOT/pip_cache"

export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
```

Clone or update `pz-compute` under `/scripts`:

```bash
cd "$PZ_SRC_DIR"

if [ ! -d pz-compute ]; then
    git clone https://github.com/linea-it/pz-compute
fi

cd "$PZ_COMPUTE_DIR"
git status --short
```

Create and activate the conda environment if it does not exist yet:

```bash
if [ ! -d "$PZ_CONDA_ENV" ]; then
    conda create -y --prefix "$PZ_CONDA_ENV" python=3.12 pip
fi

conda activate "$PZ_CONDA_ENV"
```

Install RAIL dependencies if this environment has not already been prepared:

```bash
PZ_INSTALL_ROOT="$PZ_INSTALL_ROOT" "$PZ_COMPUTE_DIR/rail_scripts/install-pz-rail"
```

When prompted by `install-pz-rail`, type:

```text
yes
```

Install the packages used by the inspection and conversion commands:

```bash
conda install -y -c conda-forge pyarrow tables-io hdf5 h5py pandas
```

Create a script link under `/scripts/$(whoami)/bin`:

```bash
ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" "$SCRIPTS/bin/rail-estimate"
chmod +x "$SCRIPTS/bin/rail-estimate"
```

Create an environment loader for interactive shells and Slurm jobs:

```bash
cat > "$PZ_INSTALL_ROOT/env-dp1-gaap1p0-estimate.sh" <<'EOF'
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp1_gaap1p0
export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
export PATH=$PZ_CONDA_ENV/bin:$SCRIPTS/bin:$PZ_COMPUTE_DIR/rail_scripts:$PATH
export PYTHONPATH=$PZ_COMPUTE_DIR/rail_scripts:${PYTHONPATH:-}
EOF

chmod +x "$PZ_INSTALL_ROOT/env-dp1-gaap1p0-estimate.sh"
source "$PZ_INSTALL_ROOT/env-dp1-gaap1p0-estimate.sh"
```

The loader intentionally avoids `conda activate` and instead places the conda
environment's `bin` directory at the front of `PATH`. This is more robust in
non-interactive Slurm shells.

Verify the environment:

```bash
python - <<'PY'
import pandas
import pyarrow
import rail
import tables_io
print("DP1 GAaP 1.0 estimate environment is importable")
PY

command -v rail-estimate
```

## 2. Create the run directory

Create an isolated run directory under `/scratch`:

```bash
source /scripts/$(whoami)/ondemand/env-dp1-gaap1p0-estimate.sh

export RUN_ID=dp1-stage2-fzboost-gaap1p0-matched-v4
export PZ_APOLLO_RUN=$PZ_RUN_ROOT/$RUN_ID

mkdir -p "$PZ_APOLLO_RUN/model" "$PZ_APOLLO_RUN/output" "$PZ_APOLLO_RUN/log"
cd "$PZ_APOLLO_RUN"
```

Copy or link the model pickle produced by
`dp1_stage1_train_instructions_matched_v4.md` into the run directory:

```bash
cp /path/to/model_dp1_v4_fzboost_gaap1p0_6band.pickle \
   "$PZ_APOLLO_RUN/model/"
```

Set the canonical paths used below:

```bash
export PZ_DP1_INPUT_DATASET=/data/cl/lsst/dp1/secondary/catalogs/skinny_collection/mag/gaap1p0/sfd/catalog/dataset
export PZ_MODEL=$PZ_APOLLO_RUN/model/model_dp1_v4_fzboost_gaap1p0_6band.pickle
export PZ_OUTPUT_DIR=$PZ_APOLLO_RUN/output
export PZ_LOG_DIR=$PZ_APOLLO_RUN/log
```

## 3. Inspect one input parquet

Select one parquet and validate its schema before submitting any jobs:

```bash
cd "$PZ_APOLLO_RUN"

find "$PZ_DP1_INPUT_DATASET" -type f -name '*.parquet' | sort | head -1 > first-input.txt

python - <<'PY'
from pathlib import Path

import numpy as np
import pandas as pd

path = Path("first-input.txt").read_text(encoding="utf-8").strip()
if not path:
    raise SystemExit("No input parquet found")

required = []
required += [f"{band}_gaap1p0Mag_dered" for band in "ugrizy"]
required += [f"{band}_gaap1p0MagErr_dered" for band in "ugrizy"]

df = pd.read_parquet(path)
missing = [col for col in required if col not in df.columns]
if missing:
    raise SystemExit(f"Missing required columns: {missing}")

print("input:", path)
print("shape:", df.shape)
print("columns:", list(df.columns))

for band in "ugrizy":
    mag = df[f"{band}_gaap1p0Mag_dered"].to_numpy()
    err = df[f"{band}_gaap1p0MagErr_dered"].to_numpy()
    sentinel = mag == 99.0
    print(
        band,
        "non-finite mag/error:",
        int((~np.isfinite(mag)).sum()),
        int((~np.isfinite(err)).sum()),
        "mag sentinel 99:",
        int(sentinel.sum()),
        "matching error sentinel 99:",
        int((err[sentinel] == 99.0).sum()),
    )
PY
```

`objectId`, `coord_ra`, and `coord_dec` are needed later to associate the
photo-z output with catalog objects, but `rail-estimate` itself consumes only
the 12 magnitude and magnitude-error columns.

## 4. Run a single-file smoke test

Direct parquet input may be exposed to RAIL as a `pyarrow.Table`, which can
fail inside `rail-estimate` because that code path expects a mapping-like
object. Convert each input parquet to a temporary HDF5 file before estimation.
The conversion also keeps the arrays writable so FlexZBoost can replace
`99.0` non-detections with limiting magnitudes.

Run a smoke test on the first 1,000 rows:

```bash
cd "$PZ_APOLLO_RUN"

export PZ_FIRST_INPUT=$(cat first-input.txt)
mkdir -p tmp

python - <<'PY'
import os
from pathlib import Path

import pandas as pd
import tables_io

inp = Path(os.environ["PZ_FIRST_INPUT"])
out = Path("tmp/smoke-test-input.hdf5")

cols = []
cols += [f"{band}_gaap1p0Mag_dered" for band in "ugrizy"]
cols += [f"{band}_gaap1p0MagErr_dered" for band in "ugrizy"]

df = pd.read_parquet(inp, columns=cols).head(1000).copy()
tables_io.write(df, str(out))

print("wrote:", out, df.shape)
PY

rail-estimate \
  tmp/smoke-test-input.hdf5 \
  "$PZ_OUTPUT_DIR/smoke-test.hdf5" \
  --algorithm=fzboost \
  --calibration-file="$PZ_MODEL" \
  --column-template='{band}_gaap1p0Mag_dered' \
  --column-template-error='{band}_gaap1p0MagErr_dered'
```

The `_dered` templates are intentional. The Stage 1 training columns contain
already-dereddened values without that suffix, whereas the target DP1 catalog
records the same photometric state using `_dered`. No additional
dereddening is performed here.

Validate the smoke-test output:

```bash
python - <<'PY'
import h5py
import numpy as np

path = "output/smoke-test.hdf5"
with h5py.File(path, "r") as handle:
    xvals = handle["meta/xvals"][:]
    yvals = handle["data/yvals"][:]
    print("meta/xvals:", xvals.shape, xvals.dtype)
    print("data/yvals:", yvals.shape, yvals.dtype)
    print("all PDF values finite:", bool(np.isfinite(yvals).all()))
    if yvals.shape != (1000, 301):
        raise SystemExit(f"Unexpected PDF shape: {yvals.shape}")
    if not np.isfinite(yvals).all():
        raise SystemExit("Non-finite values found in photo-z PDFs")
PY
```

With the Stage 1 model, the expected PDF grid has 301 bins from `z = 0.0` to
`z = 3.0`.

## 5. Build the parquet file list

Create one stable recursive file list and retain it with the run metadata:

```bash
cd "$PZ_APOLLO_RUN"

find "$PZ_DP1_INPUT_DATASET" -type f -name '*.parquet' | sort > input-parquet-files.txt

export PZ_NFILES=$(wc -l < input-parquet-files.txt)
if [ "$PZ_NFILES" -eq 0 ]; then
    echo "No parquet files found under $PZ_DP1_INPUT_DATASET" >&2
    exit 1
fi
echo "Number of parquet files: $PZ_NFILES"
```

## 6. Create the Slurm array script

Each array task processes one parquet, creates a temporary HDF5 input, and
writes one final HDF5 output. The output path preserves the input path relative
to the dataset root, replacing only the `.parquet` suffix with `.hdf5`.

```bash
cd "$PZ_APOLLO_RUN"

cat > run-one-dp1-gaap1p0-estimate.sh <<'EOF'
#!/usr/bin/env bash
#SBATCH --job-name=dp1-pz-gaap1p0
#SBATCH --partition=cpu
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=log/slurm-%A_%a.out
#SBATCH --error=log/slurm-%A_%a.err

set -euo pipefail

source /scripts/$(whoami)/ondemand/env-dp1-gaap1p0-estimate.sh

: "${PZ_DP1_INPUT_DATASET:?missing PZ_DP1_INPUT_DATASET}"
: "${PZ_MODEL:?missing PZ_MODEL}"
: "${PZ_OUTPUT_DIR:?missing PZ_OUTPUT_DIR}"
: "${PZ_FILE_LIST:?missing PZ_FILE_LIST}"

input_file=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$PZ_FILE_LIST")
if [ -z "$input_file" ]; then
    echo "No input file for SLURM_ARRAY_TASK_ID=$SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi
export input_file

relative_path="${input_file#$PZ_DP1_INPUT_DATASET/}"
if [ "$relative_path" = "$input_file" ]; then
    echo "Input is outside PZ_DP1_INPUT_DATASET: $input_file" >&2
    exit 1
fi

output_file="$PZ_OUTPUT_DIR/${relative_path%.parquet}.hdf5"
tmp_dir="${TMPDIR:-$PWD/tmp}/dp1-gaap1p0-estimate-${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID}"
tmp_input="$tmp_dir/input.hdf5"
export tmp_input

mkdir -p "$(dirname "$output_file")" "$tmp_dir"
cleanup() {
    rm -f -- "$tmp_input"
    rmdir -- "$tmp_dir" 2>/dev/null || true
}
trap cleanup EXIT

echo "SLURM_JOB_ID=$SLURM_JOB_ID"
echo "SLURM_ARRAY_TASK_ID=$SLURM_ARRAY_TASK_ID"
echo "input_file=$input_file"
echo "tmp_input=$tmp_input"
echo "output_file=$output_file"
echo "model=$PZ_MODEL"

python - <<'PY'
import os
from pathlib import Path

import pandas as pd
import tables_io

inp = Path(os.environ["input_file"])
out = Path(os.environ["tmp_input"])

cols = []
cols += [f"{band}_gaap1p0Mag_dered" for band in "ugrizy"]
cols += [f"{band}_gaap1p0MagErr_dered" for band in "ugrizy"]

df = pd.read_parquet(inp, columns=cols)
tables_io.write(df, str(out))

print("converted:", inp, "->", out, df.shape)
PY

rail-estimate \
  "$tmp_input" \
  "$output_file" \
  --algorithm=fzboost \
  --calibration-file="$PZ_MODEL" \
  --column-template='{band}_gaap1p0Mag_dered' \
  --column-template-error='{band}_gaap1p0MagErr_dered'
EOF

chmod +x run-one-dp1-gaap1p0-estimate.sh
bash -n run-one-dp1-gaap1p0-estimate.sh
```

## 7. Submit a pilot array job

Run a pilot on up to ten of the largest parquet files. Selecting large shards
makes the observed `MaxRSS` a useful basis for the production memory request
and concurrency cap.

```bash
cd "$PZ_APOLLO_RUN"

python - <<'PY'
from pathlib import Path

paths = [Path(line) for line in Path("input-parquet-files.txt").read_text(encoding="utf-8").splitlines() if line]
largest = sorted(paths, key=lambda path: path.stat().st_size, reverse=True)[:10]
Path("pilot-parquet-files.txt").write_text(
    "\n".join(map(str, largest)) + ("\n" if largest else ""),
    encoding="utf-8",
)
print("pilot files:", len(largest))
for path in largest:
    print(path.stat().st_size, path)
PY

mkdir -p "$PZ_APOLLO_RUN/output-pilot"

export PZ_FILE_LIST=$PZ_APOLLO_RUN/pilot-parquet-files.txt
export PZ_NFILES=$(wc -l < "$PZ_FILE_LIST")
export PZ_OUTPUT_DIR=$PZ_APOLLO_RUN/output-pilot
export PZ_MAX_CONCURRENT=10

sbatch \
  --array=0-$((PZ_NFILES - 1))%$PZ_MAX_CONCURRENT \
  --export=ALL,PZ_DP1_INPUT_DATASET="$PZ_DP1_INPUT_DATASET",PZ_MODEL="$PZ_MODEL",PZ_OUTPUT_DIR="$PZ_OUTPUT_DIR",PZ_FILE_LIST="$PZ_FILE_LIST" \
  run-one-dp1-gaap1p0-estimate.sh
```

Save the job ID printed by `sbatch`:

```bash
export PZ_ARRAY_JOB_ID=<jobid>
```

If Apollo requires an account for the allocation, add `--account=<account>` to
the `sbatch` command.

Monitor and inspect the pilot:

```bash
squeue -j "$PZ_ARRAY_JOB_ID"
sacct -j "$PZ_ARRAY_JOB_ID" --format=JobID%30,JobName%25,State,ExitCode,Elapsed,MaxRSS
find "$PZ_APOLLO_RUN/output-pilot" -type f -name '*.hdf5' | sort
grep -R "Traceback\|Error:\|CondaError\|Killed\|OOM\|out of memory" "$PZ_LOG_DIR" || true
```

All pilot array tasks must finish with state `COMPLETED` and exit code `0:0`.
Increase `--mem` in the array script if `MaxRSS` is too close to 16 GB or any
task is killed for exceeding memory. Reduce it only after the largest-shard
pilot demonstrates sufficient headroom.

Before production, restore the output directory:

```bash
export PZ_OUTPUT_DIR=$PZ_APOLLO_RUN/output
```

## 8. Submit the production array

Choose concurrency from the pilot's memory use and the currently available
Apollo capacity. The initial value below is deliberately conservative; adjust
it to local scheduling policy and filesystem load.

```bash
cd "$PZ_APOLLO_RUN"

export PZ_FILE_LIST=$PZ_APOLLO_RUN/input-parquet-files.txt
export PZ_NFILES=$(wc -l < "$PZ_FILE_LIST")
export PZ_MAX_CONCURRENT=100

sbatch \
  --array=0-$((PZ_NFILES - 1))%$PZ_MAX_CONCURRENT \
  --export=ALL,PZ_DP1_INPUT_DATASET="$PZ_DP1_INPUT_DATASET",PZ_MODEL="$PZ_MODEL",PZ_OUTPUT_DIR="$PZ_OUTPUT_DIR",PZ_FILE_LIST="$PZ_FILE_LIST" \
  run-one-dp1-gaap1p0-estimate.sh
```

Save the production job ID:

```bash
export PZ_ARRAY_JOB_ID=<jobid>
```

Do not increase concurrency solely from the CPU count. Each process holds the
input photometry and a 301-bin PDF array, so available memory and shared
filesystem performance are also limiting factors.

## 9. Resume missing outputs

After the production array finishes, generate a file list for inputs whose
corresponding output does not exist:

```bash
cd "$PZ_APOLLO_RUN"

python - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["PZ_DP1_INPUT_DATASET"])
out_root = Path(os.environ["PZ_OUTPUT_DIR"])

missing = []
for line in Path("input-parquet-files.txt").read_text(encoding="utf-8").splitlines():
    if not line:
        continue
    input_path = Path(line)
    relative = input_path.relative_to(root)
    output_path = out_root / relative.with_suffix(".hdf5")
    if not output_path.exists():
        missing.append(line)

Path("missing-parquet-files.txt").write_text(
    "\n".join(missing) + ("\n" if missing else ""),
    encoding="utf-8",
)
print("missing outputs:", len(missing))
PY
```

Resubmit only missing files when necessary:

```bash
export PZ_FILE_LIST=$PZ_APOLLO_RUN/missing-parquet-files.txt
export PZ_NFILES=$(wc -l < "$PZ_FILE_LIST")
export PZ_MAX_CONCURRENT=100

if [ "$PZ_NFILES" -gt 0 ]; then
  sbatch \
    --array=0-$((PZ_NFILES - 1))%$PZ_MAX_CONCURRENT \
    --export=ALL,PZ_DP1_INPUT_DATASET="$PZ_DP1_INPUT_DATASET",PZ_MODEL="$PZ_MODEL",PZ_OUTPUT_DIR="$PZ_OUTPUT_DIR",PZ_FILE_LIST="$PZ_FILE_LIST" \
    run-one-dp1-gaap1p0-estimate.sh
fi
```

This check detects absent files. Also inspect the Slurm status and sample the
HDF5 contents before treating all existing outputs as valid.

## 10. Inspect outputs

Summarize the production array status:

```bash
cd "$PZ_APOLLO_RUN"

: "${PZ_ARRAY_JOB_ID:?set PZ_ARRAY_JOB_ID to the production Slurm array job id}"

squeue -j "$PZ_ARRAY_JOB_ID" || true
sacct -j "$PZ_ARRAY_JOB_ID" --format=JobID%30,JobName%25,State,ExitCode,Elapsed,MaxRSS

sacct -j "$PZ_ARRAY_JOB_ID" --parsable2 --noheader \
  --format=JobID%30,State,ExitCode,Elapsed,MaxRSS |
awk -F'|' -v job="$PZ_ARRAY_JOB_ID" '
  $1 ~ "^" job "_[0-9]+$" {
    total += 1
    states[$2] += 1
    if ($2 != "COMPLETED" || $3 != "0:0") {
      bad += 1
      print "non-success array task:", $0 > "/dev/stderr"
    }
  }
  END {
    print "array tasks:", total
    for (state in states) {
      print state, states[state]
    }
    if (total == 0 || bad > 0) {
      exit 1
    }
  }
'
```

Count inputs and production outputs. The smoke test and pilot live outside the
production output tree counted here:

```bash
cd "$PZ_APOLLO_RUN"

echo "input parquets: $(wc -l < input-parquet-files.txt)"
echo "production output HDF5 files: $(find "$PZ_OUTPUT_DIR" -type f -name '*.hdf5' ! -name 'smoke-test.hdf5' | wc -l)"
```

Inspect a production input/output pair and verify that the number of PDF rows
matches the number of parquet rows:

```bash
cd "$PZ_APOLLO_RUN"

python - <<'PY'
import os
from pathlib import Path

import h5py
import pyarrow.parquet as pq

root = Path(os.environ["PZ_DP1_INPUT_DATASET"])
out_root = Path(os.environ["PZ_OUTPUT_DIR"])

input_path = Path(
    Path("input-parquet-files.txt").read_text(encoding="utf-8").splitlines()[0]
)
relative = input_path.relative_to(root)
output_path = out_root / relative.with_suffix(".hdf5")

input_rows = pq.ParquetFile(input_path).metadata.num_rows
with h5py.File(output_path, "r") as handle:
    x_shape = handle["meta/xvals"].shape
    y_shape = handle["data/yvals"].shape

print("input:", input_path)
print("output:", output_path)
print("input rows:", input_rows)
print("meta/xvals:", x_shape)
print("data/yvals:", y_shape)

if y_shape != (input_rows, 301):
    raise SystemExit(f"Input/output row or bin mismatch: {input_rows=} {y_shape=}")
PY
```

Check the logs for unresolved failures:

```bash
grep -R "Traceback\|Error:\|CondaError\|Killed\|OOM\|out of memory" "$PZ_LOG_DIR" || true
```

## 11. Expected outputs

The run directory should contain:

```text
$PZ_APOLLO_RUN/model/model_dp1_v4_fzboost_gaap1p0_6band.pickle
$PZ_APOLLO_RUN/input-parquet-files.txt
$PZ_APOLLO_RUN/run-one-dp1-gaap1p0-estimate.sh
$PZ_APOLLO_RUN/output/<same-relative-path-as-input>.hdf5
$PZ_APOLLO_RUN/log/slurm-*.out
$PZ_APOLLO_RUN/log/slurm-*.err
```

Each input parquet has exactly one output HDF5 at the same relative path below
the respective input and output roots:

```text
input:  $PZ_DP1_INPUT_DATASET/<subdirectories>/Npix=*.parquet
output: $PZ_OUTPUT_DIR/<subdirectories>/Npix=*.hdf5
```

The association with `objectId`, `coord_ra`, and `coord_dec` is positional:
row `i` in an input parquet corresponds to row `i` in `data/yvals` of its
matching HDF5 file. The temporary conversion must therefore preserve row order,
as the commands in this document do.

The estimation stage is successful when:

- the smoke test writes a `(1000, 301)` `data/yvals` dataset;
- every production Slurm array task completes with exit code `0:0`;
- the number of production HDF5 files matches the number of input parquets;
- sampled outputs have 301 redshift bins and the same row count as their input;
- the logs contain no unresolved tracebacks or repeated `rail-estimate` errors.
