# DP2 PSF FlexZBoost Stage 2: Clipped RTN-124 Model

This document describes how to run photo-z estimation on Apollo/LIneA after the
PSF-trained clipped RTN-124 FlexZBoost pickle has been generated.

The input dataset is the LSST DP2 primary Object catalog stored on Apollo as
individual parquet shards:

```text
/data/cl/lsst/dp2/primary/catalogs/object
```

The directory contains files such as:

```text
object_6309_lsst_cells_v2_LSSTCam_runs_DRP_DP2_v30_0_8_DM-55060_stage3_20260606T114559Z.parq
object_9974_lsst_cells_v2_LSSTCam_runs_DRP_DP2_v30_0_8_DM-55060_stage3_20260609T183945Z.parq
```

All parquet files are expected to have the same schema, including:

```text
u_psfFlux, g_psfFlux, r_psfFlux, i_psfFlux, z_psfFlux, y_psfFlux
u_psfFluxErr, g_psfFluxErr, r_psfFluxErr, i_psfFluxErr, z_psfFluxErr, y_psfFluxErr
ebv, coord_ra, coord_dec, objectId
```

During estimation, `rail-estimate` converts the nJy fluxes to AB magnitudes and
magnitude uncertainties, then applies the SFD correction from `ebv`. The
resulting in-memory columns are named `{band}_psfMag_sfd` and
`{band}_psfMagErr_sfd`.

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
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/primary/catalogs/object
export PZ_MODEL=$PZ_APOLLO_RUN/model/model_dp2_v3p1_fzboost_psf_clipped_rtn124.pickle
export PZ_OUTPUT_DIR=$PZ_APOLLO_RUN/output
export PZ_LOG_DIR=$PZ_APOLLO_RUN/log
```

## 3. Inspect one input parquet

Use one parquet file to validate the schema before submitting many jobs:

```bash
cd "$PZ_APOLLO_RUN"

find "$PZ_DP2_INPUT_DATASET" -name '*.parq' | sort | head -1 > first-input.txt

python - <<'PY'
import pyarrow.parquet as pq

path = open("first-input.txt", encoding="utf-8").read().strip()
schema = pq.read_schema(path)
print("input:", path)
print("columns:", len(schema.names))
print("rows:", pq.read_metadata(path).num_rows)

required = ["ebv", "objectId", "coord_ra", "coord_dec"]
required += [f"{band}_psfFlux" for band in "ugrizy"]
required += [f"{band}_psfFluxErr" for band in "ugrizy"]
missing = [column for column in required if column not in schema.names]
if missing:
    raise SystemExit(f"Missing required columns: {missing}")
print("required DP2 columns are present")
PY
```

## 4. Run a single-file smoke test

This verifies the model, flux-to-magnitude conversion, SFD correction, and
retained-column output before launching the full dataset. `rail-estimate` reads
only the required parquet columns, so the other Object-table fields are not
loaded into memory.

```bash
cd "$PZ_APOLLO_RUN"
export PZ_FIRST_INPUT=$(cat first-input.txt)

rail-estimate \
  "$PZ_FIRST_INPUT" \
  "$PZ_OUTPUT_DIR/smoke-test.hdf5" \
  --algorithm=fzboost \
  --calibration-file="$PZ_MODEL" \
  --sfd-deredden \
  --column-template='{band}_psfMag_sfd' \
  --column-template-error='{band}_psfMagErr_sfd' \
  --row-id-column=objectId \
  --output-columns=i_psfMagErr_sfd
```

Inspect the smoke-test output:

```bash
python - <<'PY'
import h5py

path = "output/smoke-test.hdf5"
with h5py.File(path, "r") as handle:
    for name in ("meta/xvals", "data/yvals", "ancillary/i_psfMagErr_sfd"):
        dataset = handle[name]
        print(name, dataset.shape, dataset.dtype)
    assert handle["data/yvals"].shape[0] == handle["ancillary/i_psfMagErr_sfd"].shape[0]
    integrity = handle["pz_compute"]
    assert bool(integrity.attrs["complete"])
    assert integrity.attrs["row_count"] == handle["data/yvals"].shape[0]
    assert integrity.attrs["row_id_column"] == "objectId"
    assert "row_id_fingerprint" in integrity.attrs
PY
```

The `ancillary/i_psfMagErr_sfd` dataset is carried into both final products by
`pz-build-hats` in stage 3.

## 5. Build the parquet file list

The input dataset contains many parquet shards. Create a stable file list
once and keep it with the run logs:

```bash
cd "$PZ_APOLLO_RUN"

find "$PZ_DP2_INPUT_DATASET" -name '*.parq' | sort > input-parquet-files.txt

export PZ_NFILES=$(wc -l < input-parquet-files.txt)
echo "Number of parquet files: $PZ_NFILES"
```

## 6. Create the Slurm array script

Create a small array-job runner. Each array task processes exactly one parquet
file and writes one HDF5 output. `rail-estimate` projects only the 12 PSF flux
fields plus `ebv` and `objectId`, creates the SFD columns once, and reuses them for inference
and optional output retention.

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
output_file="$PZ_OUTPUT_DIR/${relative_path%.parq}.hdf5"
mkdir -p "$(dirname "$output_file")"

if [ -f "$output_file" ]; then
    if python - "$output_file" <<'PY'
import h5py
import sys

with h5py.File(sys.argv[1], "r") as handle:
    rows = handle["data/yvals"].shape[0]
    marker = handle["pz_compute"].attrs
    valid = (
        bool(marker.get("complete", False))
        and int(marker.get("row_count", -1)) == rows
        and "row_id_fingerprint" in marker
        and "ancillary/i_psfMagErr_sfd" in handle
        and handle["ancillary/i_psfMagErr_sfd"].shape[0] == rows
    )
raise SystemExit(0 if valid else 1)
PY
    then
        echo "Complete output already exists: $output_file"
        exit 0
    fi
    backup="${output_file}.incomplete-${SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID}"
    mv "$output_file" "$backup"
    echo "Moved incomplete output to $backup"
fi

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
  --sfd-deredden \
  --column-template='{band}_psfMag_sfd' \
  --column-template-error='{band}_psfMagErr_sfd' \
  --row-id-column=objectId \
  --output-columns=i_psfMagErr_sfd
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
dispatcher because each array task reads its input parquet directly, writes a
final output path ending in `.hdf5`, and preserves the input relative path.
The historical `pz-compute` defaults are useful as a CPU-scale reference, but
the final concurrency must be capped by the current
Apollo `cpu` partition memory and by the observed per-task memory requirement.

## 9. Resume failed or missing outputs

After the array job finishes, build a retry list containing missing or incomplete outputs:

```bash
cd "$PZ_APOLLO_RUN"

python - <<'PY'
from pathlib import Path
import os

root = Path(os.environ["PZ_DP2_INPUT_DATASET"])
out_root = Path(os.environ["PZ_OUTPUT_DIR"])

invalid = []
for line in Path("input-parquet-files.txt").read_text(encoding="utf-8").splitlines():
    input_path = Path(line)
    relative = input_path.relative_to(root)
    output_path = out_root / relative.with_suffix(".hdf5")
    valid = False
    if output_path.exists():
        try:
            import h5py
            with h5py.File(output_path, "r") as handle:
                rows = handle["data/yvals"].shape[0]
                marker = handle["pz_compute"].attrs
                valid = (
                    bool(marker.get("complete", False))
                    and int(marker.get("row_count", -1)) == rows
                    and "row_id_fingerprint" in marker
                    and "ancillary/i_psfMagErr_sfd" in handle
                    and handle["ancillary/i_psfMagErr_sfd"].shape[0] == rows
                )
        except (KeyError, OSError):
            valid = False
    if not valid:
        invalid.append(line)

Path("retry-parquet-files.txt").write_text(
    "\n".join(invalid) + ("\n" if invalid else ""), encoding="utf-8"
)
print("missing or incomplete outputs:", len(invalid))
PY
```

If `missing or incomplete outputs` is greater than zero, resubmit only those files. The runner preserves any incomplete HDF5 with an `.incomplete-*` suffix before retrying:

```bash
export PZ_FILE_LIST=$PZ_APOLLO_RUN/retry-parquet-files.txt
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
echo "production output HDF5 files: $(find "$PZ_OUTPUT_DIR" -name '*.hdf5' | wc -l)"
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
$PZ_APOLLO_RUN/output/object_*.hdf5
$PZ_APOLLO_RUN/log/slurm-*.out
$PZ_APOLLO_RUN/log/slurm-*.err
```

These outputs can be passed to `pz-build-hats` with the original DP2 parquet
dataset as the input directory and the stage 2 HDF5 tree as the output
directory. `pz-build-hats` matches files by relative path, for example:

```text
input:  $PZ_DP2_INPUT_DATASET/object_6309_...parq
output: $PZ_OUTPUT_DIR/object_6309_...hdf5
```

The association with `objectId`, `coord_ra`, and `coord_dec` is positional:
row `i` in the input parquet is matched to row `i` in `data/yvals` from the
corresponding HDF5 output.

The estimation stage is successful when:

- the single-file smoke test writes `output/smoke-test.hdf5`;
- the full Slurm array finishes without failed tasks;
- the number of output HDF5 files matches the number of input parquet files;
- a sampled output contains `meta/xvals`, `data/yvals`, and `ancillary/i_psfMagErr_sfd`;
- logs do not contain unresolved tracebacks or repeated `rail-estimate` errors.
