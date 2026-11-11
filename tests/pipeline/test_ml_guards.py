"""Reject incomplete evidence and unsafe GPU claims without requiring ML dependencies."""

import copy
import json
import os
import subprocess
import sys

import pytest

from tools import ml_lab
from tools.ml_lab import ROOT, inject, validate_report


def valid_report():
    return {
        "status": "passed",
        "backend": "cpu",
        "native_cuda": False,
        "checks": [
            {"name": "forward", "status": "passed"},
            {
                "name": "activation-forward-backward",
                "status": "passed",
                "finite_difference": True,
                "cases": [
                    {"dtype": dtype, "elements": n}
                    for dtype in ("float32", "float16", "bfloat16")
                    for n in (0, 1, 7, 257, 1025)
                ],
            },
            {
                "name": "lora-two-step",
                "status": "passed",
                "steps": 2,
                "frozen_base": "unchanged",
                "zero_initialized_b": True,
                "losses": [0.1, 0.09],
            },
        ],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(native_cuda=True),
        lambda r: r.update(backend="cuda"),
        lambda r: r.update(status="running"),
        lambda r: r["checks"].pop(),
        lambda r: r["checks"][1].update(cases=[]),
        lambda r: r["checks"][1].update(finite_difference=False),
        lambda r: r["checks"][2].update(steps=1),
        lambda r: r["checks"][2].update(losses=[float("nan"), 0.1]),
        lambda r: r["checks"][2].update(frozen_base="changed"),
    ],
)
def test_incomplete_training_evidence_is_rejected(mutation):
    report = valid_report()
    validate_report(report, "cpu", "training")
    mutation(report)
    with pytest.raises(ValueError):
        validate_report(report, "cpu", "training")


def test_interpreter_cannot_be_promoted_to_native_cuda():
    report = copy.deepcopy(valid_report())
    report.update(backend="interpreter")
    with pytest.raises(ValueError):
        validate_report(report, "cuda", "training")


def test_fault_patch_refuses_changed_source(tmp_path):
    (tmp_path / "pyproject.toml").write_text("changed upstream")
    with pytest.raises(ValueError, match="ambiguous"):
        inject(tmp_path, "missing-resource")


def test_cuda_interpreter_conflict_fails_before_torch_import(tmp_path):
    report = tmp_path / "report.json"
    source = ROOT / "fixtures/training/src"
    command = [
        sys.executable,
        "-I",
        "-O",
        "-c",
        (
            "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));"
            "runpy.run_module('soup_training_probe.cli',run_name='__main__')"
        ),
        str(source),
        "--backend",
        "cuda",
        "--report",
        str(report),
    ]
    result = subprocess.run(
        command,
        env={**os.environ, "TRITON_INTERPRET": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(report.read_text())
    assert result.returncode == 3, result.stderr
    assert data["error"]["code"] == "interpreter-is-not-gpu"
    assert data["native_cuda"] is False


def test_hash_inventory_covers_both_stacks_and_all_supported_cpu_targets():
    catalog = json.loads((ROOT / "requirements/ml-wheels.json").read_text())
    expected = {f"3.{minor}-{system}" for minor in (11, 12, 13) for system in ("linux", "win32")}
    for profile in catalog["profiles"].values():
        assert set(profile["torch_wheels"]) == expected
        for wheel in profile["torch_wheels"].values():
            assert wheel["url"].startswith("https://download-r2.pytorch.org/whl/cpu/")
            assert len(bytes.fromhex(wheel["sha256"])) == 32
        assert not any("nvidia-" in requirement for requirement in profile["torch_requires_dist"])


@pytest.mark.parametrize("action", ["test", "bare", "gpu_guard"])
def test_existing_report_is_rejected_before_running_anything(tmp_path, monkeypatch, action):
    report = tmp_path / "previous-pass.json"
    original = json.dumps(valid_report())
    report.write_text(original)

    def unexpected(*args, **kwargs):
        pytest.fail(
            "An existing report must be rejected before inspecting or running the candidate"
        )

    monkeypatch.setattr(ml_lab, "verify", unexpected)
    monkeypatch.setattr(ml_lab, "run", unexpected)
    with pytest.raises(ValueError, match="Report already exists"):
        if action == "test":
            ml_lab.test(tmp_path / "bundle", tmp_path / "profile", "cpu", "wheel", report)
        elif action == "bare":
            ml_lab.bare(tmp_path / "bundle", report)
        else:
            ml_lab.gpu_guard(tmp_path / "profile", report)
    assert report.read_text() == original
