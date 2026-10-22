# DP2 FlexZBoost Stage 3: build the HATS products

Load the shared Stage 3 environment, then submit FlexZBoost only:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-hats.sh fzboost
```

Use the [Stage 3 terminal commands](inspect_runs.md#stage-3-hats-build) with
`algorithm=fzboost` to follow the driver, inspect Dask worker logs, check its
exit marker, and validate the final row counts and schemas.

After the driver completes, validate this product with:

```bash
doc/dp2_v3/scripts/validate-hats.py fzboost
```

All FlexZBoost-attributable output remains under:

```text
$PZ_DP2_ROOT/fzboost/stage3/
├── output/
│   ├── pz-fzboost-gaap1p0-clipped-hats/
│   └── pz-fzboost-gaap1p0-clipped-hats.pdf/
├── log/
│   ├── dask-*/
│   └── driver-*/
├── smoke/
└── benchmark/
```

Technical history and the evidence required to certify a new production run
are documented in [`fzboost_runs.md`](../references/fzboost_runs.md).
