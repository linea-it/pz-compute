# DP2 batch Stage 2: estimate all catalogs with all algorithms

This stage uses one generic Slurm runner to submit FlexZBoost, BPZ, and DNF
together. The algorithm registry changes the model, reviewed YAML, output
directory, and resource defaults. Every Object parquet shard becomes one HDF5
file per algorithm.

## 1. Load the common environment and check inputs

```bash
source /scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

test -f "$PZ_DP2_ROOT/fzboost/stage1/model/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle"
test -f "$PZ_DP2_ROOT/bpz/stage1/model/model_dp2_v3p1_bpz_dp2_6band_gold.pickle"
test -f "$PZ_DP2_ROOT/dnf/stage1/model/model_dp2_v3p1_dnf_dp2_6band_gold.pickle"
```

The environment used here must match
`$PZ_DP2_ROOT/common/training/environment-freeze.txt`:

```bash
for algorithm in fzboost bpz dnf; do
    mkdir -p "$PZ_DP2_ROOT/$algorithm/stage2"
    "$PZ_PY" -m pip freeze > \
      "$PZ_DP2_ROOT/$algorithm/stage2/environment-freeze.txt"
    diff -u \
      "$PZ_DP2_ROOT/common/training/environment-freeze.txt" \
      "$PZ_DP2_ROOT/$algorithm/stage2/environment-freeze.txt"
done
```

## 2. Training/estimation column contract

`rail-estimate --sfd-deredden` projects the six GAaP fluxes, six flux errors,
`ebv`, and `objectId` from each large Object shard and constructs the reviewed
algorithm inputs. The complete scientific contracts, including dereddening,
band order, missing-data behavior, features/templates, uncertainties, and PDF
grid, are documented in
[`fzboost_science.md`](../references/fzboost_science.md) and
[`bpz_science.md`](../references/bpz_science.md), and
[`dnf_science.md`](../references/dnf_science.md). This operational guide does
not redefine those choices.

## 3. Run mandatory smoke tests

The batch route is production-oriented and therefore expects the official BPZ
136-SED tree described in
[`bpz_reference_data.md`](../references/bpz_reference_data.md).

Run a 10,000-row sample from one shard through all three algorithms:

```bash
doc/dp2_v3/scripts/smoke-estimates.sh all
```

The script projects only the required input columns before writing
`$PZ_DP2_ROOT/common/smoke/smoke-input.parquet`. Override the sample size when
needed with `PZ_SMOKE_ROWS`; the smoke test intentionally does not process a
complete production shard.

For BPZ this is also a cache-warming step. RAIL/desc-bpz builds missing AB
template files below its reference-data directory. Letting hundreds of array
tasks attempt that creation simultaneously risks races and unnecessary I/O.
The submitter refuses an algorithm whose smoke test has not written its
`smoke/READY` marker. That marker records the model, estimator YAML, and
versioned DP2 v3 LSSTCam SFD-configuration checksums; changing any of them
forces a new smoke test. For BPZ it also records the SED-list, SED-file, and
filter checksums.

Inspect each smoke output before continuing:

```bash
find "$PZ_DP2_ROOT" -path '*/stage2/smoke/smoke-test.hdf5' -print
```

## 4. Pilot on the five largest shards

The BPZ and DNF runtime and memory use differ substantially from FlexZBoost.
Pilot each algorithm before a complete submission. Create both shared
manifests by following the
[manifest preparation procedure](../common/prepare_estimation_manifests.md),
then submit all three pilots:

```bash
pilot=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
PZ_INPUT_MANIFEST=$pilot \
PZ_FZBOOST_MAX_CONCURRENT=5 \
PZ_BPZ_MAX_CONCURRENT=5 \
PZ_DNF_MAX_CONCURRENT=5 \
  doc/dp2_v3/scripts/submit-estimates.sh all
```

Look up the three recorded job IDs and inspect `MaxRSS` and `Elapsed`:

```bash
tail -1 "$PZ_DP2_ROOT/fzboost/stage2/submitted-job-ids.tsv"
tail -1 "$PZ_DP2_ROOT/bpz/stage2/submitted-job-ids.tsv"
tail -1 "$PZ_DP2_ROOT/dnf/stage2/submitted-job-ids.tsv"
sacct -j <jobid> --format=JobID%30,State,ExitCode,Elapsed,MaxRSS
```

The supplied official BPZ defaults (20 concurrent tasks, 40 GiB, 24 hours) are
conservative starting values, not measured production claims. DNF defaults to
105 concurrent tasks, 34 GiB, and two hours based on pilot job `217097`.
FlexZBoost defaults to 105 concurrent tasks, 34 GiB, and one hour based on
pilot job `217085`. These two 34-GiB requests retain 19.0% and 16.9% above
their observed peaks, respectively, and each 105-task throttle targets 95% of
the resulting discrete cluster capacity. Override resources with the
corresponding `PZ_<ALGORITHM>_*` variables when newer evidence or a different
partition requires it.

## 5. Submit all algorithms over the complete catalog

```bash
doc/dp2_v3/scripts/submit-estimates.sh all
```

`all` submits one independent Slurm array per algorithm. Each array covers the
stable, sorted full-catalog manifest; Slurm queues and executes the work after
the shell disconnects. Existing complete output files are validated and
skipped, so rerunning the same command is the recovery path for interrupted or
partially failed production runs. An invalid existing file is renamed with an
`.incomplete-<job>-<task>` suffix before retrying.

Outputs and logs remain isolated:

```text
$PZ_DP2_ROOT/fzboost/stage2/output/Norder=*/Dir=*/Npix=*.hdf5
$PZ_DP2_ROOT/fzboost/stage2/log/slurm-*.{out,err}
$PZ_DP2_ROOT/bpz/stage2/output/Norder=*/Dir=*/Npix=*.hdf5
$PZ_DP2_ROOT/bpz/stage2/log/slurm-*.{out,err}
$PZ_DP2_ROOT/dnf/stage2/output/Norder=*/Dir=*/Npix=*.hdf5
$PZ_DP2_ROOT/dnf/stage2/log/slurm-*.{out,err}
```

No `nohup`, `tmux`, or open SSH session is needed after `sbatch` returns the
job IDs.

For a single algorithm, use its named guide under
[`individual/README.md`](../individual/README.md).

## 6. Verify completion

For each algorithm, require equal input/output counts and no failed array task:

```bash
inputs=$(wc -l < "$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt")
for algorithm in fzboost bpz dnf; do
    outputs=$(find "$PZ_DP2_ROOT/$algorithm/stage2/output" -name '*.hdf5' | wc -l)
    printf '%s: inputs=%s outputs=%s\n' "$algorithm" "$inputs" "$outputs"
    test "$inputs" -eq "$outputs"
done

cat "$PZ_DP2_ROOT/fzboost/stage2/submitted-job-ids.tsv"
cat "$PZ_DP2_ROOT/bpz/stage2/submitted-job-ids.tsv"
cat "$PZ_DP2_ROOT/dnf/stage2/submitted-job-ids.tsv"
```

Use `sacct -j <jobid>` for every production job ID and require every array task
to be `COMPLETED` with exit code `0:0`. The generic runner also verifies the
601-bin PDF, retained `i_gaap1p0Mag_sfd`, row count, and `objectId` fingerprint
before treating an existing HDF5 as complete.

Continue with [batch Stage 3](build_hats_all.md), which submits all three HATS
builds with one `all` command.
