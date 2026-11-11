#!/usr/bin/env bash
set -euo pipefail

benchmark_dir=${1:?benchmark directory is required}
worker_log_dir=${2:?worker log directory is required}
name_file=$benchmark_dir/worker-job-name.txt
driver_context=$benchmark_dir/run-context.log
output=$benchmark_dir/worker-job-ids.txt

test -r "$name_file" || { echo "Missing worker job name: $name_file" >&2; exit 1; }
test -r "$driver_context" || { echo "Missing driver context: $driver_context" >&2; exit 1; }
command -v sacct >/dev/null

worker_job_name=$(tr -d '\r\n' < "$name_file")
driver_start=$(sed -n 's/^driver_start_time=//p' "$driver_context" | tail -n 1)
test -n "$worker_job_name"
test -n "$driver_start"

tmp_dir=$(mktemp -d "$benchmark_dir/.worker-job-ids.XXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT

if ! sacct --allocations --noheader --parsable2 \
  --starttime="$driver_start" \
  --name="$worker_job_name" \
  --format=JobIDRaw,JobName%128,State > "$tmp_dir/sacct.tsv"; then
    echo "WARNING: sacct worker-name query failed; falling back to worker logs" >&2
    : > "$tmp_dir/sacct.tsv"
fi

awk -F'|' -v expected="$worker_job_name" \
  '$1 ~ /^[0-9]+$/ && $2 == expected {print $1}' \
  "$tmp_dir/sacct.tsv" > "$tmp_dir/accounting-ids.txt"

if [ -d "$worker_log_dir" ]; then
  find "$worker_log_dir" -type f -name 'slurm-*.out' -printf '%f\n' |
    sed -n 's/^slurm-\([0-9][0-9]*\)\.out$/\1/p' > "$tmp_dir/log-ids.txt"
else
  : > "$tmp_dir/log-ids.txt"
fi

sort -n -u "$tmp_dir/accounting-ids.txt" "$tmp_dir/log-ids.txt" > "$output"
test -s "$output" || {
  echo "No Stage 3 worker job IDs found for $worker_job_name" >&2
  exit 1
}

printf 'Recovered %s worker job IDs (%s from accounting, %s from started-worker logs)\n' \
  "$(wc -l < "$output")" \
  "$(wc -l < "$tmp_dir/accounting-ids.txt")" \
  "$(wc -l < "$tmp_dir/log-ids.txt")"
