# DP2 FlexZBoost Stage 1: reproduce the six-band GAaP model

This document reproduces the scientific training configuration of the
RAIL/FlexZBoost model
`model_dp2_v3p1_fzboost_dp2_6band_gold.pickle` from the clipped RTN-124
training catalog `train_clipped_v3.parquet`. It uses the six
`{band}_gaap1p0Mag` columns (`u`, `g`, `r`, `i`, `z`, and `y`). These
magnitudes are already dereddened even though their names do not have a
dereddening suffix. [RTN-124 documents](https://github.com/lsst/rtn-124/blob/2f6e3f4cc7381f6789cb33fb9746ac574a9be9e3/body.tex#L70-L78)
that the nJy-to-AB conversion and SFD dereddening happen before the catalog is
shuffled and split into the `dp2_v3p1` training and test sets. **Do not apply
another extinction correction.**

The source products are:

- [CLIPPED_TRAIN RTN-124 (PARQUET)](https://pzserver.linea.org.br/product/415_clipped_train_rtn124_parquet),
  containing `train_clipped_v3.parquet`;
- [FlexZBoost model DP2 gold 6 bands RTN-124](https://pzserver.linea.org.br/product/435_flexzboost_model_dp2_gold_6_bands_rtn124),
  containing the reference
  `model_dp2_v3p1_fzboost_dp2_6band_gold.pickle`.

Run the one-time [local setup](dp2_setup_local.md) or
[Apollo/LineA setup](dp2_setup_apollo.md) before starting. Both use the same
environment recipe and define `PZ_PY` and `PZ_COMPUTE_DIR` consistently. If
training locally and estimating on Apollo, the Stage 2 manifest comparison is
still mandatory: independently resolved environments must not be assumed to
contain identical versions.

## 0. Reproducibility scope

The recipe below follows the official `dp2_v3p1`, `dp2_6band`,
`lsst_gaap_1p0` configuration. The relevant upstream files should be cited by
their immutable revision:

- [`dp2_v3p1.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_v3p1.yaml):
  50 basis functions and fixed bump/sharpen values;
- [`dp2_catalogs.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_catalogs.yaml):
  GAaP column templates, band order, magnitude limits, `zmax`, and `nzbins`.

This choice also follows the [RTN-124 production
description](https://github.com/lsst/rtn-124/blob/2f6e3f4cc7381f6789cb33fb9746ac574a9be9e3/body.tex#L287-L303),
which identifies GAaP 1.0 and `dp2_v3p1.yaml` as the optimized DP2 setup.

Inspection of the reference pickle independently confirms the following
persisted state:

| Item | Reference value |
|---|---:|
| catalog tag | `lsst_gaap_1p0` |
| provenance | project `dp2_v3p1`, flavor `dp2_6band`, selection `gold` |
| number of input features | 6 |
| `max_basis` / retained bases | 50 / 50 |
| basis system | `cosine` |
| model redshift interval | `[0.0, 6.0]` |
| XGBoost `max_depth` | 8 |
| XGBoost objective | `reg:squarederror` |
| XGBoost learning rate / boosting rounds | 0.3 / 100 |
| final `bump_threshold` | 0.02 |
| final `sharpen_alpha` | 1.2 |
| XGBoost version embedded in the model | 3.2.0 |
| scikit-learn version stored in the pickle | 1.8.0 |

The pickle does not retain every informer option or a complete package lock.
The remaining options below are taken from the pinned official configuration
and the RAIL defaults used by that configuration. This procedure intentionally
does not require the historical XGBoost and scikit-learn versions: production
should use the current validated software environment. The important
operational requirement is that Stage 1 training and Stage 2 estimation use
the same environment. Section 6 checks configuration compatibility rather than
binary equality or numerically identical predictions.

As an additional data-lineage check, the first non-constant tree in the
reference model was traversed with the effective features reconstructed from
this parquet. After replacing missing magnitudes with the six limits below,
the row counts agree at every tree node. The root contains exactly 554,676
objects. Leaving the values as `NaN` produces disagreements at 452 nodes. This
is direct evidence for both the full-row input and the non-detection transform.

## 1. Load the common environment and prepare the inputs

Load the Stage 1/Stage 2 environment created by the appropriate setup guide.
On Apollo:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
```

For a local installation, replace the loader path with the absolute path
created in `dp2_setup_local.md`:

```bash
source /path/to/pz-dp2-work/software/env-dp2-gaap1p0.sh
```

Create the Stage 1 run under the common run root. On Apollo this resolves below
`/scratch`; locally it resolves below the root selected in the local setup:

```bash
export RUN_ID=dp2-stage1-fzboost-gaap1p0-clipped
export PZ_STAGE1_RUN=$PZ_RUN_ROOT/$RUN_ID

mkdir -p "$PZ_STAGE1_RUN/training-model/reference"
cd "$PZ_STAGE1_RUN"
```

Check and record the environment before training. The versions are not pinned
to those found in the reference pickle; save this manifest and use the same
environment during Stage 2 estimation:

```bash
$PZ_PY - <<'PY'
from importlib.metadata import PackageNotFoundError, version

packages = [
    "pz-rail",
    "pz-rail-base",
    "pz-rail-flexzboost",
    "flexcode",
    "xgboost",
    "scikit-learn",
    "numpy",
    "pandas",
    "pyarrow",
    "tables-io",
]

for package in packages:
    try:
        print(f"{package}=={version(package)}")
    except PackageNotFoundError:
        raise SystemExit(f"Missing package: {package}")
PY

$PZ_PY -m pip freeze > training-model/environment-freeze.txt
```

Download the parquet from the PZ Server and place it at:

```text
training-model/train_clipped_v3.parquet
```

Optionally download the reference pickle for the comparison in Section 6 and
place it at:

```text
training-model/reference/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle
```

The artifacts inspected while preparing this recipe had these checksums:

```text
0c645457352446bfe9288b2b0d1e85577166f5ca8318c78dfb350453c349e511  train_clipped_v3.parquet
33e0fcfa29c10c4305e6de1c739a4765cc1291110d08d8c23674af8de6d8b127  model_dp2_v3p1_fzboost_dp2_6band_gold.pickle
```

Verify the downloaded input:

```bash
sha256sum training-model/train_clipped_v3.parquet
```

## 2. Validate and convert the training catalog

The reference model was fitted with all 554,676 rows, consistent with the
[RTN-124 training-count
table](https://github.com/lsst/rtn-124/blob/2f6e3f4cc7381f6789cb33fb9746ac574a9be9e3/body.tex#L410-L423).
In particular, do not filter the 501 objects with `redshift > 6`: the model's
`zmax: 6.0` defines the FlexCode basis interval but the reference training run
did not use it as a row selection. Row order must also remain unchanged.

The effective training features are the `i` magnitude and five adjacent
colors, following the [RAIL FlexZBoost feature
construction](https://github.com/LSSTDESC/rail_flexzboost/blob/19d5078910cd4d9bfa5cd4da6943c0e90f266647/src/rail/estimation/algos/flexzboost.py#L19-L44):

```text
i, u-g, g-r, r-i, i-z, z-y
```

RAIL replaces a missing magnitude with the band-specific limiting magnitude
before constructing these features. The exact limits are:

```text
u=26.5, g=27.8, r=27.1, i=26.7, z=25.8, y=24.6
```

Use HDF5 for training because FlexZBoost changes its in-memory input arrays
while replacing non-detections. Some parquet-backed arrays are read-only and
can otherwise fail with `ValueError: assignment destination is read-only`.

The conversion below copies the already-dereddened GAaP magnitudes and their
errors without changing values, filtering rows, sorting, or sampling:

```bash
$PZ_PY - <<'PY'
from pathlib import Path

import numpy as np
import pandas as pd
import tables_io

inp = Path("training-model/train_clipped_v3.parquet")
out = Path("training-model/train_clipped_v3_gaap1p0_fzboost.hdf5")

bands = "ugrizy"
cols = ["redshift"]
cols += [f"{band}_gaap1p0Mag" for band in bands]
cols += [f"{band}_gaap1p0MagErr" for band in bands]

df = pd.read_parquet(inp, columns=cols)

assert len(df) == 554_676, len(df)
assert list(df.columns) == cols
assert not df["redshift"].isna().any()
assert np.isclose(df["redshift"].min(), 0.0010000000474974513)
assert np.isclose(df["redshift"].max(), 9.975)
assert int((df["redshift"] > 6.0).sum()) == 501

expected_missing = {
    "u": 130_609,
    "g": 41_932,
    "r": 20_539,
    "i": 745,
    "z": 24_034,
    "y": 78_789,
}
for band, expected in expected_missing.items():
    column = f"{band}_gaap1p0Mag"
    actual = int(df[column].isna().sum())
    assert actual == expected, (column, actual, expected)

tables_io.write(df, str(out))
print("wrote:", out, df.shape)
PY
```

If the checksum in Section 1 does not match, treat failures in the exact row or
missing-value assertions as a dataset-version mismatch; do not simply delete
the assertions.

## 3. Create the reference-compatible FlexZBoost configuration

Create `training-model/fzboost_dp2_v3p1_6band_gold.yaml`:

```bash
cat > training-model/fzboost_dp2_v3p1_6band_gold.yaml <<'YAML'
zmin: 0.0
zmax: 6.0
nzbins: 601
nondetect_val: .nan
mag_limits:
  u_gaap1p0Mag: 26.5
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
bumpmax: 0.02
nbump: 1
sharpmin: 1.2
sharpmax: 1.2
nsharp: 1
max_basis: 50
basis_system: cosine
regression_params:
  max_depth: 8
  learning_rate: 0.3
  verbosity: 1
  objective: reg:squarederror
include_mag_err: false
use_weights: false
YAML
```

Important details:

- `nondetect_val: .nan` is required because the parquet represents missing
  GAaP magnitudes as `NaN`. This causes RAIL to substitute the six official
  GAaP magnitude limits before forming colors.
- `nbump: 1` and `nsharp: 1` reproduce the fixed production values; this is not
  a 20-by-15 hyperparameter search.
- `max_basis: 50` matches both the production configuration and the reference
  pickle.
- `learning_rate: 0.3` and `verbosity: 1` are FlexCode defaults that are
  persisted in the reference model; spelling them out avoids an implicit
  dependency on defaults.
- `include_mag_err: false` gives six features. Magnitude-error columns are
  still present because the RAIL non-detection handling updates the matching
  error when it replaces a missing magnitude.

## 4. Optional smoke test

The smoke test validates the installation and schema only. Its model must not
be compared scientifically with the full reference model.

```bash
$PZ_PY - <<'PY'
from pathlib import Path

import pandas as pd
import tables_io

inp = Path("training-model/train_clipped_v3.parquet")
out = Path("training-model/train_clipped_v3_gaap1p0_smoke_5000.hdf5")
cols = ["redshift"]
cols += [f"{band}_gaap1p0Mag" for band in "ugrizy"]
cols += [f"{band}_gaap1p0MagErr" for band in "ugrizy"]

df = pd.read_parquet(inp, columns=cols).sample(n=5000, random_state=1138)
tables_io.write(df, str(out))
print("wrote:", out, df.shape)
PY

$PZ_PY "$PZ_COMPUTE_DIR/rail_scripts/rail-train" \
  training-model/train_clipped_v3_gaap1p0_smoke_5000.hdf5 \
  training-model/fzboost_dp2_v3p1_6band_gold_smoke.pickle \
  --algorithm=fzboost \
  --bins=601 \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp2_v3p1_6band_gold.yaml
```

The setup is functional if the command finishes with `Training done.`

## 5. Train and wrap the production model

First write the trained FlexCode object to an intermediate pickle:

```bash
$PZ_PY "$PZ_COMPUTE_DIR/rail_scripts/rail-train" \
  training-model/train_clipped_v3_gaap1p0_fzboost.hdf5 \
  training-model/model_dp2_v3p1_fzboost_dp2_6band_gold.raw.pickle \
  --algorithm=fzboost \
  --bins=601 \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp2_v3p1_6band_gold.yaml
```

The PZ Server reference is a `rail.core.model.Model` wrapper, not a bare
`flexcode.core.FlexCodeModel`. Add the same scientific metadata and write the
final artifact:

```bash
$PZ_PY - <<'PY'
import pickle
from pathlib import Path

from rail.core.model import Model

raw_path = Path(
    "training-model/model_dp2_v3p1_fzboost_dp2_6band_gold.raw.pickle"
)
out_path = Path(
    "training-model/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle"
)

with raw_path.open("rb") as stream:
    data = pickle.load(stream)
if isinstance(data, Model):
    data = data.data

model = Model(
    data=data,
    creation_class_name=(
        "rail.estimation.algos.flexzboost.FlexZBoostInformer"
    ),
    version=0,
    catalog_tag="lsst_gaap_1p0",
    provenance={
        "project": "dp2_v3p1",
        "flavor": "dp2_6band",
        "selection": "gold",
    },
)
model.write(str(out_path))
print("wrote:", out_path)
PY
```

### 5.1. Slurm example

On the LineA HPC infrastructure, submit the training command as one process on
one HPE ProLiant XL220n node in `apl[17-25]` of the `cpu_photoz` partition with
the `hpc-photoz` account; `apl[26-28]` remain reserved for internal pipelines
and Jupyter. Slurm reports 104 effective logical CPUs,
`RealMemory=253132 MiB`, and `MemSpecLimit=4096 MiB` on these nodes. The memory
available to jobs is therefore 249036 MiB. Reserve approximately 95% of each
effective resource, respecting the allocation granularity:

```text
CPU target: 0.95 * 104 = 98.8 logical CPUs
CR_CORE_MEMORY allocation uses complete 2-thread cores, so request 98 CPUs

memory available to jobs: 253132 MiB - 4096 MiB = 249036 MiB
memory target: 0.95 * 249036 MiB = 236584.2 MiB
231 GiB = 236544 MiB = 94.98% of the available memory
```

Requesting 99 CPUs would cause Slurm to allocate 100 because the cluster uses
`SelectTypeParameters=CR_CORE_MEMORY` and each physical core has two threads.
The 98-CPU request is the closest supported allocation that does not exceed
the 95% target.

XGBoost is parallelized by `MultiOutputRegressor`; keep BLAS/OpenMP at one
thread per worker to avoid nested oversubscription.

Create `training-model/train-fzboost-dp2-v3p1.sbatch`:

```bash
cat > training-model/train-fzboost-dp2-v3p1.sbatch <<'SBATCH'
#!/usr/bin/env bash
#SBATCH --job-name=dp2-v3p1-fzboost
#SBATCH --partition=cpu_photoz
#SBATCH --account=hpc-photoz
#SBATCH --nodelist=apl[17-25]
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=98
#SBATCH --mem=231G
#SBATCH --time=03:00:00
#SBATCH --output=training-model/train-fzboost-dp2-v3p1-%j.out
#SBATCH --error=training-model/train-fzboost-dp2-v3p1-%j.err

set -euo pipefail
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
cd "$SLURM_SUBMIT_DIR"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

"$PZ_PY" "$PZ_COMPUTE_DIR/rail_scripts/rail-train" \
  training-model/train_clipped_v3_gaap1p0_fzboost.hdf5 \
  training-model/model_dp2_v3p1_fzboost_dp2_6band_gold.raw.pickle \
  --algorithm=fzboost \
  --bins=601 \
  --column-template='{band}_gaap1p0Mag' \
  --column-template-error='{band}_gaap1p0MagErr' \
  --param-file=training-model/fzboost_dp2_v3p1_6band_gold.yaml
SBATCH

PZ_STAGE1_JOB_ID=$(sbatch --parsable \
  training-model/train-fzboost-dp2-v3p1.sbatch)
export PZ_STAGE1_JOB_ID=${PZ_STAGE1_JOB_ID%%;*}
mkdir -p "$PZ_STAGE1_RUN/benchmark/stage1"
printf '%s\n' "$PZ_STAGE1_JOB_ID" > \
  "$PZ_STAGE1_RUN/benchmark/stage1/job-id.txt"
echo "Stage 1 Slurm job: $PZ_STAGE1_JOB_ID"
```

After the job finishes, create the lightweight Slurm benchmark artifacts
described in [Slurm performance profiling](../slurm_profile.md):

```bash
"$PZ_PY" "$PZ_COMPUTE_DIR/performance/slurm/slurm-profile" \
  --job-id-file "$PZ_STAGE1_RUN/benchmark/stage1/job-id.txt" \
  --expected-jobs 1 \
  --concurrency-target 1 \
  --label dp2-stage1-train \
  --output-dir "$PZ_STAGE1_RUN/benchmark/stage1" \
  --fail-on-unsuccessful
```

This writes `summary.log`, `summary.json`, `sacct.tsv`, `tasks.tsv`,
`time-profile.tsv`, and `time-profile.svg` without reading the training data or
the model pickle. Then run the wrapping cell above on the login node.

## 6. Validate configuration compatibility

Python pickle files can execute code while loading. Run this comparison only
with the trusted reference downloaded from the PZ Server and the file produced
locally.

The comparison is deliberately not byte-for-byte and does not require equal
predictions across library versions. It checks all options in the training YAML
and the compatible state that is persisted in both model pickles. Options such
as `trainfrac`, `seed`, `nzbins`, and the magnitude limits are not stored in the
pickle, which is why the YAML is audited separately.

```bash
$PZ_PY - <<'PY'
import pickle
from pathlib import Path

import numpy as np
import yaml
from rail.core.model import Model

reference_path = Path(
    "training-model/reference/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle"
)
candidate_path = Path(
    "training-model/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle"
)
config_path = Path("training-model/fzboost_dp2_v3p1_6band_gold.yaml")

with config_path.open() as stream:
    config = yaml.safe_load(stream)

assert np.isnan(config.pop("nondetect_val"))
assert config == {
    "zmin": 0.0,
    "zmax": 6.0,
    "nzbins": 601,
    "mag_limits": {
        "u_gaap1p0Mag": 26.5,
        "g_gaap1p0Mag": 27.8,
        "r_gaap1p0Mag": 27.1,
        "i_gaap1p0Mag": 26.7,
        "z_gaap1p0Mag": 25.8,
        "y_gaap1p0Mag": 24.6,
    },
    "redshift_col": "redshift",
    "retrain_full": True,
    "trainfrac": 0.75,
    "seed": 1138,
    "bumpmin": 0.02,
    "bumpmax": 0.02,
    "nbump": 1,
    "sharpmin": 1.2,
    "sharpmax": 1.2,
    "nsharp": 1,
    "max_basis": 50,
    "basis_system": "cosine",
    "regression_params": {
        "max_depth": 8,
        "learning_rate": 0.3,
        "verbosity": 1,
        "objective": "reg:squarederror",
    },
    "include_mag_err": False,
    "use_weights": False,
}
print("training YAML: compatible")

def load(path):
    with path.open("rb") as stream:
        obj = pickle.load(stream)
    assert isinstance(obj, Model), (path, type(obj))
    return obj

reference = load(reference_path)
candidate = load(candidate_path)

expected_class = "rail.estimation.algos.flexzboost.FlexZBoostInformer"
expected_provenance = {
    "project": "dp2_v3p1",
    "flavor": "dp2_6band",
    "selection": "gold",
}

def validate_model(label, wrapped):
    assert wrapped.creation_class_name == expected_class
    assert wrapped.version == 0
    assert wrapped.catalog_tag == "lsst_gaap_1p0"
    assert wrapped.provenance == expected_provenance

    model = wrapped.data
    assert model.max_basis == 50
    assert model.basis_system == "cosine"
    assert model.z_min == 0.0
    assert model.z_max == 6.0
    np.testing.assert_array_equal(model.best_basis, np.arange(50))
    assert np.isclose(model.bump_threshold, 0.02)
    assert np.isclose(model.sharpen_alpha, 1.2)

    expected_regression = {
        "max_depth": 8,
        "learning_rate": 0.3,
        "verbosity": 1,
        "objective": "reg:squarederror",
    }
    for key, value in expected_regression.items():
        assert model.model.params[key] == value, (label, key)

    regressors = model.model.models.estimators_
    assert model.model.models.n_features_in_ == 6
    assert len(regressors) == 50
    for regressor in regressors:
        params = regressor.get_params()
        for key, value in expected_regression.items():
            assert params[key] == value, (label, key)

    print(f"{label}: compatible")

validate_model("reference pickle", reference)
validate_model("new pickle", candidate)
PY
```

The expected result is three `compatible` messages. Differences in fitted tree
bytes or predictions are allowed when the production libraries differ from the
historical environment. Preserve `environment-freeze.txt` with the model and
verify the same package set before running Stage 2.
