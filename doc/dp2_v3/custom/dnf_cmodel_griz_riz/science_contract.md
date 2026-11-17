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

## Observed fitted-Gaussian underflow and approved correction

The `griz` production estimate for
`/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset/Norder=4/Dir=0/Npix=2648.parquet`
exposed a numerical failure in the pinned
DNF PDF implementation. Of 406,531 input rows, 19,709 rows (4.8481 per cent)
had a non-finite value in every one of their 601 PDF bins, for 11,845,109
non-finite values in total. `DNF_ZN` remained finite for every row and none of
the affected `DNF_ZN` values lay outside `[0, 6]`.

The affected PDFs are generated from `DNF_Z`, not `DNF_ZN`. In the affected
population, `DNF_Z` has median approximately `-0.303` while `photozerr` has
median approximately `0.0048`. Evaluating such a narrow fitted Gaussian
directly on the non-negative grid underflows to zero at every grid point. The
subsequent division by its zero numerical integral produces an all-`NaN` PDF.
This was a scientific-output validation failure, not an out-of-memory or time
limit failure.

The approved correction evaluates the same fitted Gaussian after a per-row
maximum log-density shift, exponentiates the shifted values, and normalizes
them over the same grid. The multiplicative factor removed by the shift
cancels during normalization, so the corrected result is numerically
equivalent wherever the direct calculation is representable. For cases that
previously underflowed, it evaluates the mathematically normalized Gaussian
restricted to the configured grid; a narrow fit below zero consequently
concentrates at the lower grid boundary.

This opt-in correction is enabled only for this custom workflow. It does not
change training, selected bands, neighbor search, hyperplane fitting,
`DNF_Z`, `photozerr`, `DNF_ZN`, the redshift grid, or the delivered schema. It
does not clip a redshift, impose an error floor, or substitute another point
estimate or PDF. Regression tests require agreement with the direct formula
where that formula is stable and cover the fitted scales observed in this
shard. Every corrected PDF is checked for finite values, a positive integral,
and unit normalization while it remains in memory. A non-finite `DNF_Z` or a
non-finite or non-positive `photozerr` remains a hard failure.

## Complete selected-band non-detections

Production inspection of
`/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset/Norder=4/Dir=0/Npix=1863.parquet`
found 121,261 of 871,439 objects
(13.9150 per cent) with no usable magnitude/error or positive finite
flux/error pair in any selected band. The affected population is identical for
`griz` and `riz`, because `g` is unavailable for every row in this shard. The
usable row counts are 739,941 in `r`, 258,855 in `i`, and 22,424 in `z`; none
of the missing stored magnitude/error pairs can be recovered from the
corresponding flux/error pair.

Where both representations are usable, stored and flux-derived AB magnitudes
agree to approximately `1e-6` mag and their errors agree at a comparable or
smaller numerical scale. This rules out the per-row flux fallback as a remedy
for the missing population. A magnitude-only missingness test finds 121,257
rows; the definitive usable-pair test adds four rows whose magnitude/error and
flux/error pairs are not usable.

The missing population includes two large contiguous regions: rows
695,223--730,865 (35,642 rows) and 730,976--742,747 (11,771 rows). In rows
700,000--710,000 and 710,000--720,000, all 10,000 rows in each estimator chunk
are complete-band non-detections. The reviewed replacement rule maps every
one of those objects to the identical magnitude vector
`(27.8, 27.1, 26.7, 25.8)` and error vector `(1.0, 1.0, 1.0, 1.0)`. The
preceding 10,000-row chunk contains 5,328 objects with the same condition.

For the first fully degenerate chunk, the pinned neighborhood fit returned a
finite fitted redshift but `photozerr == 0` for all 10,000 rows. A zero-width
Gaussian is undefined in the reviewed PDF implementation, so estimation must
continue to fail rather than silently manufacture scalar summaries.
Complete-band non-detections must be identified from input availability rather
than inferred from `photozerr`: the preceding mixed chunk contains 5,328 such
objects but did not trigger the same all-row zero-error failure.

No scientific policy has yet been approved for complete selected-band
non-detections. This observed condition is confirmed as absent cModel
information rather than a magnitude materialization defect. Its catalog-wide
prevalence must be quantified before production resumes.

Candidate policies requiring explicit scientific review are:

1. retain every catalog row but publish null photo-z summaries and a reviewed
   validity/reason flag for objects with no selected-band information;
2. exclude those objects from the published photo-z collection, changing the
   complete-catalog and row-preservation contract;
3. assign an explicitly selected and documented population-prior PDF, which
   would no longer be an object-specific DNF estimate;
4. select another photometric representation and retrain/re-estimate, changing
   the reviewed cModel observable and requiring a new comparability review;
5. define a reviewed DNF-specific fallback distribution for these rows, with
   separate provenance and validation from the ordinary estimator output.

No candidate is currently selected. Do not impose an arbitrary error floor,
create a delta PDF, substitute `DNF_ZN`, discard rows, or emit non-finite
delivered values as an implementation shortcut. Any adopted policy must state
whether `DNF_ZN` is also null or otherwise marked for objects whose nearest
neighbor was selected from the identical imputed limit vector.

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
