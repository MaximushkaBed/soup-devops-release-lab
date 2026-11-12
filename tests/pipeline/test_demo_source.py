"""A consumer must compare a demonstration artifact with the same patched candidate."""

import subprocess
import sys
from pathlib import Path

import pytest

from tools import check_wheel

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("fault", ["python310", "windows"])
def test_demo_artifact_requires_the_same_candidate_source(tmp_path, monkeypatch, fault):
    producer, consumer = tmp_path / "producer", tmp_path / "consumer"
    # Dispatch intentionally mutates the working tree before pytest. Keep this
    # regression's baseline independent of whichever fault that run is demonstrating.
    source_names = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "src"], cwd=ROOT, text=True
    ).split("\0")
    names = ["pyproject.toml", "README.md", "LICENSE", *filter(None, source_names)]
    for checkout in (producer, consumer):
        for name in names:
            target = checkout / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT))

    def inject(checkout):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/inject_bug.py"), fault],
            cwd=checkout,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        # Explicitly exercise the cross-OS byte contract, beyond newline-normalized reads.
        assert b"\r\n" not in (checkout / "src/soup_release_lab/cli.py").read_bytes()

    inject(producer)
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(tmp_path / "dist"),
        ],
        cwd=producer,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    wheel = next((tmp_path / "dist").glob("*.whl"))
    monkeypatch.setattr(check_wheel, "ROOT", producer)
    check_wheel.check(wheel)
    monkeypatch.setattr(check_wheel, "ROOT", consumer)
    with pytest.raises(ValueError, match="Wheel/source bytes differ: cli.py"):
        check_wheel.check(wheel)
    inject(consumer)
    check_wheel.check(wheel)
