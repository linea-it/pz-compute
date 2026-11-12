#!/usr/bin/env bash
set -Eeuo pipefail

: "${PZ_BATCH_RUN_TAG:?missing PZ_BATCH_RUN_TAG}"
: "${PZ_BATCH_RUN_DIR:?missing PZ_BATCH_RUN_DIR}"
: "${PZ_DP2_ROOT:?missing PZ_DP2_ROOT}"
: "${PZ_DP2_INPUT_DATASET:?missing PZ_DP2_INPUT_DATASET}"

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd "$scripts_dir/../../.." && pwd)
profile=$repo_dir/performance/slurm/slurm-profile
gaap_env=${PZ_GAAP_ENV_SCRIPT:-/scripts/$(whoami)/ondemand/env-dp2-gaap1p0.sh}
hats_env=${PZ_HATS_ENV_SCRIPT:-/scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh}

PZ_BATCH_ALGORITHMS=${PZ_BATCH_ALGORITHMS:-fzboost,dnf,bpz}
PZ_BATCH_ALGORITHMS=${PZ_BATCH_ALGORITHMS//:/,}
PZ_BATCH_JOB_TIMEOUT_SECONDS=${PZ_BATCH_JOB_TIMEOUT_SECONDS:-864000}
PZ_BATCH_POLL_SECONDS=${PZ_BATCH_POLL_SECONDS:-30}
PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB=${PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB:-8192}
IFS=',' read -r -a batch_algorithms_for_storage <<< "$PZ_BATCH_ALGORITHMS"
PZ_BATCH_MIN_FREE_GIB=${PZ_BATCH_MIN_FREE_GIB:-$((${#batch_algorithms_for_storage[@]} * 8192))}
PZ_HATS_MIN_WORKERS=${PZ_HATS_MIN_WORKERS:-1}
PZ_HATS_MAX_WORKERS=${PZ_HATS_MAX_WORKERS:-80}
PZ_HATS_SCALE_DOWN_DELAY=${PZ_HATS_SCALE_DOWN_DELAY:-180}
PZ_HATS_MARGIN_ARCSEC=${PZ_HATS_MARGIN_ARCSEC:-5}
batch_dp2_root=$PZ_DP2_ROOT
batch_input_dataset=$PZ_DP2_INPUT_DATASET
batch_hats_min_workers=$PZ_HATS_MIN_WORKERS
batch_hats_max_workers=$PZ_HATS_MAX_WORKERS
batch_hats_scale_down_delay=$PZ_HATS_SCALE_DOWN_DELAY
batch_hats_margin_arcsec=$PZ_HATS_MARGIN_ARCSEC

status_file=$PZ_BATCH_RUN_DIR/status.tsv
jobs_file=$PZ_BATCH_RUN_DIR/jobs.tsv
artifacts_file=$PZ_BATCH_RUN_DIR/artifacts.tsv
context_file=$PZ_BATCH_RUN_DIR/run-context.log
failure_file=$PZ_BATCH_RUN_DIR/failure-report.md
summary_file=$PZ_BATCH_RUN_DIR/summary.md
active_file=$PZ_BATCH_RUN_DIR/active-job.tsv
mkdir -p "$PZ_BATCH_RUN_DIR"

current_algorithm=preflight
current_stage=initialization
current_jobid=
current_job_state=
active_child=0
failure_written=0

sanitize() {
    printf '%s' "$1" | tr '\t\r\n' '   '
}

record_status() {
    local state=${1:?state is required}
    local detail=${2:-}
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$(date --iso-8601=seconds)" "$current_algorithm" "$current_stage" \
      "$state" "${current_jobid:--}" "$(sanitize "$detail")" >> "$status_file"
}

record_job() {
    local kind=${1:?kind is required}
    local jobid=${2:?jobid is required}
    local run_tag=${3:--}
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$(date --iso-8601=seconds)" "$current_algorithm" "$current_stage" \
      "$kind" "$jobid" "$run_tag" >> "$jobs_file"
}

record_artifact() {
    local kind=${1:?kind is required}
    local path=${2:?path is required}
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "$(date --iso-8601=seconds)" "$current_algorithm" "$current_stage" \
      "$kind" "$path" >> "$artifacts_file"
}

cancel_active_child() {
    if [ "$active_child" -eq 1 ] && [ -n "$current_jobid" ]; then
        scancel "$current_jobid" >/dev/null 2>&1 || true
        record_status CANCEL_REQUESTED "controller stopped while child job was active"
    fi
}

write_failure() {
    local exit_code=${1:?exit code is required}
    local reason=${2:?reason is required}
    local command=${3:-unknown}
    [ "$failure_written" -eq 0 ] || return 0
    failure_written=1
    set +e
    {
        echo "# DP2 v3 batch failure report"
        echo
        echo "- Run tag: \`$PZ_BATCH_RUN_TAG\`"
        echo "- Controller job: \`${SLURM_JOB_ID:-not-running-under-slurm}\`"
        echo "- Time: \`$(date --iso-8601=seconds)\`"
        echo "- Algorithm: \`$current_algorithm\`"
        echo "- Stage: \`$current_stage\`"
        echo "- Child job: \`${current_jobid:-none}\`"
        echo "- Child state: \`${current_job_state:-unknown}\`"
        echo "- Exit code: \`$exit_code\`"
        echo "- Reason: $reason"
        echo
        echo "## Failing command"
        echo
        echo '```text'
        printf '%s\n' "$command"
        echo '```'
        echo
        echo "## Artifacts"
        echo
        echo "- Status ledger: \`$status_file\`"
        echo "- Job ledger: \`$jobs_file\`"
        echo "- Artifact index: \`$artifacts_file\`"
        echo "- Controller stdout: \`$PZ_BATCH_RUN_DIR/controller.log\`"
        echo "- Controller stderr: \`$PZ_BATCH_RUN_DIR/controller.err\`"
        if [ -n "$current_jobid" ]; then
            echo
            echo "Inspect the failed child with:"
            echo
            echo '```bash'
            echo "sacct -j $current_jobid --units=G --format=JobID%30,State,ExitCode,Elapsed,TotalCPU,AllocCPUS,MaxRSS,ReqMem"
            echo '```'
        fi
    } > "$failure_file"
    record_status FAILED "$reason; command=$command; exit_code=$exit_code"
    touch "$PZ_BATCH_RUN_DIR/FAILED"
}

on_error() {
    local exit_code=${1:?exit code is required}
    local line=${2:?line is required}
    local command=${3:-unknown}
    trap - ERR
    cancel_active_child
    write_failure "$exit_code" "controller command failed at line $line" "$command"
    exit "$exit_code"
}

on_signal() {
    local signal=${1:?signal is required}
    trap - ERR
    cancel_active_child
    write_failure 128 "controller received $signal" "$signal"
    exit 128
}

trap 'rc=$?; on_error "$rc" "$LINENO" "$BASH_COMMAND"' ERR
trap 'on_signal SIGTERM' TERM
trap 'on_signal SIGINT' INT

printf 'timestamp\talgorithm\tstage\tstatus\tjob_id\tdetail\n' > "$status_file"
printf 'timestamp\talgorithm\tstage\tkind\tjob_id\trun_tag\n' > "$jobs_file"
printf 'timestamp\talgorithm\tstage\tkind\tpath\n' > "$artifacts_file"

validate_positive_integer() {
    local name=${1:?name is required}
    local value=${2:-}
    case "$value" in
        ''|*[!0-9]*|0) echo "$name must be a positive integer: $value" >&2; return 2 ;;
    esac
}

validate_positive_number() {
    local name=${1:?name is required}
    local value=${2:-}
    awk -v value="$value" \
      'BEGIN { exit !(value ~ /^([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$/ && value > 0) }' || {
        echo "$name must be a positive number: $value" >&2
        return 2
    }
}

load_gaap_environment() {
    # shellcheck source=/dev/null
    source "$gaap_env"
    PZ_DP2_ROOT=$batch_dp2_root
    PZ_DP2_INPUT_DATASET=$batch_input_dataset
    PZ_HATS_MIN_WORKERS=$batch_hats_min_workers
    PZ_HATS_MAX_WORKERS=$batch_hats_max_workers
    PZ_HATS_SCALE_DOWN_DELAY=$batch_hats_scale_down_delay
    PZ_HATS_MARGIN_ARCSEC=$batch_hats_margin_arcsec
    export PZ_DP2_ROOT PZ_DP2_INPUT_DATASET
    export PZ_HATS_MIN_WORKERS PZ_HATS_MAX_WORKERS PZ_HATS_SCALE_DOWN_DELAY PZ_HATS_MARGIN_ARCSEC
    cd "$repo_dir"
}

load_hats_environment() {
    # shellcheck source=/dev/null
    source "$hats_env"
    PZ_DP2_ROOT=$batch_dp2_root
    PZ_DP2_INPUT_DATASET=$batch_input_dataset
    PZ_HATS_MIN_WORKERS=$batch_hats_min_workers
    PZ_HATS_MAX_WORKERS=$batch_hats_max_workers
    PZ_HATS_SCALE_DOWN_DELAY=$batch_hats_scale_down_delay
    PZ_HATS_MARGIN_ARCSEC=$batch_hats_margin_arcsec
    export PZ_DP2_ROOT PZ_DP2_INPUT_DATASET
    export PZ_HATS_MIN_WORKERS PZ_HATS_MAX_WORKERS PZ_HATS_SCALE_DOWN_DELAY PZ_HATS_MARGIN_ARCSEC
    cd "$repo_dir"
}

ledger_count() {
    local ledger=${1:?ledger is required}
    if [ -f "$ledger" ]; then
        wc -l < "$ledger"
    else
        echo 0
    fi
}

new_job_from_ledger() {
    local ledger=${1:?ledger is required}
    local before=${2:?previous count is required}
    local expected=$((before + 1))
    local after
    after=$(ledger_count "$ledger")
    if [ "$after" -ne "$expected" ]; then
        echo "Expected one new record in $ledger; before=$before after=$after" >&2
        return 1
    fi
    sed -n "${expected}p" "$ledger" | cut -f3
}

job_record() {
    local jobid=${1:?job id is required}
    sacct -X --noheader --parsable2 -j "$jobid" \
      --format=JobIDRaw,State,ExitCode |
      awk -F'|' -v id="$jobid" '$1 == id {print $2 "|" $3; exit}'
}

wait_for_job() {
    local jobid=${1:?job id is required}
    local start now record state exit_code normalized
    start=$(date +%s)
    current_jobid=$jobid
    current_job_state=PENDING
    active_child=1
    printf '%s\t%s\t%s\t%s\n' \
      "$current_algorithm" "$current_stage" "$jobid" "$(date --iso-8601=seconds)" > "$active_file"
    record_status WAITING "waiting for Slurm terminal state"

    while true; do
        record=$(job_record "$jobid" || true)
        if [ -n "$record" ]; then
            IFS='|' read -r state exit_code <<< "$record"
            normalized=${state%% *}
            normalized=${normalized%%+}
            current_job_state=$state
            case "$normalized" in
                COMPLETED)
                    active_child=0
                    rm -f "$active_file"
                    if [ "$exit_code" = 0:0 ]; then
                        record_status COMPLETED "Slurm state=$state exit=$exit_code"
                        return 0
                    fi
                    record_status JOB_FAILED "Slurm state=$state exit=$exit_code"
                    return 1
                    ;;
                FAILED|CANCELLED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|PREEMPTED|BOOT_FAIL|DEADLINE|REVOKED)
                    active_child=0
                    rm -f "$active_file"
                    record_status JOB_FAILED "Slurm state=$state exit=$exit_code"
                    return 1
                    ;;
            esac
        fi

        now=$(date +%s)
        if [ $((now - start)) -ge "$PZ_BATCH_JOB_TIMEOUT_SECONDS" ]; then
            scancel "$jobid" >/dev/null 2>&1 || true
            active_child=0
            rm -f "$active_file"
            current_job_state=WAIT_TIMEOUT
            record_status JOB_FAILED "wait exceeded ${PZ_BATCH_JOB_TIMEOUT_SECONDS}s; cancellation requested"
            return 124
        fi
        sleep "$PZ_BATCH_POLL_SECONDS"
    done
}

profile_regular_job() {
    local jobid=${1:?job id is required}
    local target=${2:?target is required}
    local label=${3:?label is required}
    local output_dir=${4:?output directory is required}
    local nodes=${5:-}
    local args=(
      --job-id "$jobid"
      --expected-jobs 1
      --concurrency-target "$target"
      --label "$label"
      --output-dir "$output_dir"
      --capture-slurm-snapshot
      --fail-on-unsuccessful
    )
    if [ -n "$nodes" ]; then
        args+=(--cluster-context-nodes "$nodes")
    fi
    "$profile" "${args[@]}"
}

profile_array_job() {
    local jobid=${1:?job id is required}
    local expected=${2:?expected jobs is required}
    local target=${3:?target is required}
    local label=${4:?label is required}
    local output_dir=${5:?output directory is required}
    "$profile" \
      --job-id "$jobid" \
      --expected-jobs "$expected" \
      --concurrency-target "$target" \
      --cluster-context-nodes 'apl[01-28]' \
      --label "$label" \
      --output-dir "$output_dir" \
      --capture-slurm-snapshot \
      --fail-on-unsuccessful
}

require_free_gib() {
    local required_gib=${1:?required GiB is required}
    local available_bytes required_bytes
    available_bytes=$(df -PB1 "$PZ_DP2_ROOT" | awk 'NR == 2 {print $4}')
    required_bytes=$((required_gib * 1024 * 1024 * 1024))
    if [ "$available_bytes" -lt "$required_bytes" ]; then
        echo "Insufficient free space: available=$available_bytes required=$required_bytes (${required_gib} GiB)" >&2
        return 1
    fi
}

validate_algorithm_order() {
    local algorithm
    declare -A seen=()
    for algorithm in "${algorithms[@]}"; do
        case "$algorithm" in
            fzboost|dnf|bpz) ;;
            *) echo "Unsupported official batch algorithm: $algorithm" >&2; return 2 ;;
        esac
        if [ -n "${seen[$algorithm]:-}" ]; then
            echo "Duplicate batch algorithm: $algorithm" >&2
            return 2
        fi
        seen[$algorithm]=1
    done
    test "${#algorithms[@]}" -gt 0
}

require_fresh_downstream_tree() {
    local algorithm=${1:?algorithm is required}
    local stage2_output=$PZ_DP2_ROOT/$algorithm/stage2/output
    local stage3_output=$PZ_DP2_ROOT/$algorithm/stage3/output
    if [ -d "$stage2_output" ] && \
       find "$stage2_output" -type f -name '*.hdf5' -print -quit | grep -q .; then
        echo "$algorithm already has Stage 2 HDF5 outputs. The serial controller starts at Stage 1 and will not mix them with a retrained model. Recover through the individual guide or use a fresh PZ_DP2_ROOT." >&2
        return 1
    fi
    if [ -d "$stage3_output" ] && \
       find "$stage3_output" -mindepth 1 -print -quit | grep -q .; then
        echo "$algorithm already has Stage 3 outputs. Use the individual recovery path or a fresh PZ_DP2_ROOT." >&2
        return 1
    fi
}

run_algorithm() {
    local algorithm=${1:?algorithm is required}
    local upper stage1 stage2 stage3 ledger before jobid
    local pilot_manifest full_manifest pilot_expected production_expected
    local production_target run_tag benchmark_dir driver_logs worker_logs worker_count

    current_algorithm=$algorithm
    upper=${algorithm^^}
    stage1=$PZ_DP2_ROOT/$algorithm/stage1
    stage2=$PZ_DP2_ROOT/$algorithm/stage2
    stage3=$PZ_DP2_ROOT/$algorithm/stage3

    current_stage=algorithm-storage-preflight
    current_jobid=
    current_job_state=
    record_status STARTED "requiring ${PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB} GiB free before algorithm"
    require_free_gib "$PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB"
    require_fresh_downstream_tree "$algorithm"
    record_status COMPLETED "per-algorithm storage check passed"

    current_stage=stage1-training
    current_jobid=
    current_job_state=
    record_status STARTED "submitting training"
    load_gaap_environment
    ledger=$stage1/submitted-job-ids.tsv
    before=$(ledger_count "$ledger")
    "$scripts_dir/submit-training.sh" "$algorithm"
    jobid=$(new_job_from_ledger "$ledger" "$before")
    record_job training "$jobid"
    wait_for_job "$jobid"

    current_stage=stage1-benchmark
    record_status STARTED "profiling training job $jobid"
    profile_regular_job "$jobid" 1 "$algorithm-stage1-training-$jobid" \
      "$stage1/benchmark/training-$jobid" 'apl[01-28]'
    record_status COMPLETED "training benchmark written"
    record_artifact benchmark "$stage1/benchmark/training-$jobid"

    current_stage=stage1-validation
    record_status STARTED "validating trained model"
    "$scripts_dir/validate-models.py" "$algorithm"
    record_status COMPLETED "model validation passed"
    record_artifact model "$stage1/model"

    current_stage=stage2-smoke
    current_jobid=
    current_job_state=
    record_status STARTED "running Stage 2 smoke test"
    "$scripts_dir/smoke-estimates.sh" "$algorithm"
    record_status COMPLETED "smoke test passed"

    pilot_manifest=$PZ_DP2_ROOT/common/manifests/pilot-parquet-files.txt
    pilot_expected=$(wc -l < "$pilot_manifest")
    current_stage=stage2-pilot
    record_status STARTED "submitting $pilot_expected pilot tasks"
    ledger=$stage2/submitted-job-ids.tsv
    before=$(ledger_count "$ledger")
    env PZ_INPUT_MANIFEST="$pilot_manifest" "PZ_${upper}_MAX_CONCURRENT=5" \
      "$scripts_dir/submit-estimates.sh" "$algorithm"
    jobid=$(new_job_from_ledger "$ledger" "$before")
    record_job pilot-array "$jobid"
    wait_for_job "$jobid"

    current_stage=stage2-pilot-benchmark
    record_status STARTED "profiling pilot array $jobid"
    profile_array_job "$jobid" "$pilot_expected" 5 \
      "$algorithm-stage2-pilot-$jobid" "$stage2/benchmark/pilot-$jobid"
    record_status COMPLETED "pilot benchmark written"
    record_artifact benchmark "$stage2/benchmark/pilot-$jobid"

    current_stage=stage2-pilot-validation
    record_status STARTED "validating pilot outputs"
    "$scripts_dir/validate-stage2.py" "$algorithm" --manifest "$pilot_manifest"
    record_status COMPLETED "pilot validation passed"

    source "$scripts_dir/algorithm-config.sh"
    dp2_algorithm_config "$algorithm"
    production_target=$PZ_DEFAULT_MAX_CONCURRENT
    full_manifest=$PZ_DP2_ROOT/common/manifests/input-parquet-files.txt
    production_expected=$(wc -l < "$full_manifest")
    current_stage=stage2-production
    record_status STARTED "submitting $production_expected production tasks with target $production_target"
    before=$(ledger_count "$ledger")
    "$scripts_dir/submit-estimates.sh" "$algorithm"
    jobid=$(new_job_from_ledger "$ledger" "$before")
    record_job production-array "$jobid"
    wait_for_job "$jobid"

    current_stage=stage2-production-benchmark
    record_status STARTED "profiling production array $jobid"
    profile_array_job "$jobid" "$production_expected" "$production_target" \
      "$algorithm-stage2-production-$jobid" "$stage2/benchmark/production-$jobid"
    record_status COMPLETED "production benchmark written"
    record_artifact benchmark "$stage2/benchmark/production-$jobid"

    current_stage=stage2-production-validation
    record_status STARTED "validating complete Stage 2 output tree"
    "$scripts_dir/validate-stage2.py" "$algorithm"
    record_status COMPLETED "Stage 2 validation passed"
    record_artifact stage2-output "$stage2/output"

    current_stage=stage3-build
    current_jobid=
    current_job_state=
    record_status STARTED "submitting Stage 3 driver"
    load_hats_environment
    ledger=$stage3/submitted-job-ids.tsv
    before=$(ledger_count "$ledger")
    "$scripts_dir/submit-hats.sh" "$algorithm"
    jobid=$(new_job_from_ledger "$ledger" "$before")
    run_tag=$(tail -n 1 "$ledger" | cut -f4)
    test -n "$run_tag"
    record_job stage3-driver "$jobid" "$run_tag"
    wait_for_job "$jobid"

    current_stage=stage3-validation
    record_status STARTED "validating HATS with nested PDFs"
    "$scripts_dir/validate-hats.py" "$algorithm"
    record_status COMPLETED "Stage 3 validation passed"

    benchmark_dir=$stage3/benchmark/$run_tag
    driver_logs=$stage3/log/driver-$run_tag
    worker_logs=$stage3/log/dask-$run_tag
    current_stage=stage3-driver-benchmark
    record_status STARTED "profiling Stage 3 driver $jobid"
    profile_regular_job "$jobid" 1 "$algorithm-stage3-driver-$jobid" \
      "$benchmark_dir/driver" ''
    record_status COMPLETED "driver benchmark written"
    record_artifact benchmark "$benchmark_dir/driver"

    current_stage=stage3-worker-benchmark
    record_status STARTED "collecting and profiling Dask workers"
    "$scripts_dir/collect-hats-worker-job-ids.sh" "$benchmark_dir" "$worker_logs"
    worker_count=$(wc -l < "$benchmark_dir/worker-job-ids.txt")
    test "$worker_count" -gt 0
    "$profile" \
      --job-id-file "$benchmark_dir/worker-job-ids.txt" \
      --expected-jobs "$worker_count" \
      --concurrency-target "$PZ_HATS_MAX_WORKERS" \
      --cluster-context-nodes 'apl[01-28]' \
      --label "$algorithm-stage3-workers-$run_tag" \
      --output-dir "$benchmark_dir/workers" \
      --capture-slurm-snapshot
    test -f "$driver_logs/driver-resource-usage.log"
    record_status COMPLETED "$worker_count worker jobs profiled"
    record_artifact benchmark "$benchmark_dir/workers"
    record_artifact hats-with-pdfs "$stage3/output/pz-$algorithm-gaap1p0-clipped-hats"

    current_stage=algorithm-complete
    current_jobid=
    current_job_state=
    record_status COMPLETED "Stages 1, 2, and 3 validated and profiled"
}

current_stage=preflight
record_status STARTED "checking workflow prerequisites"
validate_positive_integer PZ_BATCH_JOB_TIMEOUT_SECONDS "$PZ_BATCH_JOB_TIMEOUT_SECONDS"
validate_positive_integer PZ_BATCH_POLL_SECONDS "$PZ_BATCH_POLL_SECONDS"
validate_positive_integer PZ_BATCH_MIN_FREE_GIB "$PZ_BATCH_MIN_FREE_GIB"
validate_positive_integer PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB "$PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB"
validate_positive_integer PZ_HATS_MIN_WORKERS "$PZ_HATS_MIN_WORKERS"
validate_positive_integer PZ_HATS_MAX_WORKERS "$PZ_HATS_MAX_WORKERS"
validate_positive_integer PZ_HATS_SCALE_DOWN_DELAY "$PZ_HATS_SCALE_DOWN_DELAY"
validate_positive_number PZ_HATS_MARGIN_ARCSEC "$PZ_HATS_MARGIN_ARCSEC"
test "$PZ_HATS_MIN_WORKERS" -le "$PZ_HATS_MAX_WORKERS"
test -r "$gaap_env"
test -r "$hats_env"
test -x "$profile"
command -v sacct >/dev/null
command -v sbatch >/dev/null
command -v scancel >/dev/null
load_gaap_environment

IFS=',' read -r -a algorithms <<< "$PZ_BATCH_ALGORITHMS"
validate_algorithm_order

training_data=$PZ_DP2_ROOT/common/training/train_clipped_v3_gaap1p0.hdf5
training_freeze=$PZ_DP2_ROOT/common/training/environment-freeze.txt
test -f "$training_data"
test -f "$training_freeze"
"$PZ_PY" -m pip freeze > "$PZ_BATCH_RUN_DIR/gaap-environment-freeze.txt"
diff -u "$training_freeze" "$PZ_BATCH_RUN_DIR/gaap-environment-freeze.txt"
source "$scripts_dir/algorithm-config.sh"
for algorithm in "${algorithms[@]}"; do
    case "$algorithm" in
        fzboost)
            reference_hash=33e0fcfa29c10c4305e6de1c739a4765cc1291110d08d8c23674af8de6d8b127
            reference_model=$PZ_DP2_ROOT/fzboost/stage1/model/reference/model_dp2_v3p1_fzboost_dp2_6band_gold.pickle
            ;;
        dnf)
            reference_hash=bd677d456dba126ef3b47814f34559a280dc3a92d58d58f598f7a21a8cd99ab4
            reference_model=$PZ_DP2_ROOT/dnf/stage1/model/reference/model_dp2_v3p1_dnf_dp2_6band_gold.pickle
            ;;
        bpz)
            reference_hash=4872eacee26ae6a5d3716cccd423c7e30b611ed7216e373153058ed59b985170
            reference_model=$PZ_DP2_ROOT/bpz/stage1/model/reference/model_dp2_v3p1_bpz_dp2_6band_gold.pickle
            ;;
    esac
    printf '%s  %s\n' "$reference_hash" "$reference_model" | sha256sum --check
    if [ "$algorithm" = bpz ]; then
        dp2_algorithm_config bpz
        "$scripts_dir/validate-bpz-reference-data.py" \
          "$PZ_BPZ_DATA_ROOT" "$PZ_BPZ_SPECTRA_FILE" "$PZ_BPZ_EXPECTED_SEDS"
    fi
done
PZ_DP2_ROOT="$PZ_DP2_ROOT" PZ_DP2_INPUT_DATASET="$PZ_DP2_INPUT_DATASET" \
  "$scripts_dir/prepare-estimation-manifests.sh" all

require_free_gib "$PZ_BATCH_MIN_FREE_GIB"

{
    printf 'run_tag=%s\n' "$PZ_BATCH_RUN_TAG"
    printf 'controller_job_id=%s\n' "${SLURM_JOB_ID:-not-running-under-slurm}"
    printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
    printf 'host=%s\n' "$(hostname)"
    printf 'repository=%s\n' "$repo_dir"
    printf 'git_commit=%s\n' "$(git -C "$repo_dir" rev-parse HEAD)"
    printf 'dp2_root=%s\n' "$PZ_DP2_ROOT"
    printf 'input_dataset=%s\n' "$PZ_DP2_INPUT_DATASET"
    printf 'algorithms=%s\n' "$PZ_BATCH_ALGORITHMS"
    printf 'poll_seconds=%s\n' "$PZ_BATCH_POLL_SECONDS"
    printf 'job_timeout_seconds=%s\n' "$PZ_BATCH_JOB_TIMEOUT_SECONDS"
    printf 'minimum_free_gib=%s\n' "$PZ_BATCH_MIN_FREE_GIB"
    printf 'minimum_free_per_algorithm_gib=%s\n' "$PZ_BATCH_MIN_FREE_PER_ALGORITHM_GIB"
    printf 'hats_min_workers=%s\n' "$PZ_HATS_MIN_WORKERS"
    printf 'hats_max_workers=%s\n' "$PZ_HATS_MAX_WORKERS"
    printf 'hats_scale_down_delay=%s\n' "$PZ_HATS_SCALE_DOWN_DELAY"
    printf 'hats_margin_arcsec=%s\n' "$PZ_HATS_MARGIN_ARCSEC"
    df -h "$PZ_DP2_ROOT"
    df -ih "$PZ_DP2_ROOT"
} > "$context_file"
record_status COMPLETED "preflight passed"

for algorithm in "${algorithms[@]}"; do
    run_algorithm "$algorithm"
done

current_algorithm=all
current_stage=batch-complete
current_jobid=
current_job_state=
record_status COMPLETED "all requested algorithms completed"
{
    echo "# DP2 v3 serial production summary"
    echo
    echo "- Run tag: \`$PZ_BATCH_RUN_TAG\`"
    echo "- Controller job: \`${SLURM_JOB_ID:-not-running-under-slurm}\`"
    echo "- Completed at: \`$(date --iso-8601=seconds)\`"
    echo "- Algorithm order: \`$PZ_BATCH_ALGORITHMS\`"
    echo "- Result: **SUCCESS**"
    echo
    echo "Every requested algorithm completed Stages 1, 2, and 3, including"
    echo "validation and Slurm benchmarks. Per-algorithm artifacts remain in"
    echo "their standard individual workflow directories."
    echo
    echo "- Status ledger: \`$status_file\`"
    echo "- Job ledger: \`$jobs_file\`"
    echo "- Artifact index: \`$artifacts_file\`"
    echo "- Run context: \`$context_file\`"
} > "$summary_file"
touch "$PZ_BATCH_RUN_DIR/SUCCESS"
rm -f "$active_file"
echo "DP2 v3 serial production completed successfully: $PZ_BATCH_RUN_DIR"
