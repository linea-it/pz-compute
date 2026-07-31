# DP2 PSF FlexZBoost Stage 2: Full Model

This document describes how to run photo-z estimation on Apollo/LIneA after the
PSF-trained FlexZBoost pickle has been generated.

The input dataset is the LSST DP2 Skinny Object Catalog with Magnitudes,
stored on Apollo as a partitioned parquet tree:

```text
/data/cl/lsst/dp2/secondary/catalogs/skinny_collection/mag/psf/sfd/catalog/dataset
```

The tree contains parquet files under nested directories such as:

```text
Norder=2/Dir=0/Npix=107.parquet
Norder=2/Dir=0/Npix=136.parquet
Norder=2/Dir=0/Npix=181.parquet
```

All parquet files are expected to have the same schema, including:

```text
u_psfMag_dered, g_psfMag_dered, r_psfMag_dered, i_psfMag_dered, z_psfMag_dered, y_psfMag_dered
u_psfMagErr_dered, g_psfMagErr_dered, r_psfMagErr_dered, i_psfMagErr_dered, z_psfMagErr_dered, y_psfMagErr_dered
coord_ra, coord_dec, objectId
```

## 0. Login

Access Apollo from a terminal or JupyterHub terminal:

```bash
ssh loginapl01
```

Load conda or miniconda if your shell does not already do it. The exact command
depends on your Apollo account configuration.

## 1. Prepare the Apollo environment

Use `/scripts` for source code, conda environments, package caches, and helper
scripts. Use `/scratch` for run directories, file lists, logs, and outputs.

```bash
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp2_psf

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

Install the basic packages used by the inspection commands:

```bash
conda install -y -c conda-forge pyarrow tables-io hdf5 h5py
```

Create script links under `/scripts/$(whoami)/bin`:

```bash
ln -sfn "$PZ_COMPUTE_DIR/rail_scripts/rail-estimate" "$SCRIPTS/bin/rail-estimate"
chmod +x "$SCRIPTS/bin/rail-estimate"
```

Create an environment loader:

```bash
cat > "$PZ_INSTALL_ROOT/env-dp2-psf-estimate.sh" <<'EOF'
export SCRIPTS=/scripts/$(whoami)
export SCRATCH=/scratch/users/$(whoami)
export PZ_INSTALL_ROOT=$SCRIPTS/ondemand
export PZ_SRC_DIR=$SCRIPTS
export PZ_COMPUTE_DIR=$PZ_SRC_DIR/pz-compute
export PZ_RUN_ROOT=$SCRATCH/pz-compute-runs
export PZ_CONDA_ENV=$PZ_INSTALL_ROOT/pz_compute_dp2_psf
export CONDA_PKGS_DIRS=$PZ_INSTALL_ROOT/conda_pkgs
export PIP_CACHE_DIR=$PZ_INSTALL_ROOT/pip_cache
export PATH=$SCRIPTS/bin:$PZ_COMPUTE_DIR/rail_scripts:$PATH
export PYTHONPATH=$PZ_COMPUTE_DIR/rail_scripts:${PYTHONPATH:-}
conda activate "$PZ_CONDA_ENV"
EOF

chmod +x "$PZ_INSTALL_ROOT/env-dp2-psf-estimate.sh"
source "$PZ_INSTALL_ROOT/env-dp2-psf-estimate.sh"
```

Check imports:

```bash
python - <<'PY'
import pyarrow
import rail
import tables_io
print("DP2 PSF estimate environment is importable")
PY
```

## 2. Create the run directory

Create an isolated run directory under `/scratch`:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-psf-estimate.sh

export RUN_ID=dp2-stage2-fzboost-psf
export PZ_APOLLO_RUN=$PZ_RUN_ROOT/$RUN_ID

mkdir -p "$PZ_APOLLO_RUN/model" "$PZ_APOLLO_RUN/output" "$PZ_APOLLO_RUN/log"
cd "$PZ_APOLLO_RUN"
```

Copy or link the model pickle produced by
`dp2_stage1_train_instructions_full.md` into the run directory:

```bash
cp /path/to/model_dp2_v3p1_fzboost_psf_baseline_gold.pickle \
   "$PZ_APOLLO_RUN/model/"
```

Set the canonical paths used by the commands below:

```bash
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/skinny_collection/mag/psf/sfd/catalog/dataset
export PZ_MODEL=$PZ_APOLLO_RUN/model/model_dp2_v3p1_fzboost_psf_baseline_gold.pickle
export PZ_OUTPUT_DIR=$PZ_APOLLO_RUN/output
export PZ_LOG_DIR=$PZ_APOLLO_RUN/log
```

## 3. Inspect one input parquet

Use one parquet file to validate the schema before submitting many jobs:

```bash
cd "$PZ_APOLLO_RUN"

find "$PZ_DP2_INPUT_DATASET" -name '*.parquet' | sort | head -1 > first-input.txt

python - <<'PY'
import os
import pandas as pd

path = open("first-input.txt", encoding="utf-8").read().strip()
print("input:", path)

df = pd.read_parquet(path)
print("shape:", df.shape)
print("columns:", list(df.columns))

required = []
required += [f"{band}_psfMag_dered" for band in "ugrizy"]
required += [f"{band}_psfMagErr_dered" for band in "ugrizy"]

missing = [col for col in required if col not in df.columns]
if missing:
    raise SystemExit(f"Missing required columns: {missing}")
PY
```

## 4. Run a single-file smoke test

This verifies that `rail-estimate`, the model pickle, and the PSF column
templates work together before launching the full dataset.

```bash
cd "$PZ_APOLLO_RUN"

export PZ_FIRST_INPUT=$(cat first-input.txt)

rail-estimate \
  "$PZ_FIRST_INPUT" \
  "$PZ_OUTPUT_DIR/smoke-test.hdf5" \
  --algorithm=fzboost \
  --calibration-file="$PZ_MODEL" \
  --column-template='{band}_psfMag_dered' \
  --column-template-error='{band}_psfMagErr_dered'
```

Inspect the smoke-test output:

```bash
python - <<'PY'
import h5py

path = "output/smoke-test.hdf5"
with h5py.File(path, "r") as handle:
    def show(name, obj):
        if hasattr(obj, "shape"):
            print(name, obj.shape, obj.dtype)
    handle.visititems(show)
PY
```

The output should contain datasets similar to:

```text
meta/xvals
data/yvals
```

## 5. Build the parquet file list

The input dataset is a recursive partitioned tree. Create a stable file list
once and keep it with the run logs:

```bash
cd "$PZ_APOLLO_RUN"

find "$PZ_DP2_INPUT_DATASET" -name '*.parquet' | sort > input-parquet-files.txt

export PZ_NFILES=$(wc -l < input-parquet-files.txt)
echo "Number of parquet files: $PZ_NFILES"
```

## 6. Create the Slurm array script

Create a small array-job runner. Each array task processes exactly one parquet
file and writes one HDF5 output file. The output path preserves the input
directory structure below the DP2 dataset root, replacing `.parquet` with
`.hdf5`.

```bash
cd "$PZ_APOLLO_RUN"

cat > run-one-dp2-psf-estimate.sh <<'EOF'
#!/usr/bin/env bash
#SBATCH --job-name=dp2-pz-psf
#SBATCH --partition=cpu
#SBATCH --mem-per-cpu=2140M
#SBATCH --time=12:00:00
#SBATCH --output=log/slurm-%A_%a.out
#SBATCH --error=log/slurm-%A_%a.err

set -euo pipefail

source /scripts/$(whoami)/ondemand/env-dp2-psf-estimate.sh

: "${PZ_DP2_INPUT_DATASET:?missing PZ_DP2_INPUT_DATASET}"
: "${PZ_MODEL:?missing PZ_MODEL}"
: "${PZ_OUTPUT_DIR:?missing PZ_OUTPUT_DIR}"
: "${PZ_FILE_LIST:?missing PZ_FILE_LIST}"

input_file=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$PZ_FILE_LIST")
if [ -z "$input_file" ]; then
    echo "No input file for SLURM_ARRAY_TASK_ID=$SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

relative_path="${input_file#$PZ_DP2_INPUT_DATASET/}"
output_file="$PZ_OUTPUT_DIR/${relative_path%.parquet}.hdf5"

mkdir -p "$(dirname "$output_file")"

echo "SLURM_JOB_ID=$SLURM_JOB_ID"
echo "SLURM_ARRAY_TASK_ID=$SLURM_ARRAY_TASK_ID"
echo "input_file=$input_file"
echo "output_file=$output_file"
echo "model=$PZ_MODEL"

rail-estimate \
  "$input_file" \
  "$output_file" \
  --algorithm=fzboost \
  --calibration-file="$PZ_MODEL" \
  --column-template='{band}_psfMag_dered' \
  --column-template-error='{band}_psfMagErr_dered'
EOF

chmod +x run-one-dp2-psf-estimate.sh
```

## 7. Submit a pilot array job

Before using the whole cluster, run a pilot job with only 10 parquet files. This
checks the Slurm array script, model loading, output layout, and logs without
starting the full catalog run.

Adjust `--account` if your allocation requires a Slurm account.

```bash
cd "$PZ_APOLLO_RUN"

head -10 input-parquet-files.txt > pilot-parquet-files.txt
mkdir -p "$PZ_APOLLO_RUN/output-pilot"

export PZ_FILE_LIST=$PZ_APOLLO_RUN/pilot-parquet-files.txt
export PZ_NFILES=$(wc -l < "$PZ_FILE_LIST")
export PZ_OUTPUT_DIR=$PZ_APOLLO_RUN/output-pilot
export PZ_MAX_CONCURRENT=10

sbatch \
  --array=0-$((PZ_NFILES - 1))%$PZ_MAX_CONCURRENT \
  --export=ALL,PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_MODEL="$PZ_MODEL",PZ_OUTPUT_DIR="$PZ_OUTPUT_DIR",PZ_FILE_LIST="$PZ_FILE_LIST" \
  run-one-dp2-psf-estimate.sh
```

If Apollo requires an account, include it in the `sbatch` command:

```bash
--account=<account>
```

Watch the job:

```bash
squeue -u "$(whoami)"
```

After the pilot finishes, inspect the pilot outputs:

```bash
find "$PZ_APOLLO_RUN/output-pilot" -name '*.hdf5' | sort
grep -R "Traceback\\|Error:" log || true
```

Before submitting production, reset `PZ_OUTPUT_DIR` to the production output
directory:

```bash
export PZ_OUTPUT_DIR=$PZ_APOLLO_RUN/output
```

## 8. Submit the full-cluster production job

For the final run over the complete DP2 catalog, scale the array concurrency to
fill Apollo in the same spirit as the historical large `pz-compute` runs.

The previous production defaults in this repository used:

```text
-N 26 -n 2032
```

for `fzboost` and similar single-process estimators. That corresponds to about
78 concurrent `rail-estimate` processes per node. If the current Apollo
allocation has 28 CPU nodes available, a conservative scaled target is:

```text
28 nodes * 78 slots per node = 2184 concurrent tasks
```

Use this as the first full-cluster target:

```bash
cd "$PZ_APOLLO_RUN"

export PZ_FILE_LIST=$PZ_APOLLO_RUN/input-parquet-files.txt
export PZ_NFILES=$(wc -l < "$PZ_FILE_LIST")
export PZ_MAX_CONCURRENT=2184

sbatch \
  --array=0-$((PZ_NFILES - 1))%$PZ_MAX_CONCURRENT \
  --export=ALL,PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_MODEL="$PZ_MODEL",PZ_OUTPUT_DIR="$PZ_OUTPUT_DIR",PZ_FILE_LIST="$PZ_FILE_LIST" \
  run-one-dp2-psf-estimate.sh
```

If the cluster is busy, or if the run shows memory pressure or filesystem
contention, reduce only the concurrency cap, for example:

```bash
export PZ_MAX_CONCURRENT=1000
```

If the run is stable and Apollo policy allows a higher active array limit, the
cap can be increased after confirming the current hardware and queue limits with
the operations team.

This document uses a Slurm array rather than the legacy `pz-compute.batch`
dispatcher because each array task writes an output path ending in `.hdf5` while
preserving the input `Norder=*/Dir=*/Npix=*` tree. The historical `pz-compute`
defaults are still used here to choose a full-cluster concurrency target.

## 9. Resume failed or missing outputs

After the array job finishes, build a list of missing outputs:

```bash
cd "$PZ_APOLLO_RUN"

python - <<'PY'
from pathlib import Path
import os

root = Path(os.environ["PZ_DP2_INPUT_DATASET"])
out_root = Path(os.environ["PZ_OUTPUT_DIR"])

missing = []
for line in Path("input-parquet-files.txt").read_text(encoding="utf-8").splitlines():
    input_path = Path(line)
    relative = input_path.relative_to(root)
    output_path = out_root / relative.with_suffix(".hdf5")
    if not output_path.exists():
        missing.append(line)

Path("missing-parquet-files.txt").write_text("\n".join(missing) + ("\n" if missing else ""), encoding="utf-8")
print("missing outputs:", len(missing))
PY
```

If `missing outputs` is greater than zero, resubmit only the missing files:

```bash
export PZ_FILE_LIST=$PZ_APOLLO_RUN/missing-parquet-files.txt
export PZ_NFILES=$(wc -l < "$PZ_FILE_LIST")
export PZ_MAX_CONCURRENT=2184

if [ "$PZ_NFILES" -gt 0 ]; then
  sbatch \
    --array=0-$((PZ_NFILES - 1))%$PZ_MAX_CONCURRENT \
    --export=ALL,PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_MODEL="$PZ_MODEL",PZ_OUTPUT_DIR="$PZ_OUTPUT_DIR",PZ_FILE_LIST="$PZ_FILE_LIST" \
    run-one-dp2-psf-estimate.sh
fi
```

## 10. Inspect outputs

Count output HDF5 files:

```bash
cd "$PZ_APOLLO_RUN"

echo "input parquets: $(wc -l < input-parquet-files.txt)"
echo "production output HDF5 files: $(find "$PZ_OUTPUT_DIR" -path '*/Norder=*/*.hdf5' | wc -l)"
```

Inspect one output file:

```bash
cd "$PZ_APOLLO_RUN"

find "$PZ_OUTPUT_DIR" -name '*.hdf5' | sort | head -1 > first-output.txt

python - <<'PY'
import h5py

path = open("first-output.txt", encoding="utf-8").read().strip()
print("output:", path)

with h5py.File(path, "r") as handle:
    def show(name, obj):
        if hasattr(obj, "shape"):
            print(name, obj.shape, obj.dtype)
    handle.visititems(show)
PY
```

Check recent failures:

```bash
cd "$PZ_APOLLO_RUN"

grep -R "Traceback\\|Error:" log || true
```

## 11. Expected outputs

The run directory should contain:

```text
$PZ_APOLLO_RUN/model/model_dp2_v3p1_fzboost_psf_baseline_gold.pickle
$PZ_APOLLO_RUN/input-parquet-files.txt
$PZ_APOLLO_RUN/run-one-dp2-psf-estimate.sh
$PZ_APOLLO_RUN/output/Norder=*/Dir=*/Npix=*.hdf5
$PZ_APOLLO_RUN/log/slurm-*.out
$PZ_APOLLO_RUN/log/slurm-*.err
```

The estimation stage is successful when:

- the single-file smoke test writes `output/smoke-test.hdf5`;
- the full Slurm array finishes without failed tasks;
- the number of output HDF5 files matches the number of input parquet files;
- a sampled output HDF5 contains `meta/xvals` and `data/yvals`;
- logs do not contain unresolved tracebacks or repeated `rail-estimate` errors.
