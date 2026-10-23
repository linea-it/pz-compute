# DP2 BPZ Stage 3: build the HATS products

Load the shared Stage 3 environment, then submit BPZ only:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-hats.sh bpz
```

Use the [Stage 3 terminal commands](inspect_runs.md#stage-3-hats-build) with
`algorithm=bpz` to follow the driver, inspect Dask worker logs, check its exit
marker, and validate the final row counts and schemas.

After the driver completes, validate this product with:

```bash
doc/dp2_v3/scripts/validate-hats.py bpz
```

All BPZ-attributable output remains under:

```text
$PZ_DP2_ROOT/bpz/stage3/
├── output/
│   ├── pz-bpz-gaap1p0-clipped-hats/
│   └── pz-bpz-gaap1p0-clipped-hats.pdf/
├── log/
│   ├── dask-*/
│   └── driver-*/
├── smoke/
└── benchmark/
```

The BPZ scientific contract is documented in
[`bpz_science.md`](../references/bpz_science.md). No BPZ production-run note
exists yet; create one only after this workflow completes and is validated.
