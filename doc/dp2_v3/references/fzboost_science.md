# FlexZBoost scientific choices for DP2

This note documents the scientific decisions encoded in
[`fzboost-train.yaml`](../config/fzboost-train.yaml) and
[`fzboost-estimate.yaml`](../config/fzboost-estimate.yaml). It contains no
cluster recipe. Operational instructions live under `../individual/` and
`../batch/`; historical production details are summarized in
[`fzboost_runs.md`](fzboost_runs.md).

## Authority and source products

The target is the official `dp2_v3p1 / dp2_6band / gold` configuration, not a
new optimization. Decisions are traced to immutable upstream sources:

- [`dp2_v3p1.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_v3p1.yaml)
  defines the FlexZBoost model settings;
- [`dp2_catalogs.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_catalogs.yaml)
  defines the six-band catalog contract, limiting magnitudes, and redshift grid;
- [`dp2_library.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_library.yaml)
  identifies the DP2 algorithm classes;
- [RTN-124](https://github.com/lsst/rtn-124/blob/2f6e3f4cc7381f6789cb33fb9746ac574a9be9e3/body.tex)
  describes DP2 photo-z production and training-sample construction;
- [the RAIL FlexZBoost implementation](https://github.com/LSSTDESC/rail_flexzboost/blob/19d5078910cd4d9bfa5cd4da6943c0e90f266647/src/rail/estimation/algos/flexzboost.py)
  defines feature construction and non-detection handling.

The input and reference artifacts are:

- [clipped RTN-124 training catalog](https://pzserver.linea.org.br/product/415_clipped_train_rtn124_parquet),
  SHA-256 `0c645457352446bfe9288b2b0d1e85577166f5ca8318c78dfb350453c349e511`;
- [published FlexZBoost model](https://pzserver.linea.org.br/product/435_flexzboost_model_dp2_gold_6_bands_rtn124),
  SHA-256 `33e0fcfa29c10c4305e6de1c739a4765cc1291110d08d8c23674af8de6d8b127`.

## Training sample and photometry

The training input contains all 554,676 clipped RTN-124 rows. Its redshift
range is approximately `0.001` through `9.975`, including 501 objects above
redshift 6. Those rows are retained: `zmax: 6.0` defines the FlexCode basis
interval, not a training-row cut. Filtering them would no longer reproduce the
reference input. The [RTN-124 count table](https://github.com/lsst/rtn-124/blob/2f6e3f4cc7381f6789cb33fb9746ac574a9be9e3/body.tex#L410-L423)
provides the external sample-count reference.

Training uses six GAaP 1.0 magnitudes in `ugrizy` order:

```text
u_gaap1p0Mag, g_gaap1p0Mag, r_gaap1p0Mag,
i_gaap1p0Mag, z_gaap1p0Mag, y_gaap1p0Mag
```

These training magnitudes are already SFD-dereddened even though their names
lack an `_sfd` suffix. RTN-124 documents that flux-to-AB conversion and SFD
correction precede the shuffled DP2 train/test split. Applying another dust
correction would double-correct the training photometry.

At estimation time, the DP2 Object table supplies GAaP fluxes and flux errors
in nJy, plus `ebv`. The workflow constructs AB magnitudes with
`31.4 - 2.5 log10(flux_nJy)` and applies the DP2 SFD coefficients
`[4.81, 3.64, 2.70, 2.06, 1.58, 1.31]` in `ugrizy` order. The resulting Stage
2 names end in `_sfd`. See the Rubin DP2
[photometry documentation](https://dp2.lsst.io/v/SP-3082/tutorials/notebook/201/notebook-201-01.html#photometry)
and [dust-correction tutorial](https://dp2.lsst.io/v/SP-3082/tutorials/notebook/311/notebook-311-1.html#correct-the-effects-of-dust).

The different Stage 1 and Stage 2 suffixes therefore identify the same
scientific photometry state: dereddened GAaP 1.0 magnitudes.

## Feature and missing-data contract

FlexZBoost receives six effective features, constructed by RAIL as:

```text
i, u-g, g-r, r-i, i-z, z-y
```

This is why `include_mag_err: false`: magnitude errors are not model features.
The error columns remain in the common input schema because RAIL updates the
paired error when replacing a missing magnitude.

`nondetect_val: .nan` matches both the clipped training parquet and invalid or
non-positive Object-table fluxes. Before constructing colors, RAIL replaces a
missing magnitude with the official DP2 limit for that band:

| band | u | g | r | i | z | y |
|---|---:|---:|---:|---:|---:|---:|
| limiting magnitude | 26.5 | 27.8 | 27.1 | 26.7 | 25.8 | 24.6 |

The Stage 2 YAML uses the same numerical limits under `_sfd` column names
because RAIL looks them up against the active estimation column template.
Using unsuffixed keys during estimation would not apply the training transform
to the intended columns.

The `mag_limits` mappings therefore contain these exact keys:

| configuration | keys |
|---|---|
| training | `u_gaap1p0Mag`, `g_gaap1p0Mag`, `r_gaap1p0Mag`, `i_gaap1p0Mag`, `z_gaap1p0Mag`, `y_gaap1p0Mag` |
| estimation | `u_gaap1p0Mag_sfd`, `g_gaap1p0Mag_sfd`, `r_gaap1p0Mag_sfd`, `i_gaap1p0Mag_sfd`, `z_gaap1p0Mag_sfd`, `y_gaap1p0Mag_sfd` |

`redshift_col: redshift` identifies the supervised target. `use_weights:
false` reproduces the unweighted DP2 fit; no selection or importance weights
are introduced by this workflow.

## Redshift representation

Both training and estimation use `zmin: 0.0`, `zmax: 6.0`, and `nzbins: 601`.
This is a uniform grid with spacing `0.01`. Keeping the same grid across the
informer, estimator, HDF5 output, and HATS conversion avoids interpolation and
ensures that every stored PDF has the DP2 shape.

## FlexCode and regression choices

All values below reproduce the pinned DP2 configuration:

| setting | value | scientific reason |
|---|---:|---|
| `basis_system` | `cosine` | official DP2 FlexCode basis |
| `max_basis` | `50` | official DP2 model complexity; the reference pickle retains all 50 bases |
| `bumpmin`, `bumpmax`, `nbump` | `0.02`, `0.02`, `1` | fixes the bump threshold to the optimized DP2 value instead of searching it |
| `sharpmin`, `sharpmax`, `nsharp` | `1.2`, `1.2`, `1` | fixes sharpening to the optimized DP2 value instead of searching it |
| `trainfrac` | `0.75` | official fraction used for internal tuning before the final refit |
| `seed` | `1138` | makes the internal split reproducible |
| `retrain_full` | `true` | refits the selected configuration on the full training sample |
| `max_depth` | `8` | official XGBoost tree depth |
| `learning_rate` | `0.3` | official/reference XGBoost learning rate |
| `objective` | `reg:squarederror` | regression objective used for basis coefficients |
| `verbosity` | `1` | explicit reference-compatible XGBoost setting; it changes logging, not the scientific target |

With one bump and one sharpening value, the run is not a new hyperparameter
scan. It reproduces the selected DP2 solution.

The four XGBoost choices are nested under the YAML `regression_params` key;
they are stated explicitly so that a future library-default change cannot
silently alter the fit.

## Model identity and retained evidence

The wrapped model carries:

```text
creation_class_name = rail.estimation.algos.flexzboost.FlexZBoostInformer
catalog_tag = lsst_gaap_1p0
provenance = {project: dp2_v3p1, flavor: dp2_6band, selection: gold}
```

Inspection of the trusted reference pickle confirms six input features, a
cosine basis, 50 retained bases, redshift interval `[0, 6]`, bump `0.02`,
sharpening `1.2`, and the XGBoost parameters above. Tree traversal using the
clipped parquet agrees with the reference only after NaNs are replaced by the
six limiting magnitudes; the root contains all 554,676 rows. This is independent
evidence for the row-selection and non-detection decisions.

The pickle does not persist every informer option. The YAML remains the source
of truth for `trainfrac`, `seed`, `nzbins`, limiting magnitudes, and refit
behavior; the pickle validator checks only state that is actually persisted.

## Output contract

Stage 2 stores one 601-bin PDF per object and retains
`i_gaap1p0Mag_sfd` as ancillary data. `objectId` is used to fingerprint row
identity and order before Stage 3. HATS conversion is representation and
packaging only; it must not change the grid, PDF values, or retained magnitude.
