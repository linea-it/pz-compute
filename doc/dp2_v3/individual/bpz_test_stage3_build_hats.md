# DP2 BPZ test Stage 3: build standalone HATS products

> **TEST ONLY:** this creates an engineering HATS catalog, not an official DP2
> BPZ product.

Stage 3 requires every input shard to have a corresponding completed HDF5
below `bpz_test/stage2/output`. It does not inspect or consume `bpz/stage2`.

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-hats.sh bpz_test
```

After the driver and Dask workers complete, validate only the test product:

```bash
doc/dp2_v3/scripts/validate-hats.py bpz_test
```

All artifacts remain visibly separated:

```text
$PZ_DP2_ROOT/bpz_test/stage3/
├── output/
│   ├── pz-bpz_test-gaap1p0-clipped-hats/
│   └── pz-bpz_test-gaap1p0-clipped-hats.pdf/
├── log/{dask-*,driver-*}/
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Do not rename, copy, or publish this tree as `bpz`. Its scientific limitations
remain those documented in
[`bpz_test_science.md`](../references/bpz_test_science.md).
