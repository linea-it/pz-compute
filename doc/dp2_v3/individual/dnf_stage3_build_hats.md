# DP2 DNF Stage 3: build the HATS products

Load the shared Stage 3 environment and submit DNF only:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/scripts/submit-hats.sh dnf
```

After the driver completes, validate the DNF products:

```bash
doc/dp2_v3/scripts/validate-hats.py dnf
```

All DNF-attributable output remains under:

```text
$PZ_DP2_ROOT/dnf/stage3/
├── output/
│   ├── pz-dnf-gaap1p0-clipped-hats/
│   └── pz-dnf-gaap1p0-clipped-hats.pdf/
├── log/
│   ├── dask-*/
│   └── driver-*/
├── smoke/
└── benchmark/
```

The summary HATS catalog retains the common scalar statistics and
`i_gaap1p0Mag_sfd`; the companion PDF product retains the 601-bin vectors and
redshift grid. DNF-specific Stage 2 ancillary values remain in the estimator
HDF5 files and are not added to the common HATS schema by this workflow.
