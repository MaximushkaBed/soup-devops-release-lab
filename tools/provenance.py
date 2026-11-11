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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def identity() -> dict[str, str]:
    return {
        "commit": os.environ.get("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "run": os.environ.get("GITHUB_RUN_ID", "local"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
    }


def distributions(bundle: Path) -> dict[str, str]:
    artifacts = sorted((bundle / "dist").iterdir())
    require(len(artifacts) == 2, "Expected exactly two distributions")
    require(
        all(p.is_file() and not p.is_symlink() for p in artifacts),
        "Expected regular artifact files",
    )
    require(sum(p.suffix == ".whl" for p in artifacts) == 1, "Expected one wheel")
    require(sum(p.name.endswith(".tar.gz") for p in artifacts) == 1, "Expected one sdist")
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}


def single_header(info, name: str) -> str:
    values = info.get_all(name, [])
    require(len(values) == 1 and bool(values[0].strip()), f"Expected one nonempty {name} header")
    return values[0].strip()


def metadata(bundle: Path) -> str:
    versions = []
    for artifact in (bundle / "dist").iterdir():
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as archive:
                members = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
                require(len(members) == 1, "Expected one wheel metadata file")
                raw = archive.read(members[0])
        else:
            with tarfile.open(artifact) as archive:
                members = [
                    m
                    for m in archive.getmembers()
                    if m.name.count("/") == 1 and m.name.endswith("/PKG-INFO")
                ]
                require(len(members) == 1, "Expected one sdist metadata file")
                require(members[0].isfile(), "Expected regular sdist metadata file")
                raw = archive.extractfile(members[0]).read()
        info = BytesParser().parsebytes(raw)
        require(single_header(info, "Name") == DIST, "Unexpected distribution name")
        require(not info.get_all("Requires-Dist"), "Unexpected runtime dependency")
        require(
            set(single_header(info, "Requires-Python").split(",")) == {">=3.10", "<3.15"},
            "Unexpected Python support range",
        )
        versions.append(single_header(info, "Version"))
    require(len(versions) == 2 and len(set(versions)) == 1, "Distribution versions differ")
    version = versions[0]
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        require(os.environ["GITHUB_REF_NAME"] == f"v{version}", "Version/tag mismatch")
    return version


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "verify"))
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    hashes = distributions(args.bundle)
    current = {**identity(), "version": metadata(args.bundle), "sha256": hashes}
    manifest = args.bundle / "manifest.json"
    if args.action == "record":
        manifest.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    else:
        require(
            json.loads(manifest.read_text(encoding="utf-8")) == current,
            "Stale or modified artifact",
        )
    print(json.dumps(current, indent=2))


if __name__ == "__main__":
    main()
