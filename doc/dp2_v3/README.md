# DP2 v3: FlexZBoost, official BPZ, and standalone BPZ test

This directory describes one DP2 workflow with a shared installation, shared
training catalog, and algorithm-specific configurations. The supported set is
currently deliberately small:

| command name | RAIL classes | model |
|---|---|---|
| `fzboost` | `FlexZBoostInformer` / `FlexZBoostEstimator` | fitted from the clipped RTN-124 catalog |
| `bpz` | `BPZliteInformer` / `BPZliteEstimator` | fixed HDFN prior used by DP2 |
| `bpz_test` | `BPZliteInformer` / `BPZliteEstimator` | non-production COSMOS31-compatible test prior |

Run [the Apollo setup](dp2_setup_apollo.md) once. For a reduced local test, use
[the local setup](dp2_setup_local.md). Shared, algorithm-neutral prerequisites
live under `common/`; after preparing them, choose an execution route:

| route | use when | entry point |
|---|---|---|
| `common/` | preparing inputs reused by either execution route | [`common/README.md`](common/README.md) |
| `individual/` | running and diagnosing one named algorithm | [`individual/README.md`](individual/README.md) |
| `batch/` | queueing and validating FlexZBoost and BPZ together | [`batch/README.md`](batch/README.md) |

The individual files always include the algorithm in the filename:

- [`fzboost_stage1_train.md`](individual/fzboost_stage1_train.md)
- [`fzboost_stage2_estimate.md`](individual/fzboost_stage2_estimate.md)
- [`fzboost_stage3_build_hats.md`](individual/fzboost_stage3_build_hats.md)
- [`bpz_stage1_train.md`](individual/bpz_stage1_train.md)
- [`bpz_stage2_estimate.md`](individual/bpz_stage2_estimate.md)
- [`bpz_stage3_build_hats.md`](individual/bpz_stage3_build_hats.md)
- [`bpz_test_stage1_train.md`](individual/bpz_test_stage1_train.md)
- [`bpz_test_stage2_estimate.md`](individual/bpz_test_stage2_estimate.md)
- [`bpz_test_stage3_build_hats.md`](individual/bpz_test_stage3_build_hats.md)

The batch route keeps only shared or multi-algorithm procedures:

- [`train_all.md`](batch/train_all.md)
- [`estimate_all.md`](batch/estimate_all.md)
- [`build_hats_all.md`](batch/build_hats_all.md)

The individual guides never require instructions from `batch/`. Both routes
refer to the same neutral prerequisites:

- [`prepare_training_catalog.md`](common/prepare_training_catalog.md)
- [`prepare_estimation_manifests.md`](common/prepare_estimation_manifests.md)

`sbatch` owns the jobs after submission, so the login shell may be closed.

The files under `config/` are the reviewed scientific parameters. The files
under `scripts/` are reusable launchers; do not copy a FlexZBoost command and
edit it by hand for BPZ.

The shared scientific environment installs all seven algorithms represented by
the DP2 reference models: BPZ, DNF, FlexZBoost, GPz, KNN, LePhare, and TPZ.
The current v3 orchestration exposes official FlexZBoost and BPZ plus the
explicitly non-production `bpz_test` workflow. Installing all seven packages
keeps the environment ready for the remaining algorithms without claiming
that their v3 workflows are ready.

Scientific provenance and production evidence are intentionally separate:

- [`references/fzboost_science.md`](references/fzboost_science.md)
- [`references/fzboost_runs.md`](references/fzboost_runs.md)
- [`references/bpz_science.md`](references/bpz_science.md)
- [`references/bpz_reference_data.md`](references/bpz_reference_data.md)
- [`references/bpz_test_science.md`](references/bpz_test_science.md)
- [`references/bpz_test_runs.md`](references/bpz_test_runs.md)

There is no official BPZ run-history document until a real BPZ production run
has been completed and validated. The BPZ test pilot is recorded separately
and cannot validate or size the official 136-template workflow.

## Canonical Stage 2 input

Stage 2 reads the partitioned DP2 Object catalog expected to provide more
balanced shards at:

```text
/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
```

Its Parquet files are discovered recursively below
`Norder=*/Dir=*/Npix=*.parquet`. The Stage 2 output tree preserves those
relative directories and replaces only the `.parquet` suffix with `.hdf5`.
The catalog has the same column schema as the former DP2 Object input.

## Canonical run layout

Individual and batch launchers use exactly the same layout below
`$PZ_RUN_ROOT`. The batch mode changes only how jobs are submitted; it does not
mix their artifacts:

```text
dp2-v3/
├── common/
│   ├── training/
│   │   ├── train_clipped_v3.parquet
│   │   ├── train_clipped_v3_gaap1p0.hdf5
│   │   └── environment-freeze.txt
│   └── manifests/
│       ├── input-parquet-files.txt
│       └── pilot-parquet-files.txt
├── fzboost/
│   ├── stage1/{model,log,benchmark}/
│   ├── stage2/{output,log,smoke,benchmark}/
│   └── stage3/{output,log/{dask-*,driver-*},smoke,benchmark}/
├── bpz/
│   ├── stage1/{model,log,benchmark}/
│   ├── stage2/{output,log,smoke,benchmark}/
│   └── stage3/{output,log/{dask-*,driver-*},smoke,benchmark}/
└── bpz_test/
    ├── stage1/{model,log,benchmark}/
    ├── stage2/{output,log,smoke,benchmark}/
    └── stage3/{output,log/{dask-*,driver-*},smoke,benchmark}/
```

Each stage also keeps its own `submitted-job-ids.tsv` when applicable. Thus
everything attributable to BPZ remains below `dp2-v3/bpz/`, and everything
attributable to FlexZBoost remains below `dp2-v3/fzboost/`. Only immutable or
shared inputs live below `common/`. The non-production workflow is likewise
confined to `dp2-v3/bpz_test/`; it is never included in batch `all` commands.

Set the root after loading the environment:

```bash
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
```

## Scientific contract

Both algorithms see six already-dereddened GAaP 1.0 magnitudes in `ugrizy`
order during training. At estimation time, `rail-estimate` derives the matching
`{band}_gaap1p0Mag_sfd` and `{band}_gaap1p0MagErr_sfd` columns from Object-table
fluxes, flux errors, and `ebv`. DP2 v3 explicitly supplies the LSSTCam
`A_band/E(B-V)` coefficients from
[`dp2-v3-sfd-lsstcam.yaml`](config/dp2-v3-sfd-lsstcam.yaml):
`[4.78, 3.65, 2.70, 2.06, 1.58, 1.31]` in `ugrizy` order. This leaves the
legacy defaults used by older workflows unchanged.

The important difference is that FlexZBoost constructs six features (`i` and
five adjacent colors) and does not use magnitude errors. BPZ consumes all six
magnitudes and all six magnitude errors. BPZ also needs its SED/filter data;
the sampled smoke test must be run before a large array so its AB cache is
created once rather than concurrently by many tasks.

Production BPZ requires the official 136-SED tree. The public COSMOS31 path is
implemented as the completely separate `bpz_test` workflow, including its own
Stage 1 model, Stage 2 estimates, Stage 3 HATS products, configurations,
validation, and documentation. It is not a profile or fallback within `bpz`.

The retained redshift grid is 601 points over `[0, 6]` for all three workflows,
so Stage 3 receives the same HDF5 shape and the same retained
`i_gaap1p0Mag_sfd` ancillary column.

## Pinned upstream configuration

The parameters are transcribed from the immutable DP2 project files:

- [`dp2_v3p1.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_v3p1.yaml)
- [`dp2_catalogs.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_catalogs.yaml)
- [`dp2_library.yaml`](https://github.com/LSSTDESC/rail_project_config/blob/c1014cf5de697b9238d38c0cd635efb2cbafd382/dp2/dp2_library.yaml)

The legacy detailed FlexZBoost run recipes remain in `doc/dp2_v2/`. DP2 v3
keeps operational instructions in `individual/` and `batch/`, while
`references/` records scientific justification and concise run evidence.
