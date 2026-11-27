# Prepare the shared Stage 1 training catalog

Complete the [Apollo setup](../dp2_setup_apollo.md), then load the shared Stage
1/Stage 2 environment:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
mkdir -p "$PZ_DP2_ROOT/common/training"
cd "$PZ_DP2_ROOT"
```

Download the PZ Server product
[`CLIPPED_TRAIN RTN-124 (PARQUET)`](https://pzserver.linea.org.br/product/415_clipped_train_rtn124_parquet)
to `common/training/train_clipped_v3.parquet`, then verify it:

```bash
printf '%s  %s\n' \
  0c645457352446bfe9288b2b0d1e85577166f5ca8318c78dfb350453c349e511 \
  common/training/train_clipped_v3.parquet | sha256sum --check
```

Create one HDF5 table containing the columns required by all official algorithms. The
conversion copies values without filtering, sorting, sampling, imputation, or
another extinction correction:

```bash
"$PZ_PY" - <<'PY'
from pathlib import Path

import numpy as np
import pandas as pd
import tables_io

source = Path("common/training/train_clipped_v3.parquet")
target = Path("common/training/train_clipped_v3_gaap1p0.hdf5")
bands = "ugrizy"
columns = ["redshift"]
columns += [f"{band}_gaap1p0Mag" for band in bands]
columns += [f"{band}_gaap1p0MagErr" for band in bands]

data = pd.read_parquet(source, columns=columns)
assert list(data.columns) == columns
assert len(data) == 554_676
assert not data["redshift"].isna().any()
assert np.isclose(data["redshift"].min(), 0.0010000000474974513)
assert np.isclose(data["redshift"].max(), 9.975)
assert int((data["redshift"] > 6.0).sum()) == 501

tables_io.write(data, str(target))
print("wrote:", target, data.shape)
PY

"$PZ_PY" -m pip freeze > common/training/environment-freeze.txt
```

The resulting shared artifact is:

```text
$PZ_DP2_ROOT/common/training/train_clipped_v3_gaap1p0.hdf5
```

It contains `redshift`, six already-dereddened GAaP 1.0 magnitudes, and six
magnitude errors in `ugrizy` order. Although the output grid ends at redshift
6, retain the 501 training rows above 6 to reproduce the FlexZBoost and DNF
reference inputs. BPZ with `output_hdfn: true` does not fit those rows, but
uses the same file to preserve the shared column contract.
