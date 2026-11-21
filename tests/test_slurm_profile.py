import csv
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

FIELDS = [
    "JobIDRaw", "JobID", "JobName", "Partition", "Account", "QOS",
    "State", "ExitCode", "Submit",
    "Eligible", "Start", "End", "ElapsedRaw", "AllocCPUS", "CPUTimeRAW",
    "TotalCPU", "ReqMem", "MaxRSS", "NodeList",
]


def test_slurm_profile_builds_array_metrics(tmp_path):
    source = Path(__file__).parents[1] / "performance" / "slurm" / "slurm-profile"
    sacct = tmp_path / "input.tsv"
    rows = [
        ["100", "100", "array", "cpu_photoz", "hpc-photoz", "normal", "COMPLETED", "0:0", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:01:00", "2026-01-01T10:06:00", "300", "1", "300", "00:04:30", "40Gn", "", ""],
        ["101", "100_0", "array", "cpu_photoz", "hpc-photoz", "normal", "COMPLETED", "0:0", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:01:00", "2026-01-01T10:03:00", "120", "1", "120", "", "40Gn", "", "apl01"],
        ["101.batch", "100_0.batch", "batch", "", "", "", "COMPLETED", "0:0", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:01:00", "2026-01-01T10:03:00", "120", "1", "120", "00:01:30", "", "1048576K", "apl01"],
        ["102", "100_1", "array", "cpu_photoz", "hpc-photoz", "normal", "COMPLETED", "0:0", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:02:00", "2026-01-01T10:06:00", "240", "1", "240", "", "40Gn", "", "apl02"],
        ["102.batch", "100_1.batch", "batch", "", "", "", "COMPLETED", "0:0", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:02:00", "2026-01-01T10:06:00", "240", "1", "240", "00:03:00", "", "2097152K", "apl02"],
    ]
    with sacct.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(rows)

    job_ids = tmp_path / "job-ids.txt"
    job_ids.write_text("100\n", encoding="utf-8")
    metadata = tmp_path / "metadata.tsv"
    metadata.write_text(
        "array_task_id\tinput_path\tinput_bytes\tinput_rows\n"
        "0\t/input/a.parquet\t1000\t10\n"
        "1\t/input/b.parquet\t2000\t20\n",
        encoding="utf-8",
    )
    output = tmp_path / "metrics"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for command in ("scontrol", "squeue"):
        executable = fake_bin / command
        executable.write_text(f"#!/bin/sh\necho '{command} snapshot'\n", encoding="utf-8")
        executable.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    subprocess.run(
        [
            sys.executable,
            str(source),
            "--sacct-file", str(sacct),
            "--job-id-file", str(job_ids),
            "--expected-jobs", "2",
            "--concurrency-target", "2",
            "--label", "test-array",
            "--output-dir", str(output),
            "--task-metadata-file", str(metadata),
            "--context", "algorithm=test",
            "--context-file", str(metadata),
            "--storage-path", str(tmp_path),
            "--capture-slurm-snapshot",
            "--fail-on-unsuccessful",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["logical_jobs"] == 2
    assert summary["successful_jobs"] == 2
    assert summary["first_start_to_last_end_seconds"] == 300
    assert summary["concurrency"]["peak"] == 2
    assert summary["concurrency"]["mean"] == 1.2
    assert summary["max_rss_gib"]["maximum"] == 2
    assert summary["cpu"]["efficiency_percent"] == 75
    assert summary["slurm"] == {
        "accounts": ["hpc-photoz"],
        "partitions": ["cpu_photoz"],
        "qos": ["normal"],
    }

    assert (output / "sacct.tsv").is_file()
    assert (output / "sacct.tsv.gz").is_file()
    assert (output / "tasks.tsv").is_file()
    assert (output / "tasks.tsv.gz").is_file()
    assert (output / "task-metadata.tsv").is_file()
    assert (output / "benchmark-context.json").is_file()
    assert (output / "time-profile.tsv").is_file()
    assert (output / "summary.log").is_file()
    assert summary["slurm_snapshot"]["available"] is True
    assert (output / "slurm-snapshot" / "nodes.txt").is_file()
    assert (output / "slurm-snapshot" / "config.txt").is_file()
    assert "<svg" in (output / "time-profile.svg").read_text(encoding="utf-8")
    ET.parse(output / "time-profile.svg")
    with gzip.open(output / "tasks.tsv.gz", "rt", encoding="utf-8") as stream:
        tasks = list(csv.DictReader(stream, delimiter="\t"))
    assert tasks[0]["metadata_input_path"] == "/input/a.parquet"
    assert tasks[1]["metadata_input_bytes"] == "2000"
    assert summary["task_metadata"]["matched_tasks"] == 2
    assert abs(
        summary["task_metadata"]["correlations"]["input_bytes"][
            "duration_seconds"
        ]["pearson"]
        - 1
    ) < 1e-12
    context = json.loads((output / "benchmark-context.json").read_text())
    assert context["values"] == {"algorithm": "test"}
    assert context["files"][0]["sha256"]
    assert context["storage"][0]["available_bytes"] > 0


def test_slurm_profile_accepts_regular_worker_job_ids(tmp_path):
    source = Path(__file__).parents[1] / "performance" / "slurm" / "slurm-profile"
    sacct = tmp_path / "workers.tsv"
    rows = [
        ["200", "200", "dask-worker", "cpu_photoz", "hpc-photoz", "normal", "COMPLETED", "0:0", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:01:00", "2026-01-01T10:05:00", "240", "8", "1920", "", "40Gn", "", "apl17"],
        ["200.batch", "200.batch", "batch", "", "", "", "COMPLETED", "0:0", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:01:00", "2026-01-01T10:05:00", "240", "8", "1920", "00:20:00", "", "4194304K", "apl17"],
        ["201", "201", "dask-worker", "cpu_photoz", "hpc-photoz", "normal", "CANCELLED by 1", "0:15", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:02:00", "2026-01-01T10:06:00", "240", "8", "1920", "", "40Gn", "", "apl18"],
        ["201.batch", "201.batch", "batch", "", "", "", "CANCELLED", "0:15", "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:02:00", "2026-01-01T10:06:00", "240", "8", "1920", "00:10:00", "", "3145728K", "apl18"],
    ]
    with sacct.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(rows)

    job_ids = tmp_path / "worker-job-ids.txt"
    job_ids.write_text("200\n201\n", encoding="utf-8")
    output = tmp_path / "worker-metrics"
    subprocess.run(
        [
            sys.executable,
            str(source),
            "--sacct-file", str(sacct),
            "--job-id-file", str(job_ids),
            "--expected-jobs", "2",
            "--concurrency-target", "2",
            "--output-dir", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["logical_jobs"] == 2
    assert summary["successful_jobs"] == 1
    assert summary["unsuccessful_jobs"] == 1
    assert summary["states"] == {"CANCELLED": 1, "COMPLETED": 1}
    assert summary["max_rss_gib"]["maximum"] == 4


def test_slurm_profile_collects_io_metrics_from_batch_step(tmp_path):
    source = Path(__file__).parents[1] / "performance" / "slurm" / "slurm-profile"
    sacct = tmp_path / "io.tsv"
    io_fields = FIELDS[:-1] + [
        "AveDiskRead", "AveDiskWrite", "MaxDiskRead", "MaxDiskWrite", "NodeList"
    ]
    rows = [
        ["300", "300", "io-job", "cpu", "account", "normal", "COMPLETED", "0:0",
         "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:01:00",
         "2026-01-01T10:03:00", "120", "2", "240", "", "4Gn", "", "", "", "", "", "n01"],
        ["300.batch", "300.batch", "batch", "", "", "", "COMPLETED", "0:0",
         "2026-01-01T10:00:00", "2026-01-01T10:00:00", "2026-01-01T10:01:00",
         "2026-01-01T10:03:00", "120", "2", "240", "00:03:00", "", "1048576K",
         "524288K", "262144K", "2097152K", "1048576K", "n01"],
    ]
    with sacct.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(io_fields)
        writer.writerows(rows)

    output = tmp_path / "io-metrics"
    subprocess.run(
        [sys.executable, str(source), "--sacct-file", str(sacct), "--job-id", "300",
         "--output-dir", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == 4
    assert summary["io"]["jobs_with_accounting"] == 1
    assert summary["io"]["max_disk_read_gib"]["maximum"] == 2
    assert summary["io"]["max_disk_write_gib"]["maximum"] == 1

    with (output / "tasks.tsv").open(encoding="utf-8", newline="") as stream:
        task = next(csv.DictReader(stream, delimiter="\t"))
    assert float(task["ave_disk_read_gib"]) == 0.5
    assert float(task["ave_disk_write_gib"]) == 0.25
    assert float(task["max_disk_read_gib"]) == 2
    assert float(task["max_disk_write_gib"]) == 1


def test_slurm_profile_reports_scheduler_and_cluster_context(tmp_path):
    source = Path(__file__).parents[1] / "performance" / "slurm" / "slurm-profile"
    fields = FIELDS + [
        "TimelimitRaw", "NNodes", "ReqCPUS", "ReqTRES", "AllocTRES", "User"
    ]
    target = tmp_path / "target.tsv"
    target_row = [
        "400", "400", "target", "cpu_photoz", "hpc-photoz", "photoz",
        "COMPLETED", "0:0", "2026-01-01T10:00:00", "2026-01-01T10:01:00",
        "2026-01-01T10:03:00", "2026-01-01T10:13:00", "600", "2", "1200",
        "00:10:00", "40Gn", "20971520K", "apl01", "60", "1", "1",
        "billing=2,cpu=1,mem=40G,node=1", "billing=2,cpu=2,mem=40G,node=1",
        "app.photoz",
    ]
    context = tmp_path / "context.tsv"
    external_row = [
        "401", "401", "external", "cpu", "hpc-public", "public",
        "COMPLETED", "0:0", "2026-01-01T09:00:00", "2026-01-01T09:00:00",
        "2026-01-01T10:00:00", "2026-01-01T10:02:00", "120", "4", "480",
        "00:20:00", "8Gn", "4194304K", "apl02", "120", "1", "4",
        "billing=4,cpu=4,mem=8G,node=1", "billing=4,cpu=4,mem=8G,node=1",
        "other.user",
    ]
    for path, rows in ((target, [target_row]), (context, [target_row, external_row])):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
            writer.writerow(fields)
            writer.writerows(rows)

    output = tmp_path / "metrics"
    subprocess.run(
        [
            sys.executable, str(source), "--sacct-file", str(target),
            "--cluster-sacct-file", str(context), "--concurrency-target", "1",
            "--output-dir", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["pre_eligible_wait_seconds"]["maximum"] == 60
    assert summary["eligible_wait_seconds"]["maximum"] == 120
    assert summary["memory_peak_fraction_percent"]["maximum"] == 50
    assert abs(summary["timelimit_utilization_percent"]["maximum"] - 100 / 6) < 1e-6
    assert summary["cpu"]["average_used_per_job"]["maximum"] == 1
    assert summary["cluster_context"]["logical_jobs_overlapping"] == 1
    assert summary["cluster_context"]["peak_allocated_cpus"] == 4
    assert summary["cluster_context"]["accounts"] == {"hpc-public": 1}
    assert summary["cluster_context"]["window_start"] == "2026-01-01T10:00:00"
    assert summary["cluster_context"]["includes_initial_queue_wait"] is True
    assert (output / "cluster-context-sacct.tsv").is_file()
    assert (output / "cluster-context-profile.tsv").is_file()


def test_manifest_task_metadata_maps_array_ids_and_file_sizes(tmp_path):
    helper = (
        Path(__file__).parents[1]
        / "performance"
        / "slurm"
        / "manifest-task-metadata"
    )
    first = tmp_path / "first.dat"
    second = tmp_path / "second.dat"
    first.write_bytes(b"one")
    second.write_bytes(b"twenty")
    manifest = tmp_path / "inputs.txt"
    manifest.write_text(f"{first}\n{second}\n", encoding="utf-8")
    output = tmp_path / "metadata.tsv"

    subprocess.run(
        [sys.executable, str(helper), str(manifest), str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert [row["array_task_id"] for row in rows] == ["0", "1"]
    assert [row["input_bytes"] for row in rows] == ["3", "6"]
    assert [row["input_path"] for row in rows] == [str(first), str(second)]


def test_slurm_watch_samples_scheduler_steps_and_storage(tmp_path):
    watcher = Path(__file__).parents[1] / "performance" / "slurm" / "slurm-watch"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state_file = tmp_path / "squeue-count"
    squeue = fake_bin / "squeue"
    squeue.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in --version) echo 'slurm 1'; exit 0;; esac\n"
        f"if [ ! -f '{state_file}' ]; then touch '{state_file}'; "
        "printf '%s\\n' '500_[0-2%2]|PENDING|Resources' "
        "'500_3|RUNNING|None'; fi\n",
        encoding="utf-8",
    )
    sstat = fake_bin / "sstat"
    sstat.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in --version) echo 'slurm 1'; exit 0;; esac\n"
        "printf '500_3.batch|00:01|1024K|2048K|4096K|1K|2K|3K|4K|\\n'\n",
        encoding="utf-8",
    )
    sacct = fake_bin / "sacct"
    sacct.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in --version) echo 'slurm 1'; exit 0;; esac\n"
        "printf 'COMPLETED|\\n'\n",
        encoding="utf-8",
    )
    for executable in (squeue, sstat, sacct):
        executable.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    output = tmp_path / "monitor"

    subprocess.run(
        [
            sys.executable,
            str(watcher),
            "--job-id",
            "500",
            "--interval-seconds",
            "0.01",
            "--storage-path",
            str(tmp_path),
            "--context",
            "algorithm=test",
            "--output-dir",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    summary = json.loads((output / "monitor-summary.json").read_text())
    assert summary["status"] == "completed"
    assert summary["max_tasks_by_state"] == {"PENDING": 3, "RUNNING": 1}
    assert summary["max_tasks_by_reason"] == {"None": 1, "Resources": 3}
    assert summary["minimum_available_bytes_by_path"][str(tmp_path.resolve())] > 0
    assert (output / "step-samples.tsv").read_text().count("500_3.batch") >= 1


def test_slurm_watch_discovers_jobs_by_name(tmp_path):
    watcher = Path(__file__).parents[1] / "performance" / "slurm" / "slurm-watch"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state_file = tmp_path / "squeue-count"
    sstat_args = tmp_path / "sstat-args"
    squeue = fake_bin / "squeue"
    squeue.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in --version) echo 'slurm 1'; exit 0;; esac\n"
        f"if [ ! -f '{state_file}' ]; then touch '{state_file}'; "
        "printf '%s\\n' '700|RUNNING|None'; fi\n",
        encoding="utf-8",
    )
    sstat = fake_bin / "sstat"
    sstat.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in --version) echo 'slurm 1'; exit 0;; esac\n"
        f"printf '%s\\n' \"$*\" > '{sstat_args}'\n"
        "printf '700.batch|00:01|1024K|2048K|4096K|1K|2K|3K|4K|\\n'\n",
        encoding="utf-8",
    )
    sacct = fake_bin / "sacct"
    sacct.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in --version) echo 'slurm 1'; exit 0;; esac\n",
        encoding="utf-8",
    )
    for executable in (squeue, sstat, sacct):
        executable.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    output = tmp_path / "monitor"

    subprocess.run(
        [
            sys.executable,
            str(watcher),
            "--job-name",
            "adaptive-workers",
            "--interval-seconds",
            "0.01",
            "--output-dir",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    context = json.loads((output / "monitor-context.json").read_text())
    assert context["job_names"] == ["adaptive-workers"]
    assert "--jobs=700" in sstat_args.read_text()
    assert (output / "scheduler-samples.tsv").read_text().count("700") == 1
