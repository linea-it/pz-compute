# DP2 custom DNF cModel `griz` and `riz`

This project produces two full-DP2 DNF products with SFD-corrected cModel
photometry: one model and estimate using `griz`, and another using `riz`. It is
a custom science delivery and is not part of the official six-band GAaP 1.0
DP2 reproduction.

The reviewed choices are recorded in
[`science_contract.md`](science_contract.md). Do not infer scientific choices
from launcher defaults when the contract is more specific.
The implementation boundary and backward-compatibility plan are recorded in
[`technical_design.md`](technical_design.md).

## Status

The scientific request is defined. Generic band selection, copy-on-write-safe
DNF non-detection handling, allow-listed `DNF_ZN` propagation, and Rubin-style
scalar HATS summaries have local smoke coverage. The reviewed no-photometry
policy preserves every row and writes `NaN` to all nine science fields when
no selected band is usable, without adding a flag column. Stage 1 has
project-specific preparation, launchers, provenance wrappers, validation, and
accepted Apollo resources. Stage 2 has smoke, pilot and production launchers
plus source-aware validation; its production defaults are fixed from
successful five-shard Apollo pilots. Stage 3 has independent scalar-only
launchers, opt-in trapezoidal summaries with continuous CDF inversion,
complete schema and value validation, PDF-product rejection, and publication
records. Stage 3 resource measurements remain to be collected from its first
Apollo build.

The complete local Stage 1 rehearsal trained and validated both 554,676-row
models from the prepared tables. This confirms the four-feature `griz` and
three-feature `riz` model contracts; it does not replace the Apollo job and
resource-profile evidence.

A local Stage 2 rehearsal with real Object photometry also validated both
variants, including cModel SFD materialization, ANF estimation, normalized
601-bin PDFs, row identity, and exact `DNF_ZN` propagation.

Earlier local Stage 3 rehearsals produced two 11-column HATS collections under
the superseded contract; the approved product now has 12 columns including
`dnf_z_best`. Those earlier collections passed full scalar scans, interval
ordering, Stage 2/HATS `DNF_ZN` aggregate
comparison, and the no-PDF contract. Those artifacts must be rebuilt for the
approved schema before publication.

## Execution guides

1. [`stage1_train.md`](stage1_train.md): prepare the two cModel training
   projections and train independent `griz` and `riz` models.
2. [`stage2_estimate.md`](stage2_estimate.md): smoke-test, pilot, and estimate
   the complete DP2 Object catalog with each model.
3. [`stage3_build_hats.md`](stage3_build_hats.md): build scalar-only HATS
   products containing the Rubin-style summaries and `DNF_ZN`.

The measured resource evidence and accepted defaults are recorded in
[`resource_measurements.md`](resource_measurements.md).
All three guides use the general profiling tools documented in
[`../../../slurm_profile.md`](../../../slurm_profile.md), including task-input
metadata, reproducibility context, compressed accounting, storage headroom,
and low-frequency live monitoring.

These guides reuse the official environment and operational patterns from
[`../../individual/`](../../individual/README.md), but all project-specific
commands and artifacts remain under this directory and its dedicated run
root.

## Repository layout

```text
dnf_cmodel_griz_riz/
├── README.md
├── resource_measurements.md
├── science_contract.md
├── technical_design.md
├── stage1_train.md
├── stage2_estimate.md
├── stage3_build_hats.md
├── config/
│   ├── dnf-griz-train.yaml
│   ├── dnf-griz-estimate.yaml
│   ├── dnf-riz-train.yaml
│   └── dnf-riz-estimate.yaml
├── notebooks/
│   ├── README.md
│   ├── dnf_cmodel_griz_riz_qa.ipynb
│   └── render-qa.sh
└── scripts/
    ├── README.md
    ├── prepare-training-catalog.py
    ├── run-one-estimate.sbatch
    ├── run-one-hats.sbatch
    ├── run-one-train.sbatch
    ├── smoke-estimates.sh
    ├── submit-estimates.sh
    ├── submit-hats.sh
    ├── submit-training.sh
    ├── validate-hats.py
    ├── validate-stage2.py
    ├── validate-models.py
    ├── variant-config.sh
    └── wrap-model.py
```

## Artifact isolation

Use a dedicated root rather than `$PZ_DP2_ROOT/dnf`:

```bash
export PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
```

The intended runtime layout is:

```text
$PZ_DP2_CUSTOM_ROOT/
├── common/
│   └── training/
├── griz/
│   ├── stage1/
│   ├── stage2/
│   └── stage3/
└── riz/
    ├── stage1/
    ├── stage2/
    └── stage3/
```

The official `$PZ_DP2_ROOT/common/manifests/` may be reused because both
variants cover the same complete Object catalog. Generated cModel training
tables, models, estimates, logs, benchmarks, and HATS products belong below
`$PZ_DP2_CUSTOM_ROOT`.
