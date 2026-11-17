# Technical design and compatibility plan

This document separates reusable repository capabilities from orchestration
specific to the custom DNF cModel `griz`/`riz` delivery. The primary constraint
is that the official DP2 v3 commands, defaults, artifact paths, and output
schemas remain unchanged unless a separately reviewed bug fix explicitly
restores their documented behavior.

## Verified input contract

The clipped RTN-124 parquet has 554,676 rows and contains, for all six LSST
bands, cModel fluxes, flux errors, flags, magnitudes, and magnitude errors. The
custom training projections need only `redshift` and the selected cModel
magnitude/error pairs.

Direct numerical comparison establishes that the stored cModel training
magnitudes are already SFD-corrected. The `r`, `i`, and `z` values agree with
the flux-derived AB magnitude minus the corresponding legacy correction to
floating-point precision. The `g` values use the legacy coefficient `3.64`,
whereas the versioned DP2 v3 estimation configuration uses `3.65`.

The DP2 Object parquet exposes uncorrected `{band}_cModelMag` and
`{band}_cModelMagErr` columns as well as their source fluxes, `ebv`,
`objectId`, coordinates, and `refExtendedness`. The inspected shard includes
complete-band non-detections: its `r` and `z` cModel values are absent for all
rows. This is retained as a useful stress case for magnitude-limit imputation
and PDF validation rather than filtered out.

## Verified software behavior

The local reference environment contains `pz-rail-dnf 2.0.4`. Its estimator
writes the following one-dimensional arrays below the qp `ancil` group:

- `DNF_Z`;
- `DNF_ZN`;
- `photozerr`;
- `photozerr_param`;
- `photozerr_fit`;
- `nneighbors`;
- `de1`;
- `d1`;
- `id1`.

The existing `rail-estimate` finalizer preserves `ancil` in the Stage 2 HDF5
but only columns copied into its separate `ancillary` group are propagated by
`pz-build-hats`. The custom run therefore needs an explicit, allow-listed way
to promote `DNF_ZN`; it must not copy every estimator diagnostic by default.

`pz-rail-dnf 2.0.4` replaces a missing magnitude with its configured limit and
sets the corresponding error to `1.0`. Its implementation uses chained pandas
assignment. With pandas 3 copy-on-write semantics that assignment does not
modify a DataFrame. A smoke estimate completed without a process error but
produced non-finite PDFs for 6 of 100 rows. Pre-applying exactly the configured
DNF replacement made all 100 PDFs finite and normalized. Completion markers
alone are therefore insufficient; PDF health must be validated.

## Generic changes

### 1. Explicit band selection

Add a shared LSST-band parser and a `--bands` option to `rail-train` and
`rail-estimate`.

- accepted values are ordered, unique subsets of `ugrizy`;
- the default remains `ugrizy`;
- column mappings, parquet projection, SFD markers, and estimator configuration
  use the selected order;
- a parameter file that supplies `bands` or `err_bands` must agree with the
  command-line selection, preventing two conflicting sources of truth.

The official commands omit `--bands`, so their six-band behavior remains
unchanged. Custom launchers pass `--bands=griz` or `--bands=riz` explicitly.

### 2. DNF non-detection compatibility

Implement one tested array-based replacement helper in the shared Python
layer. Before invoking DNF training or estimation, apply the effective DNF
configuration to a copy of each selected magnitude/error column:

1. identify only the configured non-detection value (`NaN` in DP2);
2. replace its magnitude with that column's configured limit;
3. replace the matching error with `1.0`;
4. leave detections and unrelated columns unchanged.

This restores the behavior declared by DNF 2.0.4 under pandas copy-on-write;
it does not introduce a new imputation rule. Tests must demonstrate identical
results to the upstream mutation where that mutation still works.

### 3. Allow-listed estimator ancillary propagation

Add an explicit `rail-estimate` option for qp ancillary names. After estimation
and before marking the file complete, copy only requested one-dimensional
datasets from `ancil/<name>` to `ancillary/<name>`. Validate existence, row
count, dimensionality, and collisions. The default empty list preserves all
official Stage 2 schemas.

The custom launcher requests only `DNF_ZN`.

### 4. Rubin-style scalar summary schema

Extend `pz-build-hats` with explicit options for a summary prefix and the 95%
interval. With prefix `dnf`, the custom schema is:

```text
dnf_z_mean
dnf_z_median
dnf_z_mode
dnf_z_err68_low
dnf_z_err68_high
dnf_z_err95_low
dnf_z_err95_high
```

The interval bounds follow the Rubin DP1 convention documented in
[`SITCOMTN-154`](https://sitcomtn-154.lsst.io/): 16th/84th percentiles for 68%
and 2.5th/97.5th percentiles for 95%. The custom build also passes
`--pdf-layout=none`, so PDFs are read from Stage 2 to derive scalars but are not
published in nested or companion form.

Without these new options, `pz-build-hats` continues to emit the existing
`zmode`, `zmean`, `zmedian`, `z_p16`, and `z_p84` columns and retains its
current PDF-layout default.

## Project-specific code

Scripts below this project directory will own:

- row-preserving `griz` and `riz` training projections;
- custom model names and provenance;
- dedicated artifact roots for each variant;
- explicit opt-in arguments to the generic capabilities;
- smoke, pilot, production, and validation commands;
- schema validation for the eight requested scientific columns;
- run records and PZ Server publication metadata.

They will reuse the official DP2 environment, SFD coefficient file, Object
manifest, Slurm profiling tools, and generic command-line programs. They will
not call or write into the official `dnf` artifact tree.

## Regression matrix

Every generic implementation increment must pass:

| case | required result |
|---|---|
| existing repository tests | all pass |
| official command without `--bands` | still selects `ugrizy` |
| official Stage 2 output | unchanged ancillary and SFD marker schema |
| official Stage 3 command | unchanged scalar names and nested PDF column |
| custom `griz` smoke | four model features; finite normalized PDFs |
| custom `riz` smoke | three model features; finite normalized PDFs |
| ancillary allow-list empty | no estimator diagnostics promoted |
| ancillary allow-list `DNF_ZN` | exactly one DNF diagnostic promoted |
| scalar-only HATS build | requested scalars present; no PDF product |

The initial baseline is 36 passing tests. New tests must be added before or
with each generic behavior change.

## Implemented local evidence

The implemented local increments have established:

- 58 passing repository tests;
- full row-preserving training projections for both variants;
- a four-feature `griz` DNF training/estimate smoke;
- a three-feature `riz` DNF training/estimate smoke;
- finite normalized PDFs for all 1,000 real-Object smoke rows in both variants;
- exact allow-listed `DNF_ZN` propagation;
- exact Stage 2 row fingerprints and checksum-sealed manifest validation;
- scalar-only Rubin-style HATS staging with finite, ordered intervals;
- complete 11-column HATS builds with `float64` science values, no PDF
  artifacts, Stage 2/HATS `DNF_ZN` aggregate agreement, and sealed publication
  validation records;
- an official-default six-band GAaP smoke retaining the `ugrizy` SFD marker
  and existing ancillary schema.
