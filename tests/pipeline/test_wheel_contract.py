"""Mutate real wheel contents, with both stale and freshly recomputed RECORDs."""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from wheel.wheelfile import WheelFile

ROOT = Path(__file__).resolve().parents[2]
INFO = "soup_release_lab_maximushkabed-0.9.3.dist-info"


def wheel_contents():
    files = {
        f"soup_release_lab/{name}": (ROOT / "src/soup_release_lab" / name).read_bytes()
        for name in ("__init__.py", "cli.py", "greeting.txt")
    }
    files.update(
        {
            f"{INFO}/METADATA": (
                b"Metadata-Version: 2.4\nName: soup-release-lab-maximushkabed\nVersion: 0.9.3\n"
            ),
            f"{INFO}/WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
            f"{INFO}/entry_points.txt": (
                b"[console_scripts]\nsoup-release = soup_release_lab.cli:main\n"
            ),
            f"{INFO}/top_level.txt": b"soup_release_lab\n",
            f"{INFO}/licenses/LICENSE": (ROOT / "LICENSE").read_bytes(),
        }
    )
    return files


@pytest.mark.parametrize("optimized", [False, True])
@pytest.mark.parametrize(
    ("fault", "expected"),
    [
        ("fixed", None),
        ("stale-record", "Hash mismatch"),
        ("missing-resource", "missing="),
        ("unexpected-pth", "unexpected="),
        ("unexpected-module", "unexpected="),
        ("changed-source", "Wheel/source bytes differ"),
        ("changed-license", "license bytes differ"),
        ("extra-entrypoint", "Unexpected wheel entry points"),
        ("duplicate", "Duplicate wheel member"),
    ],
)
def test_wheel_contract(tmp_path, optimized, fault, expected):
    files = wheel_contents()
    resource = "soup_release_lab/greeting.txt"
    if fault == "missing-resource":
        del files[resource]
    elif fault == "unexpected-pth":
        files["startup.pth"] = b"# An unexpected startup hook, with a valid RECORD\n"
    elif fault == "unexpected-module":
        files["soup_release_lab/surprise.py"] = b"value = 1\n"
    elif fault == "changed-source":
        files[resource] = b"Wrong greeting\n"
    elif fault == "changed-license":
        files[f"{INFO}/licenses/LICENSE"] = b"Wrong license\n"
    elif fault == "extra-entrypoint":
        files[f"{INFO}/entry_points.txt"] += b"extra = soup_release_lab.cli:main\n"
    wheel = tmp_path / "soup_release_lab_maximushkabed-0.9.3-py3-none-any.whl"
    with WheelFile(wheel, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    if fault == "stale-record":
        with zipfile.ZipFile(wheel) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        members[resource] = b"Tampered\n"
        with zipfile.ZipFile(wheel, "w") as archive:
            for name, data in members.items():
                archive.writestr(name, data)
    elif fault == "duplicate":
        with pytest.warns(UserWarning, match="Duplicate name"):
            with zipfile.ZipFile(wheel, "a") as archive:
                archive.writestr(resource, files[resource])
    result = subprocess.run(
        [sys.executable, *(["-O"] if optimized else []), "tools/check_wheel.py", str(wheel)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=15,
    )
    if expected is None:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
        assert expected in result.stderr
