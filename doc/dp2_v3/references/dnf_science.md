# DNF scientific contract for DP2

This note records the scientific configuration and provenance of the official
six-band DP2 DNF workflow. Operational instructions live under
[`individual/`](../individual/README.md) and [`batch/`](../batch/README.md).
No LineA DNF production run or resource profile is claimed until its pilot and
full-run evidence are retained.

## Pinned DP2 configuration

The immutable
[`dp2_v3p1.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_v3p1.yaml)
includes `dnf` in the six-band `dp2_6band` production set but defines no
DNF-specific overrides. The
[`dp2_library.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_library.yaml)
maps it to `rail.estimation.algos.dnf.DNFInformer` and `DNFEstimator`.
Consequently, reproducing DP2 means combining the `lsst_gaap_1p0` catalog
contract with the defaults implemented by
[`pz-rail-dnf` 2.0.4](https://github.com/LSSTDESC/rail_dnf/blob/v2.0.4/src/rail/estimation/algos/dnf.py).

The executable copies are [`dnf-train.yaml`](../config/dnf-train.yaml) and
[`dnf-estimate.yaml`](../config/dnf-estimate.yaml). They make configurable
defaults explicit so later package releases cannot silently change the run.

## Photometry and training model

Training uses 554,676 clipped RTN-124 objects and six already-dereddened GAaP
1.0 magnitudes plus errors in `ugrizy` order. The limiting magnitudes are
`[26.5, 27.8, 27.1, 26.7, 25.8, 24.6]`. A missing magnitude represented by
NaN is replaced by its band limit and its corresponding error is set to 1.0,
matching the 2.0.4 informer implementation.

`DNFInformer` persists:

- the six-column magnitude matrix (`train_mag`);
- the matching error matrix (`train_err`);
- the reference redshifts (`truez`);
- the per-object Euclidean magnitude norm (`train_norm`);
- a default scikit-learn `KNeighborsRegressor` fitted on the magnitudes.

The default regressor has five neighbors, uniform weights, Minkowski distance
with `p=2`, `algorithm=auto`, and `leaf_size=30`; the trusted artifact resolved
that fit to a Euclidean KD tree. The 501 training rows above redshift 6 are
retained. The estimator output grid, rather than the training sample, is
restricted to 601 points over `[0, 6]`.

## Estimation mode and PDFs

The DP2 project does not override `selection_mode`, so version 2.0.4 uses its
default value `1`: Angular Neighbourhood Fitting (ANF). This is easy to miss
because the package and workflow are named DNF. Values `0` and `2` would select
ENF and the directional-distance mode, respectively, and would not reproduce
the pinned DP2 configuration.

Version 2.0.4 fixes the following choices in code rather than exposing them as
stage parameters:

- preselect 4,000 Euclidean neighbors with the fitted regressor;
- retain 80 neighbors under the ANF metric;
- perform the iterative local hyperplane fit;
- construct a PDF for every object on the 601-point grid.

The estimator emits `DNF_Z` and `DNF_ZN` plus error, neighbor-count, distance,
and neighbor-index ancillary arrays. The common DP2 Stage 3 contract derives
its scalar summary from the PDF and does not promote those DNF-specific
ancillary arrays into HATS columns.

At estimation time DP2 v3 materializes `{band}_gaap1p0Mag_sfd` and matching
errors from the Object catalog using the versioned LSSTCam coefficients in
[`dp2-v3-sfd-lsstcam.yaml`](../config/dp2-v3-sfd-lsstcam.yaml):
`[4.78, 3.65, 2.70, 2.06, 1.58, 1.31]` in `ugrizy` order.

## Trusted reference artifact

The trusted PZ Server product is
[`DNF model DP2 gold 6 bands RTN-124`](https://pzserver.linea.org.br/product/434_dnf_model_dp2_gold_6_bands_rtn124).
Its model file has SHA-256
`bd677d456dba126ef3b47814f34559a280dc3a92d58d58f598f7a21a8cd99ab4`
and size 97,381,274 bytes.

A non-executing pickle-opcode inspection found:

- wrapper class `rail.core.model.Model`;
- creation class `rail.estimation.algos.dnf.DNFInformer`;
- wrapper version `0`;
- catalog tag `lsst_gaap_1p0`;
- provenance `dp2_v3p1/dp2_6band/gold`;
- `train_mag` and `train_err` arrays with 554,676 rows and six columns;
- a fitted `KNeighborsRegressor` with six input features and 554,676 samples;
- serialized scikit-learn version `1.8.0`.

Pickle loading can execute code. Verify the checksum and trusted origin before
running [`validate-models.py`](../scripts/validate-models.py). Compatibility
under a newer scikit-learn release must be demonstrated by validation and a
smoke estimate; a version warning alone neither establishes nor disproves
scientific equivalence.

## Interpretation and upstream evidence

DNF is a nearest-neighbor photometric-redshift method described by De Vicente,
Sánchez, and Sevilla-Noarbe (2016). The
[`pz-rail-dnf` documentation](https://github.com/LSSTDESC/rail_dnf)
distinguishes Euclidean, angular, and directional neighborhood modes.

[`RTN-124`](https://rtn-124.lsst.io/) identifies DNF as one of the six
algorithms entering DP2 production and classifies `rail-dnf` as
community-supported. Its reported six-band timing is useful upstream context,
not a LineA resource guarantee; Apollo memory, walltime, and concurrency must
be established with the five-largest-shard pilot.
