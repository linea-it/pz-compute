# DP1 GAaP 1.0 FlexZBoost Stage 1: Matched v4 Training Set

This document describes how to generate a RAIL/FlexZBoost model pickle for the
DP1 six-band configuration. The model uses dereddened GAaP 1.0 magnitudes in
the six LSST bands (`ugrizy`).

The training set comes from the LSST PZ Server product
[training_v4 match_ecdfs SITCOMTN-154](https://pzserver.linea.org.br/product/83_training_v4_match_ecdfs_sitcomtn154),
distributed in HDF5 format.

Run all commands from the root directory of the `pz-compute` repository.

## 0. Prepare the working directory and environment

Create a local working directory for the input, intermediate data,
configuration, logs, and model:

```bash
mkdir -p training-model
```

Choose a Python executable from an environment where `rail`, `tables_io`,
`pandas`, `flexcode`, and `xgboost` are installed:

```bash
export PZ_PY=/path/to/your/pz-compute-python
```

For example, with the local conda environment:

```bash
conda activate pz-compute-local
export PZ_PY="$(which python)"
```

Check the environment:

```bash
$PZ_PY - <<'PY'
for module in ["pandas", "tables_io", "rail", "flexcode", "xgboost"]:
    __import__(module)
    print(module, "OK")
PY
```

## 1. Get and inspect the matched v4 training set

Download the HDF5 file from the PZ Server product linked above and place it at:

```text
training-model/dp1_matched_v4_train.hdf5
```

The columns used by this training are:

```text
redshift
u_gaap1p0Mag, g_gaap1p0Mag, r_gaap1p0Mag
i_gaap1p0Mag, z_gaap1p0Mag, y_gaap1p0Mag
u_gaap1p0MagErr, g_gaap1p0MagErr, r_gaap1p0MagErr
i_gaap1p0MagErr, z_gaap1p0MagErr, y_gaap1p0MagErr
```

Despite not having a `_dered` suffix, the GAaP 1.0 magnitudes in this training
set are already dereddened. Do not apply another extinction correction and do
not use the `ebv` column in the training features.

Validate the schema and values:

```bash
$PZ_PY - <<'PY'
from pathlib import Path

import numpy as np
import tables_io

path = Path("training-model/dp1_matched_v4_train.hdf5")
data = tables_io.read(str(path))

required = ["redshift"]
required += [f"{band}_gaap1p0Mag" for band in "ugrizy"]
required += [f"{band}_gaap1p0MagErr" for band in "ugrizy"]

missing = [col for col in required if col not in data]
if missing:
    raise SystemExit(f"Missing required columns: {missing}")

nrows = len(data["redshift"])
if any(len(data[col]) != nrows for col in required):
    raise SystemExit("Required columns do not all have the same row count")

print("rows:", nrows)
print("redshift range:", data["redshift"].min(), data["redshift"].max())

for band in "ugrizy":
    mag_col = f"{band}_gaap1p0Mag"
    err_col = f"{band}_gaap1p0MagErr"
    mag = np.asarray(data[mag_col])
    err = np.asarray(data[err_col])
    print(
        band,
        "finite mag/error:", int(np.isfinite(mag).sum()), int(np.isfinite(err).sum()),
        "mag sentinel 99:", int(np.count_nonzero(mag == 99.0)),
    )
PY
```

The inspected product has 6,778 rows, no non-finite values in the required
columns, and no `99` magnitude sentinels. Its redshift range is `0.0` to
`4.705`; Section 2 restricts it to the DP1 model grid.

## 2. Restrict the training set to the DP1 redshift grid

The DP1 six-band FlexZBoost configuration uses `zmin: 0.0` and `zmax: 3.0`.
Create a compact HDF5 input containing only the required columns and rows inside
that inclusive interval:

```bash
$PZ_PY - <<'PY'
from pathlib import Path

import numpy as np
import pandas as pd
import tables_io

inp = Path("training-model/dp1_matched_v4_train.hdf5")
out = Path("training-model/dp1_matched_v4_train_z0_3_fzboost.hdf5")

cols = ["redshift"]
cols += [f"{band}_gaap1p0Mag" for band in "ugrizy"]
cols += [f"{band}_gaap1p0MagErr" for band in "ugrizy"]

raw = tables_io.read(str(inp))
missing = [col for col in cols if col not in raw]
if missing:
    raise SystemExit(f"Missing required columns: {missing}")

df = pd.DataFrame({col: raw[col] for col in cols})
finite = np.isfinite(df).all(axis=1)
in_grid = df["redshift"].between(0.0, 3.0, inclusive="both")

print("input rows:", len(df))
print("rows with non-finite required values:", int((~finite).sum()))
print("rows outside redshift grid:", int((~in_grid).sum()))

df = df.loc[finite & in_grid].copy()
tables_io.write(df, str(out))

print("wrote:", out, df.shape)
print("redshift min/max:", df["redshift"].min(), df["redshift"].max())
PY
```

For the inspected file this keeps 6,653 rows and removes 125 rows above
`z = 3.0`. No dereddening or sentinel substitution is performed in this step.

## 3. Create the DP1 six-band FlexZBoost configuration

Create:

```text
training-model/fzboost_dp1_6band_gaap1p0.yaml
```

with:

```bash
cat > training-model/fzboost_dp1_6band_gaap1p0.yaml <<'YAML'
zmin: 0.0
zmax: 3.0
nzbins: 301
nondetect_val: 99.0
redshift_col: redshift
retrain_full: true
trainfrac: 0.75
seed: 1138
bumpmin: 0.02
bumpmax: 0.35
nbump: 40
sharpmin: 0.7
sharpmax: 2.1
nsharp: 30
max_basis: 50
basis_system: cosine
regression_params:
  max_depth: 8
  objective: reg:squarederror
include_mag_err: false
YAML
```

These values combine the standard FlexZBoost settings used by this repository
with the DP1 `dp1_6band` overrides sourced from
[`dp1_v4.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/main/dp1/dp1_v4.yaml):

- `max_basis: 50`, `nbump: 40`, and `nsharp: 30` are the DP1 six-band
  overrides.
- `zmin: 0.0`, `zmax: 3.0`, and `nzbins: 301` define the DP1 redshift grid.
- `nondetect_val: 99.0` matches the non-detection representation in DP1 object
  catalogs. The inspected matched training set contains no such sentinels, but
  retaining this setting makes the model configuration consistent with its
  intended catalog domain.
- `retrain_full: true` and `trainfrac: 0.75` reserve 25% of the data while
  selecting the bump and sharpening parameters, then retrain on all rows.
- `include_mag_err: false` means the model features are the reference
  `i`-band magnitude and five adjacent colors: `u-g`, `g-r`, `r-i`, `i-z`, and
  `z-y`. Magnitude-error columns must still be present because FlexZBoost uses
  them when replacing non-detections.

The command-line column templates in Sections 4 and 5 map the generic band
configuration to the GAaP 1.0 column names. They also map the standard limiting
magnitudes to those columns.

## 4. Optional smoke test

Use a small deterministic sample to validate the HDF5 layout, parameter file,
and column templates before the final run:

```bash
$PZ_PY - <<'PY'
from pathlib import Path

import pandas as pd
import tables_io

inp = Path("training-model/dp1_matched_v4_train_z0_3_fzboost.hdf5")
out = Path("training-model/dp1_matched_v4_train_smoke_1000.hdf5")

raw = tables_io.read(str(inp))
df = pd.DataFrame(raw)
df = df.sample(n=min(1000, len(df)), random_state=1138)
tables_io.write(df, str(out))

print("wrote:", out, df.shape)
PY

$PZ_PY rail_scripts/rail-train \
  training-model/dp1_matched_v4_train_smoke_1000.hdf5 \
  training-model/estimator_dp1_fzboost_gaap1p0_smoke.pkl \
  --algorithm=fzboost \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp1_6band_gaap1p0.yaml
```

The test is successful when the command finishes with `Training done.` and
creates the smoke-test pickle. This runs the full DP1 bump/sharpen grids on a
smaller input, so it is a functional check rather than an instant syntax check.

## 5. Generate the final model pickle

Run:

```bash
$PZ_PY rail_scripts/rail-train \
  training-model/dp1_matched_v4_train_z0_3_fzboost.hdf5 \
  training-model/model_dp1_v4_fzboost_gaap1p0_6band.pickle \
  --algorithm=fzboost \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp1_6band_gaap1p0.yaml
```

FlexZBoost will:

1. fit an initial XGBoost/FlexCode model on the training split;
2. search 40 candidate bump thresholds;
3. search 30 candidate sharpening values;
4. retrain on the complete filtered training set;
5. write the model pickle.

The expected output is:

```text
training-model/model_dp1_v4_fzboost_gaap1p0_6band.pickle
```

### 5.1. Optional Slurm submission

To run the same training as a single-node Slurm job on Apollo, create:

```bash
cat > training-model/train-dp1-fzboost-gaap1p0.sbatch <<'SBATCH'
#!/usr/bin/env bash
#SBATCH --job-name=dp1-fzboost-gaap1p0
#SBATCH --partition=cpu
#SBATCH --account=hpc-public
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=training-model/train-dp1-fzboost-gaap1p0-%j.out
#SBATCH --error=training-model/train-dp1-fzboost-gaap1p0-%j.err

set -euo pipefail

cd "$SLURM_SUBMIT_DIR"

: "${PZ_PY:?Set PZ_PY to the Python executable with RAIL installed before sbatch}"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

"$PZ_PY" rail_scripts/rail-train \
  training-model/dp1_matched_v4_train_z0_3_fzboost.hdf5 \
  training-model/model_dp1_v4_fzboost_gaap1p0_6band.pickle \
  --algorithm=fzboost \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp1_6band_gaap1p0.yaml
SBATCH
```

Submit from the repository root:

```bash
sbatch --export=ALL,PZ_PY="$PZ_PY" \
  training-model/train-dp1-fzboost-gaap1p0.sbatch
```

Watch the job and inspect its logs:

```bash
squeue -u "$(whoami)"
tail -n 80 training-model/train-dp1-fzboost-gaap1p0-*.out
tail -n 80 training-model/train-dp1-fzboost-gaap1p0-*.err
```

Keeping the low-level BLAS/OpenMP thread counts at `1` prevents each
parallel worker from creating another pool of threads and oversubscribing the
node.

## 6. Compatibility note for the target DP1 catalogs

A representative DP1 catalog parquet was inspected with 461,140 rows. It has
the expected dereddened columns named
`{band}_gaap1p0Mag_dered` and `{band}_gaap1p0MagErr_dered`, with no nulls in
those columns. Invalid magnitudes use the exact sentinel `99.0`; the matching
magnitude-error value is also `99.0` in every sentinel row.

The observed magnitude-sentinel fractions were approximately 23.2% (`u`),
10.5% (`g`), 11.4% (`r`), 37.7% (`i`), 12.5% (`z`), and 49.2% (`y`). This
confirms that `nondetect_val: 99.0` is appropriate for the intended catalog.

The difference in suffixes is intentional: the training magnitudes are already
dereddened but retain names without `_dered`, while the target catalog records
that state explicitly in its column names. The training command above must use
the training-set templates exactly as shown. Any later estimation command must
map the model to the target catalog's `_dered` templates; no photometric
dereddening should be repeated in either stage.
