# DP2 PSF FlexZBoost Stage 2: Clipped RTN-124 Model

This document describes how to run photo-z estimation on Apollo/LIneA after the
PSF-trained clipped RTN-124 FlexZBoost pickle has been generated.

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
export PATH=$PZ_CONDA_ENV/bin:$SCRIPTS/bin:$PZ_COMPUTE_DIR/rail_scripts:$PATH
export PYTHONPATH=$PZ_COMPUTE_DIR/rail_scripts:${PYTHONPATH:-}
EOF

chmod +x "$PZ_INSTALL_ROOT/env-dp2-psf-estimate.sh"
source "$PZ_INSTALL_ROOT/env-dp2-psf-estimate.sh"
```

The environment loader intentionally avoids `conda activate` and instead puts
the conda environment's `bin` directory at the front of `PATH`. This is more
robust for Slurm batch jobs, where non-interactive shells may fail with:

```text
CondaError: Run 'conda init' before 'conda activate'
```

Verify that the loader does not contain `conda activate`:

```bash
if grep -n "conda activate" "$PZ_INSTALL_ROOT/env-dp2-psf-estimate.sh"; then
    echo "ERROR: remove conda activate from env-dp2-psf-estimate.sh"
    exit 1
fi
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

export RUN_ID=dp2-stage2-fzboost-psf-clipped
export PZ_APOLLO_RUN=$PZ_RUN_ROOT/$RUN_ID

mkdir -p "$PZ_APOLLO_RUN/model" "$PZ_APOLLO_RUN/output" "$PZ_APOLLO_RUN/log"
cd "$PZ_APOLLO_RUN"
```

Copy or link the model pickle produced by
`dp2_stage1_train_instructions_clipped.md` into the run directory:

```bash
cp /path/to/model_dp2_v3p1_fzboost_psf_clipped_rtn124.pickle \
   "$PZ_APOLLO_RUN/model/"
```

Set the canonical paths used by the commands below:

```bash
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/skinny_collection/mag/psf/sfd/catalog/dataset
export PZ_MODEL=$PZ_APOLLO_RUN/model/model_dp2_v3p1_fzboost_psf_clipped_rtn124.pickle
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

In this Apollo environment, direct parquet input can be exposed to RAIL as a
`pyarrow.Table`, which may fail inside `rail-estimate` with:

```text
AttributeError: 'pyarrow.lib.Table' object has no attribute 'items'
```

For that reason, convert each parquet input to a temporary HDF5 file before
calling `rail-estimate`.

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
cols += [f"{band}_psfMag_dered" for band in "ugrizy"]
cols += [f"{band}_psfMagErr_dered" for band in "ugrizy"]

df = pd.read_parquet(inp, columns=cols)
tables_io.write(df, str(out))

print("wrote:", out, df.shape)
PY

rail-estimate \
  tmp/smoke-test-input.hdf5 \
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
file, converts it to a temporary HDF5 input, and writes one final HDF5 output
file. The output path preserves the input directory structure below the DP2
dataset root, replacing `.parquet` with `.hdf5`.

```bash
cd "$PZ_APOLLO_RUN"

cat > run-one-dp2-psf-estimate.sh <<'EOF'
#!/usr/bin/env bash
#SBATCH --job-name=dp2-pz-psf
#SBATCH --partition=cpu
#SBATCH --mem=16G
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
export input_file

relative_path="${input_file#$PZ_DP2_INPUT_DATASET/}"
output_file="$PZ_OUTPUT_DIR/${relative_path%.parquet}.hdf5"
tmp_dir="${TMPDIR:-$PWD/tmp}/dp2-psf-estimate-${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID}"
tmp_input="$tmp_dir/input.hdf5"
export tmp_input

mkdir -p "$(dirname "$output_file")"
mkdir -p "$tmp_dir"
trap 'rm -rf "$tmp_dir"' EXIT

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
cols += [f"{band}_psfMag_dered" for band in "ugrizy"]
cols += [f"{band}_psfMagErr_dered" for band in "ugrizy"]

df = pd.read_parquet(inp, columns=cols)
tables_io.write(df, str(out))

print("converted:", inp, "->", out, df.shape)
PY

rail-estimate \
  "$tmp_input" \
  "$output_file" \
  --algorithm=fzboost \
  --calibration-file="$PZ_MODEL" \
  --column-template='{band}_psfMag_dered' \
  --column-template-error='{band}_psfMagErr_dered'
EOF

chmod +x run-one-dp2-psf-estimate.sh
bash -n run-one-dp2-psf-estimate.sh
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

Save the job id printed by `sbatch`:

```bash
export PZ_ARRAY_JOB_ID=<jobid>
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
sacct -j "$PZ_ARRAY_JOB_ID" --format=JobID%30,JobName%25,State,ExitCode,Elapsed,MaxRSS
find "$PZ_APOLLO_RUN/output-pilot" -name '*.hdf5' | sort
grep -R "Traceback\\|Error:\\|CondaError\\|Killed\\|OOM\\|out of memory" log || true
```

Before submitting production, reset `PZ_OUTPUT_DIR` to the production output
directory:

```bash
export PZ_OUTPUT_DIR=$PZ_APOLLO_RUN/output
```

## 8. Submit the full-cluster production job

For the final run over the complete DP2 catalog, scale the array concurrency
using three inputs:

- the historical large `pz-compute` defaults documented in this repository;
- the current Apollo partition layout documented by LIneA;
- the observed memory requirement from the pilot run.

The previous production defaults in this repository used:

```text
-N 26 -n 2032
```

for `fzboost` and similar single-process estimators. That corresponds to about
78 concurrent `rail-estimate` processes per node.

The current Apollo documentation states that the cluster has 28 compute nodes,
but the standard `cpu` partition exposes 25 nodes, `apl[01-25]`; `apl26`,
`apl27`, and `apl28` are reserved for Jupyter notebooks and other LIneA platform
pipelines. The `cpu` partition includes:

- 16 nodes `apl[01-16]` with 128 GB RAM each;
- 9 nodes `apl[17-25]` with 256 GB RAM each.

In this DP2 PSF parquet-to-HDF5 workflow, a pilot task processing a large shard
failed with the default 2140 MiB memory request and completed with `--mem=8G`.
A full-catalog run later showed that some larger shards can still exceed 8 GB,
so use `--mem=16G` for the production array unless a newer pilot over the
largest shards shows that a smaller request is enough. The memory-limited
capacity of the `cpu` partition with 16 GB per task is approximately:

```text
16 nodes * (128 GB / 16 GB) = 128 tasks
 9 nodes * (256 GB / 16 GB) = 144 tasks
total theoretical memory capacity = 272 concurrent tasks
```

Use a conservative first full-cluster target below the theoretical limit:

```bash
cd "$PZ_APOLLO_RUN"

export PZ_FILE_LIST=$PZ_APOLLO_RUN/input-parquet-files.txt
export PZ_NFILES=$(wc -l < "$PZ_FILE_LIST")
export PZ_MAX_CONCURRENT=200

sbatch \
  --array=0-$((PZ_NFILES - 1))%$PZ_MAX_CONCURRENT \
  --export=ALL,PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_MODEL="$PZ_MODEL",PZ_OUTPUT_DIR="$PZ_OUTPUT_DIR",PZ_FILE_LIST="$PZ_FILE_LIST" \
  run-one-dp2-psf-estimate.sh
```

Save the job id printed by `sbatch`:

```bash
export PZ_ARRAY_JOB_ID=<jobid>
```

If the cluster is busy, or if the run shows memory pressure or filesystem
contention, reduce only the concurrency cap, for example:

```bash
export PZ_MAX_CONCURRENT=100
```

If the run is stable and Apollo policy allows a higher active array limit, the
cap can be increased toward `250`, still staying below the approximate
memory-limited capacity of `272`.

This document uses a Slurm array rather than the legacy `pz-compute.batch`
dispatcher because each array task converts its input parquet to temporary HDF5,
writes a final output path ending in `.hdf5`, and preserves the input
`Norder=*/Dir=*/Npix=*` tree. The historical `pz-compute` defaults are useful as
a CPU-scale reference, but the final concurrency must be capped by the current
Apollo `cpu` partition memory and by the observed per-task memory requirement.

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
export PZ_MAX_CONCURRENT=200

if [ "$PZ_NFILES" -gt 0 ]; then
  sbatch \
    --array=0-$((PZ_NFILES - 1))%$PZ_MAX_CONCURRENT \
    --export=ALL,PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET",PZ_MODEL="$PZ_MODEL",PZ_OUTPUT_DIR="$PZ_OUTPUT_DIR",PZ_FILE_LIST="$PZ_FILE_LIST" \
    run-one-dp2-psf-estimate.sh
fi
```

## 10. Inspect outputs

While the job is still running, summarize the active array state without
treating `RUNNING` or `PENDING` tasks as failures:

```bash
cd "$PZ_APOLLO_RUN"

: "${PZ_ARRAY_JOB_ID:?set PZ_ARRAY_JOB_ID to the Slurm array job id}"

squeue -j "$PZ_ARRAY_JOB_ID" || true
sacct -j "$PZ_ARRAY_JOB_ID" --format=JobID%30,JobName%25,State,ExitCode,Elapsed,MaxRSS

sacct -j "$PZ_ARRAY_JOB_ID" --parsable2 --noheader \
  --format=JobID%30,State,ExitCode,Elapsed,MaxRSS |
awk -F'|' -v job="$PZ_ARRAY_JOB_ID" '
  $1 ~ "^" job "_[0-9]+$" {
    total += 1
    states[$2] += 1
    if ($2 !~ /^(COMPLETED|RUNNING|PENDING)$/) {
      failed += 1
      print "failed or terminal non-success array task:", $0 > "/dev/stderr"
    }
  }
  END {
    print "array tasks seen by sacct:", total
    for (state in states) {
      print state, states[state]
    }
    if (failed > 0) {
      exit 1
    }
  }
'
```

Check that every Slurm array task completed successfully. For an array job
`181552`, this checks task records such as `181552_0` through
`181552_<number of input files - 1>`:

```bash
cd "$PZ_APOLLO_RUN"

: "${PZ_ARRAY_JOB_ID:?set PZ_ARRAY_JOB_ID to the Slurm array job id}"

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

Summarize the total elapsed time for the array. `wall-clock elapsed` is the
real time from the first task start to the last task end; `sum task elapsed` is
the accumulated runtime across all array tasks:

```bash
cd "$PZ_APOLLO_RUN"

: "${PZ_ARRAY_JOB_ID:?set PZ_ARRAY_JOB_ID to the Slurm array job id}"

sacct -j "$PZ_ARRAY_JOB_ID" --parsable2 --noheader \
  --format=JobID%30,State,ExitCode,Start,End,ElapsedRaw \
  > array-sacct-timing.txt

python - <<'PY'
from datetime import datetime
import os
from pathlib import Path

job = os.environ["PZ_ARRAY_JOB_ID"]
starts = []
ends = []
sum_elapsed = 0
tasks = 0

for line in Path("array-sacct-timing.txt").read_text(encoding="utf-8").splitlines():
    if not line:
        continue
    parts = line.rstrip("\n").split("|")
    if len(parts) != 6:
        continue
    jobid, state, exit_code, start, end, elapsed_raw = parts
    if not jobid.startswith(f"{job}_") or "." in jobid:
        continue
    suffix = jobid.rsplit("_", 1)[-1]
    if not suffix.isdigit():
        continue
    if state != "COMPLETED" or exit_code != "0:0":
        continue
    if start in ("Unknown", "None") or end in ("Unknown", "None"):
        continue
    starts.append(datetime.fromisoformat(start))
    ends.append(datetime.fromisoformat(end))
    sum_elapsed += int(elapsed_raw)
    tasks += 1

if tasks == 0:
    raise SystemExit("No completed array tasks found in sacct output")

wall = int((max(ends) - min(starts)).total_seconds())
print("completed array tasks:", tasks)
print("first task start:", min(starts).isoformat(sep=" "))
print("last task end:", max(ends).isoformat(sep=" "))
print("wall-clock elapsed seconds:", wall)
print("sum task elapsed seconds:", sum_elapsed)
PY
```

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

grep -R "Traceback\\|Error:\\|CondaError\\|Killed\\|OOM\\|out of memory" log || true
```

## 11. Expected outputs

The run directory should contain:

```text
$PZ_APOLLO_RUN/model/model_dp2_v3p1_fzboost_psf_clipped_rtn124.pickle
$PZ_APOLLO_RUN/input-parquet-files.txt
$PZ_APOLLO_RUN/run-one-dp2-psf-estimate.sh
$PZ_APOLLO_RUN/output/Norder=*/Dir=*/Npix=*.hdf5
$PZ_APOLLO_RUN/log/slurm-*.out
$PZ_APOLLO_RUN/log/slurm-*.err
```

These outputs can be passed to `pz-build-hats` with the original DP2 parquet
dataset as the input directory and the stage 2 HDF5 tree as the output
directory. `pz-build-hats` matches files by relative path, for example:

```text
input:  $PZ_DP2_INPUT_DATASET/Norder=3/Dir=0/Npix=448.parquet
output: $PZ_OUTPUT_DIR/Norder=3/Dir=0/Npix=448.hdf5
```

The association with `objectId`, `coord_ra`, and `coord_dec` is positional:
row `i` in the input parquet is matched to row `i` in `data/yvals` from the
corresponding HDF5 output.

The estimation stage is successful when:

- the single-file smoke test writes `output/smoke-test.hdf5`;
- the full Slurm array finishes without failed tasks;
- the number of output HDF5 files matches the number of input parquet files;
- a sampled output HDF5 contains `meta/xvals` and `data/yvals`;
- logs do not contain unresolved tracebacks or repeated `rail-estimate` errors.
