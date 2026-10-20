import csv
import json
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
    output = tmp_path / "metrics"
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
            "--fail-on-unsuccessful",
        ],
        check=True,
        capture_output=True,
        text=True,
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
    assert (output / "tasks.tsv").is_file()
    assert (output / "time-profile.tsv").is_file()
    assert (output / "summary.log").is_file()
    assert "<svg" in (output / "time-profile.svg").read_text(encoding="utf-8")
    ET.parse(output / "time-profile.svg")


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
