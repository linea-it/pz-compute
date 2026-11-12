from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "doc" / "dp2_v3" / "scripts"
SUBMIT = SCRIPTS / "submit-production-batch.sh"
RUNNER = SCRIPTS / "run-production-batch.sh"
TRAIN_SUBMIT = SCRIPTS / "submit-training.sh"
TRAIN_RUNNER = SCRIPTS / "run-one-train.sbatch"
ESTIMATE_RUNNER = SCRIPTS / "run-one-estimate.sbatch"
HATS_SUBMIT = SCRIPTS / "submit-hats.sh"
HATS_RUNNER = SCRIPTS / "run-one-hats.sbatch"
WORKER_IDS = SCRIPTS / "collect-hats-worker-job-ids.sh"


def test_batch_shell_scripts_are_syntactically_valid_and_executable():
    subprocess.run(
        ["bash", "-n", str(SUBMIT), str(RUNNER)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert SUBMIT.stat().st_mode & 0o111
    assert RUNNER.stat().st_mode & 0o111
    assert WORKER_IDS.stat().st_mode & 0o111


def test_batch_submit_help_documents_serial_fail_fast_contract():
    result = subprocess.run(
        [str(SUBMIT), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "fzboost, then dnf, then bpz" in result.stderr
    assert "serial, fail-fast workflow" in result.stderr


def test_batch_runner_uses_named_serial_submissions_and_stage_order():
    source = RUNNER.read_text(encoding="utf-8")
    submit_source = SUBMIT.read_text(encoding="utf-8")
    assert "${PZ_BATCH_ALGORITHMS:-fzboost,dnf,bpz}" in source
    assert "${PZ_BATCH_ALGORITHMS//:/,}" in source
    assert "${PZ_BATCH_ALGORITHMS//,/:}" in submit_source
    assert 'PZ_BATCH_ALGORITHMS="$controller_algorithms"' in submit_source
    assert "--nodes=1" in submit_source
    assert "--nodelist" not in submit_source
    assert "--exclude" not in submit_source
    assert '"$scripts_dir/submit-training.sh" "$algorithm"' in source
    assert '"$scripts_dir/submit-estimates.sh" "$algorithm"' in source
    assert '"$scripts_dir/submit-hats.sh" "$algorithm"' in source
    assert "submit-training.sh\" all" not in source
    assert "submit-estimates.sh\" all" not in source
    assert "submit-hats.sh\" all" not in source

    ordered_stages = [
        "current_stage=stage1-training",
        "current_stage=stage1-benchmark",
        "current_stage=stage1-validation",
        "current_stage=stage2-smoke",
        "current_stage=stage2-pilot",
        "current_stage=stage2-pilot-benchmark",
        "current_stage=stage2-pilot-validation",
        "current_stage=stage2-production",
        "current_stage=stage2-production-benchmark",
        "current_stage=stage2-production-validation",
        "current_stage=stage3-build",
        "current_stage=stage3-validation",
        "current_stage=stage3-driver-benchmark",
        "current_stage=stage3-worker-benchmark",
    ]
    positions = [source.index(stage) for stage in ordered_stages]
    assert positions == sorted(positions)


def test_stage1_is_sized_for_old_nodes_without_restricting_placement():
    submit_source = TRAIN_SUBMIT.read_text(encoding="utf-8")
    train_runner_source = TRAIN_RUNNER.read_text(encoding="utf-8")
    runner_source = RUNNER.read_text(encoding="utf-8")
    assert "--nodelist" not in submit_source
    assert "--exclude" not in submit_source + train_runner_source
    assert "--cpus-per-task=52" in submit_source
    assert "--mem=113984M" in submit_source
    assert "--cpus-per-task=1 --mem=8G" in submit_source
    assert '"$stage1/benchmark/training-$jobid" \'apl[01-28]\'' in runner_source


def test_stage2_and_stage3_are_contention_tolerant_and_unrestricted():
    estimate_source = ESTIMATE_RUNNER.read_text(encoding="utf-8")
    hats_submit_source = HATS_SUBMIT.read_text(encoding="utf-8")
    hats_runner_source = HATS_RUNNER.read_text(encoding="utf-8")
    runner_source = RUNNER.read_text(encoding="utf-8")
    combined = estimate_source + hats_submit_source + hats_runner_source
    assert "--nodelist" not in combined
    assert "--exclude" not in combined
    assert "PZ_HATS_MIN_WORKERS=${PZ_HATS_MIN_WORKERS:-1}" in hats_submit_source
    assert "PZ_HATS_MARGIN_ARCSEC=${PZ_HATS_MARGIN_ARCSEC:-5}" in hats_submit_source
    assert 'PZ_HATS_MARGIN_ARCSEC="$PZ_HATS_MARGIN_ARCSEC"' in hats_submit_source
    assert 'margin_threshold_arcsec=%s' in hats_runner_source
    assert '--slurm-minimum-jobs="$PZ_HATS_MIN_WORKERS"' in hats_runner_source
    assert "--slurm-cores=2" in hats_runner_source
    assert "--slurm-processes=1" in hats_runner_source
    assert "--slurm-memory=40GiB" in hats_runner_source
    assert '--slurm-job-name="$worker_job_name"' in hats_runner_source
    assert "wait_for_workers" not in hats_runner_source
    assert runner_source.count("--cluster-context-nodes 'apl[01-28]'") == 2
    assert runner_source.count("--capture-slurm-snapshot") == 3


def test_worker_id_collection_includes_accounting_only_jobs(tmp_path):
    benchmark = tmp_path / "benchmark"
    logs = tmp_path / "logs"
    fake_bin = tmp_path / "bin"
    benchmark.mkdir()
    logs.mkdir()
    fake_bin.mkdir()
    job_name = "pz3-fzboost-production-test"
    (benchmark / "worker-job-name.txt").write_text(job_name + "\n", encoding="utf-8")
    (benchmark / "run-context.log").write_text(
        "driver_start_time=2026-01-01T10:00:00\n", encoding="utf-8"
    )
    (logs / "slurm-700.out").write_text("started\n", encoding="utf-8")
    fake_sacct = fake_bin / "sacct"
    fake_sacct.write_text(
        f"#!/bin/sh\nprintf '701|{job_name}|CANCELLED|\\n'\n", encoding="utf-8"
    )
    fake_sacct.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    subprocess.run(
        [str(WORKER_IDS), str(benchmark), str(logs)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert (benchmark / "worker-job-ids.txt").read_text(encoding="utf-8") == "700\n701\n"


def test_batch_runner_has_durable_success_and_failure_outputs():
    source = RUNNER.read_text(encoding="utf-8")
    for artifact in (
        "status.tsv",
        "jobs.tsv",
        "artifacts.tsv",
        "failure-report.md",
        "summary.md",
        'touch "$PZ_BATCH_RUN_DIR/FAILED"',
        'touch "$PZ_BATCH_RUN_DIR/SUCCESS"',
    ):
        assert artifact in source
    assert "require_fresh_downstream_tree" in source
    assert "will not mix them with a retrained model" in source


def test_batch_runner_writes_failure_report_for_invalid_algorithm(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for command in ("sacct", "sbatch", "scancel"):
        executable = fake_bin / command
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)

    run_dir = tmp_path / "run"
    root = tmp_path / "dp2-v3"
    run_dir.mkdir()
    root.mkdir()
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "PZ_BATCH_RUN_TAG": "test-invalid-algorithm",
            "PZ_BATCH_RUN_DIR": str(run_dir),
            "PZ_DP2_ROOT": str(root),
            "PZ_DP2_INPUT_DATASET": str(tmp_path / "input"),
            "PZ_BATCH_ALGORITHMS": "invalid",
            "PZ_GAAP_ENV_SCRIPT": "/dev/null",
            "PZ_HATS_ENV_SCRIPT": "/dev/null",
        }
    )

    result = subprocess.run(
        [str(RUNNER)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode != 0
    assert (run_dir / "FAILED").is_file()
    report = (run_dir / "failure-report.md").read_text(encoding="utf-8")
    assert "Algorithm: `preflight`" in report
    assert "Stage: `preflight`" in report
    assert "return 2" in report
    assert "Unsupported official batch algorithm: invalid" in result.stderr
