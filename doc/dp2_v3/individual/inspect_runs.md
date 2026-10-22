# Inspect individual DP2 v3 runs

These commands provide lightweight terminal inspection for one algorithm at a
time. Set `algorithm` to `fzboost`, `bpz`, `dnf`, or `bpz_test` after loading
the environment required by the stage-specific guide:

```bash
algorithm=dnf
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
```

The launchers append every submission to `submitted-job-ids.tsv`. The commands
below intentionally select its last record. Set `jobid` manually when
inspecting an older submission.

## Stage 1: training

Recover the latest training job ID and inspect its queue and accounting state:

```bash
stage1=$PZ_DP2_ROOT/$algorithm/stage1
jobid=$(tail -n 1 "$stage1/submitted-job-ids.tsv" | cut -f3)
test -n "$jobid"

squeue -j "$jobid" || true
sacct -j "$jobid" --units=G \
  --format=JobID%20,State,ExitCode,Elapsed,TotalCPU,AllocCPUS,MaxRSS,ReqMem
```

Follow both logs while the job runs. Press `Ctrl-C` to stop following without
cancelling the job:

```bash
tail -F \
  "$stage1/log/train-$algorithm-$jobid.out" \
  "$stage1/log/train-$algorithm-$jobid.err"
```

After a `COMPLETED` / `0:0` result, confirm that the candidate exists and run
the algorithm-specific structural validator:

```bash
find "$stage1/model" -maxdepth 1 -type f -name '*.pickle' \
  -printf '%TY-%Tm-%Td %TH:%TM:%TS %12s %p\n' | sort

cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/scripts/validate-models.py "$algorithm"
```

For official models, follow the checksum instructions in the corresponding
Stage 1 guide before allowing the validator to load the reference pickle.

## Stage 2: estimation array

Recover the last array ID and show tasks that are still queued or running:

```bash
stage2=$PZ_DP2_ROOT/$algorithm/stage2
jobid=$(tail -n 1 "$stage2/submitted-job-ids.tsv" | cut -f3)
test -n "$jobid"

squeue -j "$jobid" || true
squeue -h -j "$jobid" -o '%T' | sort | uniq -c
```

This live view refreshes every 30 seconds. It combines `sacct`, which retains
completed tasks, with the current HDF5 count. Press `Ctrl-C` to leave the view;
the array continues in Slurm:

```bash
while true; do
  clear
  date
  sacct -j "$jobid" --parsable2 --noheader --format=JobID%30,State |
  awk -F'|' -v job="$jobid" '
    $1 ~ "^" job "_[0-9]+$" {states[$2]++}
    END {for (state in states) print state, states[state]}
  '
  printf 'HDF5 outputs: '
  find "$stage2/output" -type f -name '*.hdf5' | wc -l
  sleep 30
done
```

Summarize all array-task states already visible to Slurm accounting. Step rows
such as `.batch` are excluded:

```bash
sacct -j "$jobid" --parsable2 --noheader \
  --format=JobID%30,State,ExitCode,Elapsed,MaxRSS |
awk -F'|' -v job="$jobid" '
  $1 ~ "^" job "_[0-9]+$" {
    total++
    states[$2]++
    if ($2 !~ /^(COMPLETED|RUNNING|PENDING|CONFIGURING|COMPLETING)$/) {
      bad++
      print "terminal non-success task:", $0 > "/dev/stderr"
    }
  }
  END {
    print "array tasks seen by sacct:", total
    for (state in states) print state, states[state]
    if (bad) exit 1
  }
'
```

Inspect recent output and error messages without opening the scientific data:

```bash
tail -n 40 "$stage2"/log/slurm-"$jobid"_*.out 2>/dev/null | tail -n 200
grep -REin 'Traceback|Killed|OOM|out of memory|slurmstepd: error' \
  "$stage2"/log/slurm-"$jobid"_* 2>/dev/null || true
```

Once the array has left `squeue`, require every task to have completed with
exit code `0:0`:

```bash
sacct -j "$jobid" --parsable2 --noheader \
  --format=JobID%30,State,ExitCode,Elapsed,MaxRSS |
awk -F'|' -v job="$jobid" '
  $1 ~ "^" job "_[0-9]+$" {
    total++
    states[$2]++
    if ($2 != "COMPLETED" || $3 != "0:0") {
      bad++
      print "non-success task:", $0 > "/dev/stderr"
    }
  }
  END {
    print "array tasks:", total
    for (state in states) print state, states[state]
    if (!total || bad) exit 1
  }
'
```

Compare the expected and produced file counts, then run the fast structural
check over every HDF5. This opens metadata and small marker datasets but does
not read all PDF values into memory:

```bash
manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
printf 'expected inputs: '; wc -l < "$manifest"
printf 'HDF5 outputs:   '; find "$stage2/output" -type f -name '*.hdf5' | wc -l

cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/scripts/validate-stage2.py "$algorithm"
```

For the five-file pilot, validate against the pilot manifest instead:

```bash
doc/dp2_v3/scripts/validate-stage2.py "$algorithm" \
  --manifest "$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt"
```

To inspect the schema, shapes, dtypes, and integrity marker of one output:

```bash
sample=$(find "$stage2/output" -type f -name '*.hdf5' | sort | head -n 1)
test -n "$sample"

"$PZ_PY" - "$sample" <<'PY'
import h5py
import sys

path = sys.argv[1]
print("output:", path)
with h5py.File(path, "r") as handle:
    def show(name, obj):
        if hasattr(obj, "shape"):
            print(name, obj.shape, obj.dtype)
    handle.visititems(show)
    print("pz_compute attributes:", dict(handle["pz_compute"].attrs))
PY
```

## Stage 3: HATS build

The last Stage 3 record contains both the driver job ID and its unique run tag:

```bash
stage3=$PZ_DP2_ROOT/$algorithm/stage3
IFS=$'\t' read -r submitted recorded_algorithm jobid run_tag < \
  <(tail -n 1 "$stage3/submitted-job-ids.tsv")
test "$recorded_algorithm" = "$algorithm"
test -n "$jobid"
test -n "$run_tag"

driver_logs=$stage3/log/driver-$run_tag
worker_logs=$stage3/log/dask-$run_tag
echo "driver job: $jobid"
echo "run tag: $run_tag"
squeue -j "$jobid" || true
sacct -j "$jobid" --units=G \
  --format=JobID%20,State,ExitCode,Elapsed,TotalCPU,AllocCPUS,MaxRSS,ReqMem
```

Follow the driver and inspect the Dask worker population from another terminal:

```bash
tail -F "$driver_logs/driver.log"
```

```bash
squeue -u "$(whoami)"
printf 'worker log files: '
find "$worker_logs" -type f | wc -l
find "$worker_logs" -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' |
  sort | tail -n 20
grep -REin 'Traceback|Killed|OOM|out of memory|slurmstepd: error' \
  "$driver_logs" "$worker_logs" || true
```

Dask can cancel healthy workers while closing the cluster, so worker states
alone do not determine success. After the driver finishes, require its own
zero exit marker and run the complete HATS validator:

```bash
cat "$driver_logs/driver-resource-usage.log"
test "$(cat "$driver_logs/driver-exit-code.txt")" -eq 0

cd "$PZ_COMPUTE_DIR"
doc/dp2_v3/scripts/validate-hats.py "$algorithm"
```

The final validator compares total Stage 2, HATS summary, and PDF row counts;
checks the common schemas and 601-bin redshift grid; and rejects leftover
Parquet staging directories.
