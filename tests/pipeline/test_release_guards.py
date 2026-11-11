"""Exercise release guards as real processes, including optimized Python."""

import io
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
METADATA = (
    "Metadata-Version: 2.4\n"
    "Name: soup-release-lab-maximushkabed\n"
    "Version: 0.9.3\n"
    "Requires-Python: >=3.10,<3.15\n"
)


def make_bundle(directory, wheel_metadata=METADATA, sdist_metadata=METADATA):
    dist = directory / "dist"
    dist.mkdir(parents=True)
    with zipfile.ZipFile(dist / "soup-0.9.3-py3-none-any.whl", "w") as archive:
        archive.writestr("soup-0.9.3.dist-info/METADATA", wheel_metadata)
    with tarfile.open(dist / "soup-0.9.3.tar.gz", "w:gz") as archive:
        content = sdist_metadata.encode()
        member = tarfile.TarInfo("soup-0.9.3/PKG-INFO")
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
    return directory


@pytest.fixture(params=[False, True], ids=["normal", "optimized"])
def guard(request):
    flags = ["-O"] if request.param else []

    def run(*args, code=None, extra_env=None):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GITHUB_")}
        env.update(GITHUB_SHA="1" * 40, GITHUB_RUN_ID="42", GITHUB_RUN_ATTEMPT="1")
        env.update(extra_env or {})
        result = subprocess.run(
            [sys.executable, *flags, *map(str, args)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if code is not None:
            assert result.returncode == code, result.stdout + result.stderr
        return result

    return run


def test_valid_bundle_is_accepted(tmp_path, guard):
    bundle = make_bundle(tmp_path / "valid")
    guard("tools/provenance.py", "record", bundle, code=0)
    guard("tools/provenance.py", "verify", bundle, code=0)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda text: text.replace(">=3.10", ">=3.11"), "Unexpected Python support range"),
        (
            lambda text: text + "Requires-Dist: undeclared-package\n",
            "Unexpected runtime dependency",
        ),
        (lambda text: text.replace("Version: 0.9.3", "Version: 0.9.4"), "versions differ"),
        (lambda text: text.replace("Name: soup-", "Name: other-"), "Unexpected distribution name"),
    ],
    ids=["python-range", "dependency", "version", "name"],
)
def test_metadata_defects_are_rejected_for_the_right_reason(tmp_path, guard, change, expected):
    bundle = make_bundle(tmp_path / "bad", wheel_metadata=change(METADATA))
    result = guard("tools/provenance.py", "record", bundle)
    assert result.returncode != 0
    assert expected in result.stderr, result.stderr


@pytest.mark.parametrize("header", ["Name", "Version", "Requires-Python"])
@pytest.mark.parametrize("mode", ["missing", "duplicate"])
def test_missing_or_duplicate_metadata_cannot_be_recorded(tmp_path, guard, header, mode):
    lines = METADATA.splitlines(keepends=True)
    value = next(line for line in lines if line.startswith(header + ":"))
    altered = METADATA.replace(value, "") if mode == "missing" else METADATA + value
    bundle = make_bundle(tmp_path / "malformed", wheel_metadata=altered, sdist_metadata=altered)
    result = guard("tools/provenance.py", "record", bundle)
    assert result.returncode != 0, "Malformed metadata was accepted"
    assert f"Expected one nonempty {header} header" in result.stderr


@pytest.mark.parametrize("field", ["commit", "run", "attempt"])
def test_stale_identity_is_rejected(tmp_path, guard, field):
    bundle = make_bundle(tmp_path / "stale")
    guard("tools/provenance.py", "record", bundle, code=0)
    manifest = bundle / "manifest.json"
    data = json.loads(manifest.read_text())
    data[field] = "stale"
    manifest.write_text(json.dumps(data))
    result = guard("tools/provenance.py", "verify", bundle)
    assert result.returncode != 0
    assert "Stale or modified artifact" in result.stderr


def test_mutated_bytes_are_rejected(tmp_path, guard):
    bundle = make_bundle(tmp_path / "tamper")
    guard("tools/provenance.py", "record", bundle, code=0)
    wheel = next((bundle / "dist").glob("*.whl"))
    wheel.write_bytes(wheel.read_bytes() + b"tampered")
    result = guard("tools/provenance.py", "verify", bundle)
    assert result.returncode != 0
    assert "Stale or modified artifact" in result.stderr


def test_wrong_tag_is_rejected(tmp_path, guard):
    bundle = make_bundle(tmp_path / "tag")
    result = guard(
        "tools/provenance.py",
        "record",
        bundle,
        extra_env={"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v999.0.0"},
    )
    assert result.returncode != 0
    assert "Version/tag mismatch" in result.stderr


def test_negative_checker_cannot_claim_that_a_valid_bundle_was_rejected(tmp_path, guard):
    bundle = make_bundle(tmp_path / "positive-control")
    guard("tools/provenance.py", "record", bundle, code=0)
    result = guard(
        "-c",
        "from pathlib import Path; from tools.check_supply_chain import rejected; "
        "rejected(Path(__import__('sys').argv[1]), 'Stale or modified artifact')",
        bundle,
    )
    assert result.returncode != 0, "Negative checker reported success although the guard accepted"
    assert "Guard accepted an invalid bundle" in result.stderr


def test_negative_checker_requires_the_expected_cause(tmp_path, guard):
    bundle = make_bundle(tmp_path / "wrong-cause")
    guard("tools/provenance.py", "record", bundle, code=0)
    (bundle / "manifest.json").write_text("{}")
    result = guard(
        "-c",
        "from pathlib import Path; from tools.check_supply_chain import rejected; "
        "rejected(Path(__import__('sys').argv[1]), 'Version/tag mismatch')",
        bundle,
    )
    assert result.returncode != 0, "Negative checker accepted a failure for an unrelated reason"
    assert "Stale or modified artifact" in result.stderr
