# Prepare the shared Stage 2 manifests

Complete the [Apollo setup](../dp2_setup_apollo.md), then load the shared Stage
1/Stage 2 environment and identify the DP2 Object catalog:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"
```

Create a stable, sorted full-catalog manifest and a pilot manifest containing
the five largest shards. The script searches recursively for the partitioned
`Norder=*/Dir=*/Npix=*.parquet` files:

```bash
doc/dp2_v3/scripts/prepare-estimation-manifests.sh all
```

The command writes:

```text
$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
```

Verify the manifests before submission:

```bash
wc -l "$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt"
wc -l "$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt"
head "$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt"
```

Both manifests are algorithm-neutral. An individual run selects one algorithm
only when invoking `smoke-estimates.sh` or `submit-estimates.sh`.
