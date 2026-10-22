# DP2 DNF Stage 2: estimate all catalogs

This is the canonical individual path for official six-band DP2 DNF. The run
stays under `$PZ_DP2_ROOT/dnf/stage2/`.

## 1. Check the model and run the smoke test

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

test -f "$PZ_DP2_ROOT/dnf/stage1/model/model_dp2_v3p1_dnf_dp2_6band_gold.pickle"
doc/dp2_v3/scripts/validate-models.py dnf
PZ_SMOKE_ROWS=10000 doc/dp2_v3/scripts/smoke-estimates.sh dnf
```

The smoke path projects 10,000 rows, materializes the reviewed LSSTCam SFD
columns, runs DNF with the versioned configuration, and writes model, YAML,
and SFD-configuration checksums to
`$PZ_DP2_ROOT/dnf/stage2/smoke/READY`.

## 2. Run the mandatory five-file pilot

Prepare the manifests using the
[shared procedure](../common/prepare_estimation_manifests.md), then submit the
five largest shards:

```bash
pilot=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
PZ_INPUT_MANIFEST="$pilot" \
PZ_DNF_MAX_CONCURRENT=5 \
  doc/dp2_v3/scripts/submit-estimates.sh dnf
```

Inspect the retained job record:

```bash
jobid=$(tail -1 "$PZ_DP2_ROOT/dnf/stage2/submitted-job-ids.tsv" | cut -f3)
sacct -j "$jobid" --units=G \
  --format=JobID%30,State,ExitCode,Elapsed,TotalCPU,AllocCPUS,MaxRSS,ReqMem
```

Until this LineA pilot is retained, DNF uses conservative starting defaults of
20 concurrent tasks, 40 GiB, and 24 hours per task. Do not infer production
resources from the RTN-124 per-object benchmark alone. Set
`PZ_DNF_MAX_CONCURRENT`, `PZ_DNF_MEMORY`, and `PZ_DNF_TIME` from observed
`MaxRSS`, `Elapsed`, and cluster capacity before the full submission.

## 3. Submit the complete catalog

After accepting the pilot:

```bash
doc/dp2_v3/scripts/submit-estimates.sh dnf
```

Outputs and logs remain isolated:

```text
$PZ_DP2_ROOT/dnf/stage2/
├── output/Norder=*/Dir=*/Npix=*.hdf5
├── log/slurm-*.{out,err}
├── smoke/
│   ├── smoke-test.hdf5
│   └── READY
├── benchmark/
├── environment-freeze.txt
└── submitted-job-ids.tsv
```

Complete HDF5 files are validated and skipped on resubmission. The scientific
feature, neighbor, PDF, missing-data, and version contracts are documented in
[`dnf_science.md`](../references/dnf_science.md).

Continue with [`dnf_stage3_build_hats.md`](dnf_stage3_build_hats.md).
