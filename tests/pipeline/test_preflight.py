"""A failed local gate must preserve its output and a machine-readable failure."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.preflight import Recorder
from tools.smoke import invoke

ROOT = Path(__file__).resolve().parents[2]


def test_failed_command_keeps_stdout_stderr_and_exit_code(tmp_path):
    recorder = Recorder(tmp_path)
    with pytest.raises(RuntimeError, match="exit 7"):
        recorder.step(
            "failure",
            [
                sys.executable,
                "-c",
                "import sys; print('out'); print('cause', file=sys.stderr); sys.exit(7)",
            ],
        )
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["status"] == "failed"
    step = summary["steps"][0]
    assert step["exit_code"] == 7
    log = (tmp_path / step["log"]).read_text()
    assert "out" in log and "cause" in log


def test_timeout_keeps_a_failed_report(tmp_path):
    recorder = Recorder(tmp_path)
    with pytest.raises(RuntimeError, match="exit 124"):
        recorder.step("timeout", [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert "TIMEOUT" in (tmp_path / summary["steps"][0]["log"]).read_text()


def test_missing_tool_fails_instead_of_skipping(tmp_path):
    recorder = Recorder(tmp_path)
    with pytest.raises(RuntimeError, match="exit 127"):
        recorder.step("missing", [str(tmp_path / "not-installed")])
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["steps"][0]["status"] == "failed"


@pytest.mark.skipif(sys.platform != "linux", reason="Inspect Linux child-process state")
def test_timeout_stops_grandchildren_as_well_as_the_command(tmp_path):
    pid_file = tmp_path / "grandchild.pid"
    child = (
        "import pathlib, subprocess, sys, time; "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
    )
    with pytest.raises(RuntimeError, match="exit 124"):
        Recorder(tmp_path).step("tree", [sys.executable, "-c", child, str(pid_file)], timeout=1)
    pid = int(pid_file.read_text())
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    # An exited child can briefly remain as a zombie until its new parent reaps it.
    assert Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"


def test_artifact_glob_does_not_silently_skip_a_requested_sdist(tmp_path):
    wheel = tmp_path / "candidate.whl"
    wheel.touch()
    result = subprocess.run(
        [sys.executable, "tools/test_artifact.py", str(wheel), str(tmp_path / "*.tar.gz")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "No matching artifacts" in result.stderr
    assert "*.tar.gz" in result.stderr


def test_cli_failure_keeps_the_underlying_diagnostic(capsys):
    with pytest.raises(ValueError, match="got 3"):
        invoke(
            Path(sys.executable),
            "-c",
            "import sys; print('root cause', file=sys.stderr); sys.exit(3)",
        )
    assert "root cause" in capsys.readouterr().err


@pytest.mark.parametrize(
    "change",
    [
        {"greeting": "Wrong"},
        {"version": "0.9.4"},
        {"user": ""},
        {"timestamp": "2026-01-01T00:00:00"},
        {"timestamp": "2026-01-01T00:00:00+01:00"},
    ],
    ids=["greeting", "version", "user", "naive-time", "non-utc-time"],
)
def test_broken_report_is_rejected_under_optimized_python(change):
    data = {
        "greeting": "Hello, Soup!",
        "version": "0.9.3",
        "user": "user",
        "timestamp": "2026-01-01T00:00:00+00:00",
        **change,
    }
    result = subprocess.run(
        [
            sys.executable,
            "-O",
            "-c",
            "import json, sys; from tools.smoke import validate_report; "
            "validate_report(json.loads(sys.argv[1]), 'Soup')",
            json.dumps(data),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "ValueError" in result.stderr
