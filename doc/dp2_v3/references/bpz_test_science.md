# BPZ test scientific contract (non-production)

`bpz_test` is a standalone engineering workflow. It exists so all three stages
can be exercised before the official 136 dust-expanded SEDs are available. It
is not an official BPZ profile, is excluded from every batch command, and must
not be used for scientific production or labeled as a Rubin DP2 reproduction.

## Inputs and configuration

The workflow uses the public `COSMOS_seds.list` and associated files installed
by `pz-rail-base`. Its 31 templates are partitioned as 7 elliptical, 12 spiral,
and 12 starburst templates. Therefore Stage 1 creates its own HDFN prior model
with `nt_array=[7,12,12]` using
[`bpz-test-train.yaml`](../config/bpz-test-train.yaml). Stage 2 uses only that
model and [`bpz-test-estimate.yaml`](../config/bpz-test-estimate.yaml).

The default reference-data root is discovered inside the active Python
environment. It can be overridden only for this workflow with:

```bash
export PZ_BPZ_TEST_DATA_ROOT=/absolute/path/to/cosmos31-reference-data
```

The root must contain `SED/COSMOS_seds.list`, its 31 referenced SED files,
`FILTER/lsstcam_{u,g,r,i,z,y}.res`, and a writable `AB/` directory. The smoke
test validates and checksums all of those inputs.

## Scientific limitations

The test retains the six-band GAaP photometry contract, limiting magnitudes,
Madau absorption, error floor, zero-point uncertainty, and 601-point redshift
grid. Like the official DP2 v3 workflows, it uses the versioned LSSTCam SFD
coefficients in
[`dp2-v3-sfd-lsstcam.yaml`](../config/dp2-v3-sfd-lsstcam.yaml). It is
nevertheless scientifically different from official BPZ:

- 31 base COSMOS templates replace the official 136 templates containing
  explicit internal-dust variants;
- its `[7,12,12]` prior is structurally compatible with COSMOS31 but is not the
  reviewed `[7,57,72]` DP2 template/type prior;
- template coverage and dust/type/redshift degeneracies differ, so bias,
  scatter, outlier rate, PDF shape, runtime, and memory may all differ;
- no trusted published reference pickle or validated production result exists
  for this test workflow.

Every artifact remains below `$PZ_DP2_ROOT/bpz_test/`. The model validator
checks the test-specific template partition and provenance. Stage 2 requires a
test smoke marker, and Stage 3 consumes only `bpz_test/stage2/output`; these
guards prevent an official model or output tree from being mixed into the
test workflow and vice versa.

Operational evidence and resource defaults for this non-production workflow
are recorded separately in [`bpz_test_runs.md`](bpz_test_runs.md).
