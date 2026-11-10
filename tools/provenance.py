"""Bind the exact distributions to the current commit, run, version and tag."""

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

DIST = "soup-release-lab-maximushkabed"


def identity() -> dict[str, str]:
    return {
        "commit": os.environ.get("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "run": os.environ.get("GITHUB_RUN_ID", "local"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
    }


def distributions(bundle: Path) -> dict[str, str]:
    artifacts = sorted((bundle / "dist").iterdir())
    assert len(artifacts) == 2, artifacts
    assert sum(p.suffix == ".whl" for p in artifacts) == 1
    assert sum(p.name.endswith(".tar.gz") for p in artifacts) == 1
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}


def metadata(bundle: Path) -> str:
    versions = []
    for artifact in (bundle / "dist").iterdir():
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as archive:
                members = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
                assert len(members) == 1
                raw = archive.read(members[0])
        else:
            with tarfile.open(artifact) as archive:
                members = [
                    m
                    for m in archive.getmembers()
                    if m.name.count("/") == 1 and m.name.endswith("/PKG-INFO")
                ]
                assert len(members) == 1
                raw = archive.extractfile(members[0]).read()
        info = BytesParser().parsebytes(raw)
        assert info["Name"] == DIST, info["Name"]
        assert not info.get_all("Requires-Dist"), "Unexpected runtime dependency"
        assert set(info["Requires-Python"].split(",")) == {">=3.10", "<3.15"}
        versions.append(info["Version"])
    assert len(set(versions)) == 1, versions
    version = versions[0]
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        assert os.environ["GITHUB_REF_NAME"] == f"v{version}", "Version/tag mismatch"
    return version


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "verify"))
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    current = {**identity(), "version": metadata(args.bundle), "sha256": distributions(args.bundle)}
    manifest = args.bundle / "manifest.json"
    if args.action == "record":
        manifest.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    else:
        assert json.loads(manifest.read_text()) == current, "Stale or modified artifact"
    print(json.dumps(current, indent=2))


if __name__ == "__main__":
    main()
