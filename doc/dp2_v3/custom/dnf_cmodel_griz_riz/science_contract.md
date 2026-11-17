# Scientific contract

This document records the reviewed scientific scope of the custom DP2 DNF
cModel delivery requested by Nacho Sevilla Noarbe. Operational measurements
and implementation details must not silently change these choices.

## Products

Produce two independent full-catalog runs:

| variant | ordered input bands | photometry |
|---|---|---|
| `griz` | `g`, `r`, `i`, `z` | cModel magnitudes and magnitude errors |
| `riz` | `r`, `i`, `z` | cModel magnitudes and magnitude errors |

Each variant has its own training projection, trained model, Stage 2 estimates,
and scalar-only HATS collection. Estimation covers the complete DP2 secondary
Object catalog used by the official workflow.

## Training sample

Reuse exactly the clipped RTN-124 training rows used by the official DP2 v3
workflow. Changing the photometric representation or projecting a subset of
bands must not filter, reorder, resample, or reweight the 554,676 objects.
Retain the 501 rows with reference redshift above 6, as in the official DNF
training input.

Training and estimation must use consistent cModel magnitude and error
features for each variant. Inspection of the clipped RTN-124 source confirms
that it contains the required `{band}_cModelMag` and
`{band}_cModelMagErr` columns and that the stored training magnitudes are
already SFD-corrected.

## Extinction correction and non-detections

Use the already SFD-corrected cModel training magnitudes without applying a
second correction. Their values reproduce the legacy correction used when the
clipped RTN-124 product was prepared: `R_g=3.64`, `R_r=2.70`, `R_i=2.06`, and
`R_z=1.58`.

At estimation time, follow the official DP2 v3 path and materialize the
selected `{band}_cModelMag_sfd` and `{band}_cModelMagErr_sfd` columns from the
uncorrected Object photometry. Use the versioned LSSTCam coefficients
`R_g=3.65`, `R_r=2.70`, `R_i=2.06`, and `R_z=1.58`. The small `g`-band
training/estimation coefficient difference is inherited from the official DP2
workflow and must not be silently harmonized for this custom reproduction.

Reuse the official numerical magnitude limits for the selected bands:

| band | limit |
|---|---:|
| `g` | 27.8 |
| `r` | 27.1 |
| `i` | 26.7 |
| `z` | 25.8 |

Keep the official DNF non-detection behavior: a missing magnitude represented
by `NaN` is replaced by its band limit and the matching magnitude error is set
to `1.0` by the pinned DNF implementation.

## DNF configuration

Use the same pinned software and estimator behavior as the official DP2 v3
DNF workflow, except for the explicitly changed photometry and band lists.
In particular:

- `selection_mode: 1` (Angular Neighbourhood Fitting, ANF);
- 4,000-neighbor Euclidean preselection;
- 80 retained neighbors;
- iterative local hyperplane fitting;
- 601 redshift grid points over `[0, 6]`;
- independent training for `griz` and `riz`.

The upstream estimator constructs PDFs internally. They may be used to derive
the requested scalar summaries, but they are not part of the delivered HATS
schema.

For this custom delivery, evaluate the pinned fitted Gaussian PDF with a
per-row log-density shift before normalization. This is an approved numerical
stability correction: it leaves `DNF_Z`, `photozerr`, `DNF_ZN`, the redshift
grid, and the Gaussian definition unchanged. It must not clip fitted
redshifts, replace either DNF estimate, impose an error floor, discard rows, or
substitute a neighbor-based PDF. Non-finite fitted redshifts and non-finite or
non-positive fitted errors are undefined and must fail estimation.

Validate every generated PDF while its chunk remains in memory and record
objective quality counters for fitted redshifts outside the grid, modes at
either grid boundary, parameter failures, non-finite PDFs, and normalization
failures. These diagnostics do not change the delivered HATS schema.

## Delivered HATS columns

In addition to object identity and coordinates required by HATS, publish:

- `dnf_z_mean`;
- `dnf_z_median`;
- `dnf_z_mode`;
- `dnf_z_err68_low`;
- `dnf_z_err68_high`;
- `dnf_z_err95_low`;
- `dnf_z_err95_high`;
- `DNF_ZN` from the estimator ancillary output.

Do not embed a nested PDF column and do not create a companion PDF product.
`DNF_ZN` is the nearest-neighbor point estimate produced by DNF; it is not a
summary derived from the PDF.

## Change control

Any change to the training rows, band order, photometric observable,
extinction treatment, magnitude limits, neighborhood mode, redshift grid, or
delivered scientific columns requires renewed scientific confirmation and an
update to this contract before execution.
