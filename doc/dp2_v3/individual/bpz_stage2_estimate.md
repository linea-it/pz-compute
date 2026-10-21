# DP2 BPZ Stage 2: estimate all catalogs

This procedure runs only BPZ over the DP2 Object catalog parquet shards. It
uses the batch runner but submits a single Slurm array and writes exclusively
under `$PZ_DP2_ROOT/bpz/stage2/`.

## 1. Load the environment and locate the model

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/primary/catalogs/object
cd "$PZ_COMPUTE_DIR"

test -f "$PZ_DP2_ROOT/bpz/stage1/model/model_dp2_v3p1_bpz_dp2_6band_gold.pickle"
```

## 2. BPZ photometry contract

The launcher applies the reviewed [`bpz-estimate.yaml`](../config/bpz-estimate.yaml)
to the dereddened six-band GAaP magnitudes and errors. The complete scientific
rationale for the photometry, templates, prior, uncertainties, non-detections,
and redshift grid is maintained in
[`bpz_science.md`](../references/bpz_science.md). `objectId` records row
identity and order in the HDF5 output.

## 3. Mandatory smoke test

```bash
doc/dp2_v3/scripts/smoke-estimates.sh bpz
```

In addition to validating the model, columns, and output, this command creates
any missing SED/filter AB files. Do not submit the full array before this
warm-up: concurrent cache creation can cause races and unnecessary I/O.

The smoke test writes:

```text
$PZ_DP2_ROOT/bpz/stage2/smoke/smoke-test.hdf5
$PZ_DP2_ROOT/bpz/stage2/smoke/READY
```

The `READY` marker contains model and YAML checksums. If either changes, the
launcher requires a new smoke test.

## 4. Pilot and submit production

Create the full and five-largest-shard manifests using the
[shared manifest procedure](../common/prepare_estimation_manifests.md). For the
pilot, run the same launcher with BPZ selected:

```bash
PZ_INPUT_MANIFEST=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt \
PZ_BPZ_MAX_CONCURRENT=5 \
  doc/dp2_v3/scripts/submit-estimates.sh bpz
```

After checking `MaxRSS` and `Elapsed`, submit all catalogs:

```bash
doc/dp2_v3/scripts/submit-estimates.sh bpz
```

The job remains in Slurm after logout. The initial defaults are 20 concurrent
tasks, 40 GiB, and 24 hours per task. They are conservative; tune
`PZ_BPZ_MAX_CONCURRENT`, `PZ_BPZ_MEMORY`, and `PZ_BPZ_TIME` from pilot evidence.

## 5. Outputs

```text
$PZ_DP2_ROOT/bpz/stage2/
├── output/object_*.hdf5
├── log/
│   ├── slurm-*.out
│   └── slurm-*.err
├── smoke/
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Rerunning the launcher is the recovery path: complete HDF5 files are validated
and skipped, while incomplete files are preserved with a suffix before retry.

Continue with [`bpz_stage3_build_hats.md`](bpz_stage3_build_hats.md).
