"""A green gate requires every expected job, not merely absence of failures."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("optimized", [False, True])
@pytest.mark.parametrize(
    ("needs", "expected"),
    [
        ({"build": {"result": "success"}, "tests": {"result": "success"}}, None),
        ({"build": {"result": "success"}, "tests": {"result": "skipped"}}, "did not succeed"),
        ({"build": {"result": "success"}, "tests": {"result": "cancelled"}}, "did not succeed"),
        ({"build": {"result": "success"}, "tests": {"result": "failure"}}, "did not succeed"),
        ({"build": {"result": "success"}, "tests": {"result": "neutral"}}, "did not succeed"),
        ({"build": {"result": "success"}, "tests": {}}, "did not succeed"),
        ({"build": {"result": "success"}}, "inventory differs"),
        ({}, "inventory differs"),
        ([], "inventory differs"),
    ],
)
def test_gate_rejects_missing_or_unsuccessful_jobs(optimized, needs, expected):
    result = subprocess.run(
        [sys.executable, *(["-O"] if optimized else []), "tools/check_jobs.py", "build", "tests"],
        cwd=ROOT,
        env={**os.environ, "NEEDS_JSON": json.dumps(needs)},
        text=True,
        capture_output=True,
        timeout=15,
    )
    if expected is None:
        assert result.returncode == 0, result.stderr
        assert "every required job succeeded" in result.stdout
    else:
        assert result.returncode != 0
        assert expected in result.stderr
