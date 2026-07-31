# DP2 PSF FlexZBoost Stage 1: Clipped RTN-124 Training Set

This document describes how to generate a RAIL/FlexZBoost model pickle trained
with the clipped RTN-124 training set and DP2 PSF magnitudes. The resulting
model is intended for object catalogs that contain columns named
`{band}_psfMag_dered` and `{band}_psfMagErr_dered`.

The instructions are written to be portable. Run them from the root directory of
the `pz-compute` repository.

## 0. Prepare the working directory

Create a local working directory for all training inputs, intermediate files,
configuration files, and model outputs:

```bash
mkdir -p training-model
```

Choose the Python executable from an environment where `rail`, `tables_io`,
`pandas`, `pyarrow`, `flexcode`, and `xgboost` are installed:

```bash
export PZ_PY=/path/to/your/pz-compute-python
```

For example, if you use conda:

```bash
conda activate pz-compute-local
export PZ_PY="$(which python)"
```

Check the environment:

```bash
$PZ_PY - <<'PY'
for module in ["pandas", "pyarrow", "tables_io", "rail", "flexcode", "xgboost"]:
    __import__(module)
    print(module, "OK")
PY
```

## 1. Get the clipped training parquet

Use the LSST PZ Server product:

```text
CLIPPED_TRAIN RTN-124 (PARQUET)
https://pzserver.linea.org.br/product/415_clipped_train_rtn124_parquet
```

Download the parquet file and place it at:

```text
training-model/train_clipped_v3.parquet
```

The clipped training parquet is expected to contain at least:

```text
redshift
ebv
u_psfMag, g_psfMag, r_psfMag, i_psfMag, z_psfMag, y_psfMag
u_psfMagErr, g_psfMagErr, r_psfMagErr, i_psfMagErr, z_psfMagErr, y_psfMagErr
```

The production inference catalog uses dereddened PSF columns with names like
`u_psfMag_dered`. The clipped training file stores PSF magnitudes without the
`_dered` suffix and includes `ebv`, so the conversion step below creates
matching dereddened columns.

Run a quick validation:

```bash
$PZ_PY - <<'PY'
import numpy as np
import pandas as pd

path = "training-model/train_clipped_v3.parquet"
df = pd.read_parquet(path)

required = ["redshift", "ebv"]
required += [f"{band}_psfMag" for band in "ugrizy"]
required += [f"{band}_psfMagErr" for band in "ugrizy"]

missing = [col for col in required if col not in df.columns]
if missing:
    raise SystemExit(f"Missing required columns: {missing}")

print("shape:", df.shape)
print("redshift range:", df["redshift"].min(), df["redshift"].max())
print("ebv range:", df["ebv"].min(), df["ebv"].max())
print("rows with ebv > 1:", int((df["ebv"] > 1).sum()))

for band in "ugrizy":
    col = f"{band}_psfMag"
    valid = np.isfinite(df[col]) & (df[col] > -90) & (df[col] < 90)
    print(col, "valid fraction:", f"{valid.mean():.3f}")
PY
```

## 2. Convert the clipped training data to HDF5

`rail-train` can read parquet, but in this workflow parquet input may be exposed
as read-only arrays through PyArrow/tables_io. FlexZBoost modifies the input
arrays during training: it replaces non-detections with band magnitude limits
and sets the corresponding errors to `1.0`. With read-only parquet-backed
arrays, training can fail with:

```text
ValueError: assignment destination is read-only
```

For this reason, use HDF5 as the effective input format for training.

This conversion step:

- filters the redshift domain to match the model grid (`0 <= redshift <= 6`);
- keeps only the columns required by FlexZBoost;
- creates `{band}_psfMag_dered` from `{band}_psfMag - A_band * ebv`;
- creates `{band}_psfMagErr_dered` by copying `{band}_psfMagErr`;
- preserves `NaN` values as non-detections for the clipped training set.

```bash
$PZ_PY - <<'PY'
import numpy as np
import pandas as pd
import tables_io
from pathlib import Path

inp = Path("training-model/train_clipped_v3.parquet")
out_parquet = Path("training-model/train_clipped_v3_psf_dered_z0_6_fzboost.parquet")
out_hdf5 = Path("training-model/train_clipped_v3_psf_dered_z0_6_fzboost.hdf5")

a_ebv = {
    "u": 4.81,
    "g": 3.64,
    "r": 2.70,
    "i": 2.06,
    "z": 1.58,
    "y": 1.31,
}

cols = ["redshift", "ebv"]
cols += [f"{band}_psfMag" for band in "ugrizy"]
cols += [f"{band}_psfMagErr" for band in "ugrizy"]

raw = pd.read_parquet(inp, columns=cols)
raw = raw.loc[raw["redshift"].between(0.0, 6.0, inclusive="both")].copy()
raw = raw.loc[np.isfinite(raw["ebv"])].copy()

df = pd.DataFrame({"redshift": raw["redshift"].to_numpy()})

for band in "ugrizy":
    mag = raw[f"{band}_psfMag"]
    err = raw[f"{band}_psfMagErr"]
    df[f"{band}_psfMag_dered"] = mag - raw["ebv"] * a_ebv[band]
    df[f"{band}_psfMagErr_dered"] = err

df.to_parquet(out_parquet, index=False)
tables_io.write(df, str(out_hdf5))

print("wrote:", out_parquet, df.shape)
print("wrote:", out_hdf5, df.shape)
print("redshift min/max:", df["redshift"].min(), df["redshift"].max())

for band in "ugrizy":
    col = f"{band}_psfMag_dered"
    valid = np.isfinite(df[col]) & (df[col] > -90) & (df[col] < 90)
    print(col, "valid fraction:", f"{valid.mean():.3f}")
PY
```

The clipped parquet inspected during development had NaNs for missing PSF
magnitudes rather than a `99` sentinel. This is expected for this flow and is
handled by the clipped YAML configuration below.

## 3. Create the FlexZBoost configuration file

Create:

```text
training-model/fzboost_psf_clipped.yaml
```

with:

```bash
cat > training-model/fzboost_psf_clipped.yaml <<'YAML'
zmin: 0.0
zmax: 6.0
nzbins: 301
nondetect_val: .nan
redshift_col: redshift
retrain_full: true
trainfrac: 0.75
seed: 1138
bumpmin: 0.02
bumpmax: 0.35
nbump: 20
sharpmin: 0.7
sharpmax: 2.1
nsharp: 15
max_basis: 35
basis_system: cosine
regression_params:
  max_depth: 8
  objective: reg:squarederror
include_mag_err: false
YAML
```

Parameter rationale:

These settings are intentionally based on the existing DP2 GAaP baseline model
pickle, `model_dp2_v3p1_fzboost_baseline_gold.pickle`, while changing the
training photometry to the clipped RTN-124 DP2 PSF training set.

- `zmin: 0.0` and `zmax: 6.0`: define the redshift grid for the model. Use the
  same interval used by `model_dp2_v3p1_fzboost_baseline_gold.pickle` if the
  goal is a comparable replacement model.
- `nzbins: 301`: keeps the standard RAIL output grid resolution used by this
  repository.
- `nondetect_val: .nan`: matches the clipped training file, where missing PSF
  magnitudes are represented as `NaN`. FlexZBoost replaces these values with
  band magnitude limits during training.
- `redshift_col: redshift`: the clipped RTN-124 parquet stores redshift in the
  `redshift` column.
- `retrain_full: true`, `trainfrac: 0.75`, `bump*`, and `sharp*`: use the full
  FlexZBoost calibration procedure. The model first uses a validation split to
  select `bump_threshold` and `sharpen_alpha`, then retrains on the full dataset.
- `max_basis: 35`, `basis_system: cosine`, `max_depth: 8`, and
  `objective: reg:squarederror`: FlexZBoost baseline settings inherited from the
  `model_dp2_v3p1_fzboost_baseline_gold.pickle` training setup.
- `include_mag_err: false`: keeps the default feature construction. With this
  setting, FlexZBoost trains on 6 features: reference magnitude `i` plus colors
  `u-g`, `g-r`, `r-i`, `i-z`, and `z-y`.

## 4. Optional smoke test

Before running the full training job, run a small calibration to validate the
schema, YAML file, column templates, and HDF5 input path.

```bash
$PZ_PY - <<'PY'
import pandas as pd
import tables_io
from pathlib import Path

inp = Path("training-model/train_clipped_v3_psf_dered_z0_6_fzboost.parquet")
out = Path("training-model/train_clipped_v3_psf_dered_smoke_5000.hdf5")

df = pd.read_parquet(inp)
df = df.sample(n=5000, random_state=1138)
tables_io.write(df, str(out))

print("wrote:", out, df.shape)
PY

$PZ_PY rail_scripts/rail-train \
  training-model/train_clipped_v3_psf_dered_smoke_5000.hdf5 \
  training-model/estimator_fzboost_psf_clipped_smoke.pkl \
  --algorithm=fzboost \
  --column-template='{band}_psfMag_dered' \
  --column-template-error='{band}_psfMagErr_dered' \
  --param-file=training-model/fzboost_psf_clipped.yaml
```

If this command finishes with `Training done.`, the setup is functional.

## 5. Generate the final model pickle

Run:

```bash
$PZ_PY rail_scripts/rail-train \
  training-model/train_clipped_v3_psf_dered_z0_6_fzboost.hdf5 \
  training-model/model_dp2_v3p1_fzboost_psf_clipped_rtn124.pickle \
  --algorithm=fzboost \
  --column-template='{band}_psfMag_dered' \
  --column-template-error='{band}_psfMagErr_dered' \
  --param-file=training-model/fzboost_psf_clipped.yaml
```

### 5.1. Submit the training with Slurm

If the interactive machine is not appropriate for the full training run, submit
the same command as a single-node Slurm job. This uses one node from the `cpu`
queue, the `hpc-public` account, 49 CPU cores, and 112 GB of memory.

The job requests 49 CPUs, but the low-level BLAS/OpenMP thread counts are set to
`1`. FlexZBoost uses joblib/scikit-learn parallelism internally for the
multi-output regression, so allowing each worker to spawn many BLAS/OpenMP
threads can oversubscribe the node and make the training slower.

This was observed in practice on Apollo: with BLAS/OpenMP thread counts set to
the full `SLURM_CPUS_PER_TASK`, the job stayed much longer in the initial
`fit the model...` step than a local workstation run. After setting
`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and
`NUMEXPR_NUM_THREADS` to `1`, the same Slurm job reached
`finding best bump thresh...` quickly. If the job appears stuck in
`fit the model...`, check these thread limits before changing the scientific
configuration.

Create the batch script:

```bash
cat > training-model/train-fzboost-psf-clipped.sbatch <<'SBATCH'
#!/usr/bin/env bash
#SBATCH --job-name=dp2-fzboost-psf-clipped
#SBATCH --partition=cpu
#SBATCH --account=hpc-public
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=49
#SBATCH --mem=112G
#SBATCH --time=03:00:00
#SBATCH --output=training-model/train-fzboost-psf-clipped-%j.out
#SBATCH --error=training-model/train-fzboost-psf-clipped-%j.err

set -euo pipefail

cd "$SLURM_SUBMIT_DIR"

: "${PZ_PY:?Set PZ_PY to the Python executable with RAIL installed before sbatch}"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

"$PZ_PY" rail_scripts/rail-train \
  training-model/train_clipped_v3_psf_dered_z0_6_fzboost.hdf5 \
  training-model/model_dp2_v3p1_fzboost_psf_clipped_rtn124.pickle \
  --algorithm=fzboost \
  --column-template='{band}_psfMag_dered' \
  --column-template-error='{band}_psfMagErr_dered' \
  --param-file=training-model/fzboost_psf_clipped.yaml
SBATCH
```

Submit it from the repository root:

```bash
sbatch --export=ALL,PZ_PY="$PZ_PY" training-model/train-fzboost-psf-clipped.sbatch
```

Watch the job:

```bash
squeue -u "$(whoami)"
```

Inspect the logs after it starts or finishes:

```bash
ls -lh training-model/train-fzboost-psf-clipped-*.out training-model/train-fzboost-psf-clipped-*.err
tail -n 80 training-model/train-fzboost-psf-clipped-*.out
tail -n 80 training-model/train-fzboost-psf-clipped-*.err
```

This step can take a long time. FlexZBoost performs:

1. initial XGBoost/FlexCode fit;
2. grid search for the best `bump_threshold`;
3. grid search for the best `sharpen_alpha`;
4. final retraining with the full dataset;
5. model pickle writing.

The expected output is:

```text
training-model/model_dp2_v3p1_fzboost_psf_clipped_rtn124.pickle
```

## 6. Run inference with the new model

For a DP2 object-catalog parquet with dereddened PSF magnitudes:

```bash
$PZ_PY rail_scripts/rail-estimate \
  path/to/input_catalog.parquet \
  path/to/output_photoz.hdf5 \
  --algorithm=fzboost \
  --calibration-file=training-model/model_dp2_v3p1_fzboost_psf_clipped_rtn124.pickle \
  --column-template='{band}_psfMag_dered' \
  --column-template-error='{band}_psfMagErr_dered'
```

Use the same column templates at inference time that were used during training.
