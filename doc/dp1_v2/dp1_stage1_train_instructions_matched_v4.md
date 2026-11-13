# DP1 FlexZBoost Stage 1: reproduce the final six-band GAaP model

This stage reproduces the scientific configuration of the final DP1
FlexZBoost model from:

```text
/sdf/data/rubin/shared/pz/projects/dp1_v4/data/gold_dp1_6band/model_inform_fzboost.pkl
```

The authoritative training input is the 6,778-row
[`training_v4 match_ecdfs`](https://pzserver.linea.org.br/product/83_training_v4_match_ecdfs_sitcomtn154)
product described by [SITCOMTN-154](https://sitcomtn-154.lsst.io/). Its six
`{band}_gaap1p0Mag` columns are already dereddened despite lacking a suffix;
do not apply another extinction correction. The note explicitly orders the
[nJy-to-AB conversion and SFD dereddening before cross-matching and the
train/test split](https://github.com/lsst-sitcom/sitcomtn-154/blob/7dee28834ddee2dcd9ac841e05fdc7a15c94685a/body.tex#L28-L37),
and reports the resulting [6,778-object training
sample](https://github.com/lsst-sitcom/sitcomtn-154/blob/7dee28834ddee2dcd9ac841e05fdc7a15c94685a/body.tex#L158-L159).

Run the one-time [local setup](dp1_setup_local.md) or
[Apollo setup](dp1_setup_apollo.md) first. Stage 1 and Stage 2 must use the
same frozen environment.

## 0. Reproducibility scope and evidence

The public [`dp1_v4.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/6c179d1f69c9dde2ceeb6bcd2dcb8c9d0a48a916/dp1/dp1_v4.yaml)
selects `train_file_v4` and overrides FlexZBoost to 50 basis functions, 40 bump
grid points and 30 sharpening grid points. This is the optimized setup named
by the [final note](https://github.com/lsst-sitcom/sitcomtn-154/blob/7dee28834ddee2dcd9ac841e05fdc7a15c94685a/body.tex#L325-L327).
The resolved USDF config supplies
the GAaP columns, limits and remaining defaults. The final pickle independently
confirms the fitted state:

| Item | Final DP1 reference |
|---|---:|
| training rows recorded by every fitted tree | 6,778 |
| input features | 11 |
| basis system | `cosine` |
| maximum / retained bases | 50 / 36 |
| retained basis indices | `0..34, 40` |
| redshift interval | `[0.0, 3.0]` |
| XGBoost depth / rounds / learning rate | 8 / 100 / 0.3 |
| `bump_threshold` | 0.062307692307692314 |
| `sharpen_alpha` | 1.2310344827586208 |
| scikit-learn version stored in pickle | 1.6.1 |

The 11 effective inputs are interleaved as:

```text
i,
u-g, sqrt(u_err^2 + g_err^2),
g-r, sqrt(g_err^2 + r_err^2),
r-i, sqrt(r_err^2 + i_err^2),
i-z, sqrt(i_err^2 + z_err^2),
z-y, sqrt(z_err^2 + y_err^2)
```

This was the unconditional feature construction in the historical
[`rail_flexzboost` implementation](https://github.com/LSSTDESC/rail_flexzboost/blob/5363ec62d6a492e75e510a1ab140c4fd066398f8/src/rail/estimation/algos/flexzboost.py#L16-L41).
Modern releases make the errors optional, so this recipe explicitly sets
`include_mag_err: true` in both training and estimation.

Two provenance caveats are important:

- the PZ Server product `gold dp1_optimize` is an earlier model whose fitted
  trees contain 7,000 rows; do not use it as the final reference;
- the supplied `inform_dp1_6band_config.yml` contains pre-override defaults
  (`35/20/15`) and is byte-identical to the old `dp1_optimize` config. The
  pickle and `dp1_v4.yaml` agree on the effective final values `50/40/30` and
  therefore take precedence.

The goal is scientific/configuration compatibility, not byte-identical trees.

## 1. Load the environment and prepare the inputs

On Apollo:

```bash
source /scripts/$(whoami)/ondemand/env-dp1-gaap1p0.sh
```

Locally:

```bash
source /path/to/pz-dp1-work/software/env-dp1-gaap1p0.sh
```

Create the run directory:

```bash
export RUN_ID=dp1-stage1-fzboost-gaap1p0-matched-v4
export PZ_STAGE1_RUN=$PZ_RUN_ROOT/$RUN_ID
mkdir -p "$PZ_STAGE1_RUN/training-model/reference"
cd "$PZ_STAGE1_RUN"

"$PZ_PY" -m pip freeze > training-model/environment-freeze.txt
git -C "$PZ_COMPUTE_DIR" rev-parse HEAD > training-model/pz-compute-revision.txt
```

Download the PZ Server training product and place it at:

```text
training-model/dp1_matched_v4_train.hdf5
```

For Section 6, copy the trusted USDF reference to:

```text
training-model/reference/model_inform_fzboost.pkl
```

Checksums of the inspected artifacts are:

```text
bacd50771ccf2589c9910b6d45dcf95b768833a8f2767011879af26b88520439  dp1_matched_v4_train.hdf5
a9b11f298cb598a31016eaeefb12347007f4e00ac193d0cc5ae83ff5c7515814  model_inform_fzboost.pkl
```

Verify them after transfer:

```bash
sha256sum training-model/dp1_matched_v4_train.hdf5 \
  training-model/reference/model_inform_fzboost.pkl
```

## 2. Validate and copy the training columns

Do not filter, sort or sample the production input. In particular, retain the
125 objects above `z=3`; the reference trees show that all 6,778 rows were used.
Here `zmax` defines the FlexCode basis interval, not a row-selection cut.

Create a compact writable HDF5 file while preserving row order and values:

```bash
"$PZ_PY" - <<'PY'
from pathlib import Path

import numpy as np
import pandas as pd
import tables_io

inp = Path("training-model/dp1_matched_v4_train.hdf5")
out = Path("training-model/dp1_matched_v4_gaap1p0_fzboost.hdf5")
cols = ["redshift"]
cols += [f"{band}_gaap1p0Mag" for band in "ugrizy"]
cols += [f"{band}_gaap1p0MagErr" for band in "ugrizy"]

raw = tables_io.read(str(inp))
missing = [column for column in cols if column not in raw]
assert not missing, missing
df = pd.DataFrame({column: raw[column] for column in cols})

assert len(df) == 6_778
assert np.isclose(df.redshift.min(), 0.0)
assert np.isclose(df.redshift.max(), 4.705)
assert int((df.redshift > 3.0).sum()) == 125
assert np.isfinite(df.to_numpy()).all()
for band in "ugrizy":
    assert not np.any(df[f"{band}_gaap1p0Mag"].to_numpy() == 99.0)

tables_io.write(df, str(out))
print("wrote:", out, df.shape)
PY
```

## 3. Create the reference-compatible configuration

Create `training-model/fzboost_dp1_v4_6band_gold.yaml`:

```bash
cat > training-model/fzboost_dp1_v4_6band_gold.yaml <<'YAML'
zmin: 0.0
zmax: 3.0
nzbins: 301
nondetect_val: .nan
mag_limits:
  u_gaap1p0Mag: 26.4
  g_gaap1p0Mag: 27.8
  r_gaap1p0Mag: 27.1
  i_gaap1p0Mag: 26.7
  z_gaap1p0Mag: 25.8
  y_gaap1p0Mag: 24.6
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
  learning_rate: 0.3
  objective: reg:squarederror
include_mag_err: true
use_weights: false
YAML
```

The training catalog has no `NaN` magnitudes, so the limits do not alter these
6,778 rows. They remain part of the estimator contract for Stage 2.

## 4. Optional local smoke test

This validates installation and schema only; it is not a scientific comparison.

```bash
"$PZ_PY" - <<'PY'
import pandas as pd
import tables_io

raw = tables_io.read("training-model/dp1_matched_v4_gaap1p0_fzboost.hdf5")
df = pd.DataFrame(raw).sample(n=1000, random_state=1138)
tables_io.write(df, "training-model/dp1_matched_v4_smoke_1000.hdf5")
PY

"$PZ_PY" "$PZ_COMPUTE_DIR/rail_scripts/rail-train" \
  training-model/dp1_matched_v4_smoke_1000.hdf5 \
  training-model/fzboost_dp1_v4_smoke.pickle \
  --algorithm=fzboost \
  --bins=301 \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp1_v4_6band_gold.yaml
```

## 5. Train the production model

Train to an intermediate file:

```bash
"$PZ_PY" "$PZ_COMPUTE_DIR/rail_scripts/rail-train" \
  training-model/dp1_matched_v4_gaap1p0_fzboost.hdf5 \
  training-model/model_dp1_v4_fzboost_gaap1p0_6band.raw.pickle \
  --algorithm=fzboost \
  --bins=301 \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp1_v4_6band_gold.yaml
```

The historical reference is a bare `FlexCodeModel`. Normalize the current
RAIL output to that outer type without changing its fitted data:

```bash
"$PZ_PY" - <<'PY'
import pickle
from pathlib import Path

raw = Path("training-model/model_dp1_v4_fzboost_gaap1p0_6band.raw.pickle")
out = Path("training-model/model_dp1_v4_fzboost_gaap1p0_6band.pickle")
with raw.open("rb") as stream:
    model = pickle.load(stream)
if hasattr(model, "data") and model.__class__.__module__.startswith("rail."):
    model = model.data
assert model.__class__.__module__ == "flexcode.core"
assert model.__class__.__name__ == "FlexCodeModel"
with out.open("wb") as stream:
    pickle.dump(model, stream, protocol=pickle.HIGHEST_PROTOCOL)
print("wrote:", out)
PY
```

### 5.1. Apollo Slurm example

```bash
cat > training-model/train-fzboost-dp1-v4.sbatch <<'SBATCH'
#!/usr/bin/env bash
#SBATCH --job-name=dp1-v4-fzboost
#SBATCH --partition=cpu_photoz
#SBATCH --account=hpc-photoz
#SBATCH --exclude=apl[26-28]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=training-model/train-fzboost-dp1-v4-%j.out
#SBATCH --error=training-model/train-fzboost-dp1-v4-%j.err

set -euo pipefail
source /scripts/$(whoami)/ondemand/env-dp1-gaap1p0.sh
cd "$SLURM_SUBMIT_DIR"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

"$PZ_PY" "$PZ_COMPUTE_DIR/rail_scripts/rail-train" \
  training-model/dp1_matched_v4_gaap1p0_fzboost.hdf5 \
  training-model/model_dp1_v4_fzboost_gaap1p0_6band.raw.pickle \
  --algorithm=fzboost \
  --bins=301 \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp1_v4_6band_gold.yaml
SBATCH

mkdir -p "$PZ_STAGE1_RUN/benchmark/stage1"
PZ_STAGE1_JOB_ID=$(sbatch --parsable training-model/train-fzboost-dp1-v4.sbatch)
PZ_STAGE1_JOB_ID=${PZ_STAGE1_JOB_ID%%;*}
printf '%s\n' "$PZ_STAGE1_JOB_ID" > benchmark/stage1/job-id.txt
echo "Stage 1 job: $PZ_STAGE1_JOB_ID"
```

After completion, run the normalization cell above and optionally profile:

```bash
"$PZ_PY" "$PZ_COMPUTE_DIR/performance/slurm/slurm-profile" \
  --job-id-file=benchmark/stage1/job-id.txt \
  --expected-jobs=1 --concurrency-target=1 \
  --label=dp1-stage1-train \
  --output-dir=benchmark/stage1 --fail-on-unsuccessful
```

## 6. Validate the candidate against the reference

Pickles can execute code. Load only the trusted USDF reference and the locally
created candidate.

```bash
"$PZ_PY" - <<'PY'
import json
import pickle
from pathlib import Path

import numpy as np
import yaml

reference_path = Path("training-model/reference/model_inform_fzboost.pkl")
candidate_path = Path("training-model/model_dp1_v4_fzboost_gaap1p0_6band.pickle")
config = yaml.safe_load(Path(
    "training-model/fzboost_dp1_v4_6band_gold.yaml"
).read_text())

assert config["max_basis"] == 50
assert config["nbump"] == 40 and config["nsharp"] == 30
assert config["include_mag_err"] is True
assert config["retrain_full"] is True
assert config["zmin"] == 0.0 and config["zmax"] == 3.0

def load(path):
    with path.open("rb") as stream:
        obj = pickle.load(stream)
    if hasattr(obj, "data") and obj.__class__.__module__.startswith("rail."):
        return obj.data
    return obj

def root_cover(model):
    dump = model.model.models.estimators_[1].get_booster().get_dump(
        dump_format="json", with_stats=True
    )[0]
    return json.loads(dump)["cover"]

reference = load(reference_path)
candidate = load(candidate_path)

for label, model in (("reference", reference), ("candidate", candidate)):
    assert model.max_basis == 50
    assert model.basis_system == "cosine"
    assert model.z_min == 0.0 and model.z_max == 3.0
    assert model.model.models.n_features_in_ == 11
    assert len(model.model.models.estimators_) == 50
    assert np.isclose(root_cover(model), 6778.0)
    assert model.model.params["max_depth"] == 8
    assert model.model.params["objective"] == "reg:squarederror"
    print(label, "configuration-compatible")

np.testing.assert_array_equal(reference.best_basis, np.r_[0:35, 40])
assert np.isclose(reference.bump_threshold, 0.062307692307692314)
assert np.isclose(reference.sharpen_alpha, 1.2310344827586208)
print("reference fitted state matches the audited USDF model")
PY
```

The candidate's selected bases, bump and sharpening values can differ when
library versions alter the fitted trees or validation losses. Preserve
`environment-freeze.txt`, the config, checksum and logs with the model. Stage 2
must use the same environment and `include_mag_err: true`.
