# BPZ scientific choices for DP2

This note documents every scientific decision encoded in
[`bpz-train.yaml`](../config/bpz-train.yaml) and
[`bpz-estimate.yaml`](../config/bpz-estimate.yaml). It deliberately contains no
Slurm or production-run claims. BPZ has not yet completed a validated
production run in this workflow.

## Authority and source products

The target is the official `dp2_v3p1 / dp2_6band / gold` BPZ configuration:

- [`dp2_v3p1.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_v3p1.yaml)
  defines the BPZ informer and estimator settings;
- [`dp2_catalogs.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_catalogs.yaml)
  defines band order, column templates, limiting magnitudes, and the grid;
- [`dp2_library.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_library.yaml)
  identifies `BPZliteInformer` and `BPZliteEstimator`;
- [RAIL BPZ](https://github.com/LSSTDESC/rail_bpz) documents the RAIL interface
  to the DESC_BPZ implementation and its marginalized-redshift-PDF output;
- [RTN-124](https://github.com/lsst/rtn-124/blob/2f6e3f4cc7381f6789cb33fb9746ac574a9be9e3/body.tex)
  documents the DP2 photo-z and training-data context.

The RAIL BPZ project requests citation of
[Benítez (2000)](https://ui.adsabs.harvard.edu/abs/2000ApJ...536..571B/abstract)
and [Coe et al. (2006)](https://ui.adsabs.harvard.edu/abs/2006AJ....132..926C/abstract)
for the underlying method and implementation lineage.

The source products are the
[clipped RTN-124 training catalog](https://pzserver.linea.org.br/product/415_clipped_train_rtn124_parquet)
and the trusted
[published BPZ model](https://pzserver.linea.org.br/product/433_bpz_model_dp2_gold_6_bands_rtn124).
The model
has SHA-256
`4872eacee26ae6a5d3716cccd423c7e30b611ed7216e373153058ed59b985170`.

## Photometry and grid

BPZ uses the same six already-dereddened GAaP 1.0 magnitudes as FlexZBoost,
ordered `ugrizy`, but also consumes all six magnitude errors. Stage 1 columns
are unsuffixed; Stage 2 derives `_sfd` columns from Object-table nJy fluxes,
flux errors, and `ebv`. The transformation and provenance are documented in
the Rubin DP2 [photometry documentation](https://dp2.lsst.io/v/SP-3082/tutorials/notebook/201/notebook-201-01.html#photometry),
the [dust-correction tutorial](https://dp2.lsst.io/v/SP-3082/tutorials/notebook/311/notebook-311-1.html#correct-the-effects-of-dust),
and the RTN-124 preprocessing description. The same transform applies before
either estimator is called.

The six magnitude limits are `26.5, 27.8, 27.1, 26.7, 25.8, 24.6` in `ugrizy`
order. `nondetect_val: .nan` matches missing training magnitudes and magnitudes
derived from invalid or non-positive fluxes. BPZ then applies its configured
zero-flux/non-observation treatment rather than treating NaN as a measured
magnitude. `unobserved_val: -99.0` is the explicit BPZ sentinel for an
unobserved band.

The `mag_limits` mapping uses the exact training keys `u_gaap1p0Mag`,
`g_gaap1p0Mag`, `r_gaap1p0Mag`, `i_gaap1p0Mag`, `z_gaap1p0Mag`, and
`y_gaap1p0Mag`. Estimation uses their corresponding `_sfd` keys:
`u_gaap1p0Mag_sfd`, `g_gaap1p0Mag_sfd`, `r_gaap1p0Mag_sfd`,
`i_gaap1p0Mag_sfd`, `z_gaap1p0Mag_sfd`, and `y_gaap1p0Mag_sfd`. The values and
order are unchanged because both sets represent dereddened GAaP 1.0
photometry.

Training and estimation use `zmin: 0.0`, `zmax: 6.0`, and `nzbins: 601`.
Estimation also spells out `dz: 0.01`; these values describe the same uniform
grid and must remain consistent.

## Informer and prior choices

`redshift_col: redshift` preserves the common training-catalog contract.
However, `output_hdfn: true` instructs the informer to materialize the fixed
HDFN prior rather than fit a new prior from those catalog redshifts. Supplying
the common catalog therefore validates schema consistency but does not turn
this BPZ configuration into a data-fitted empirical prior.

The `filter_list` order is fixed to the photometry order:

```text
lsstcam_u, lsstcam_g, lsstcam_r, lsstcam_i, lsstcam_z, lsstcam_y
```

Changing this order would associate fluxes with the wrong response curves.
`nt_array: [7, 57, 72]` is the official DP2/HDFN template-type partition and is
retained without reinterpretation. `override_file_offsets: false` preserves
the offsets carried by the produced model instead of replacing them from an
external file.

Inspection of the trusted reference pickle confirms the following persisted
prior state:

| field | value |
|---|---|
| `fo_arr` | `[0.35, 0.5]` |
| `kt_arr` | `[0.45, 0.147]` |
| `zo_arr` | `[0.431, 0.39, 0.0626]` |
| `km_arr` | `[0.0913, 0.0636, 0.123]` |
| `a_arr` | `[2.465, 1.806, 0.906]` |
| `m0` | `20.0` |
| `nt_array` | `[7, 57, 72]` |
| persisted zero-point offsets | six zeros |

The wrapper identity is `BPZliteInformer`, with `catalog_tag=lsst_gaap_1p0`
and provenance `{project: dp2_v3p1, flavor: dp2_6band, selection: gold}`.

## Estimator choices

| setting | value | scientific reason |
|---|---|---|
| `spectra_file` | `cosmossedswdust136.list` | reproduces the SED library selected by the official DP2 configuration |
| `madau_flag` | `"yes"` | includes intergalactic absorption in the template predictions |
| `no_prior` | `false` | uses the HDFN prior materialized by the informer |
| `p_min` | `0.005` | applies the official DP2 low-probability PDF cutoff |
| `gauss_kernel` | `0.0` | disables additional Gaussian smoothing of the redshift PDF |
| `zp_errors` | six values of `0.03` | propagates the official per-band zero-point uncertainty |
| `mag_err_min` | `0.005` | prevents unrealistically small photometric uncertainties from dominating template likelihoods |
| `override_file_offsets` | `false` | uses the model's persisted offsets; the reference contains six zeros |

The choice of COSMOS SEDs is distinct from the default BPZ CWWSB template set.
The [RAIL BPZ documentation](https://github.com/LSSTDESC/rail_bpz) describes
the alternate COSMOS templates and the BPZ-lite marginalized PDF product.

## Cache and output implications

BPZ may generate missing filter/SED AB tables before inference. The mandatory
single-shard smoke test is therefore scientifically useful as well as
operationally safe: it verifies that the selected filters and spectra can be
combined before a production array and warms the shared cache once.

Stage 2 must emit one 601-bin marginalized redshift PDF per object while
preserving row identity through `objectId`. The workflow retains
`i_gaap1p0Mag_sfd` for the same downstream selection contract used by
FlexZBoost. No claim about production runtime, memory, or scientific output
validation is made until a real BPZ pilot and production run are recorded.
