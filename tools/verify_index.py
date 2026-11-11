"""Verify published hashes and a fresh, hash-checked TestPyPI installation."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import venv
from pathlib import Path

PROJECT = "soup-release-lab-maximushkabed"
ROOT = Path(__file__).resolve().parents[1]


class IndexNotReady(ValueError):
    """The index may lag behind a completed two-file upload."""


def published_files(metadata: dict, manifest: dict) -> dict:
    info = metadata.get("info", {})
    if info.get("name") != PROJECT or info.get("version") != manifest["version"]:
        raise ValueError("Index project/version identity mismatch")
    files = metadata.get("urls", [])
    published = {item["filename"]: item for item in files}
    if len(published) != len(files):
        raise ValueError("Index returned duplicate filenames")
    expected = set(manifest["sha256"])
    if set(published) - expected:
        raise ValueError("Index has unexpected files")
    for filename, item in published.items():
        if item.get("digests", {}).get("sha256") != manifest["sha256"][filename]:
            raise ValueError(f"Published digest mismatch: {filename}")
        url = urllib.parse.urlsplit(item["url"])
        if url.scheme != "https" or url.hostname != "test-files.pythonhosted.org" or url.username:
            raise ValueError(f"Unexpected artifact download origin: {filename}")
        if item.get("yanked"):
            raise ValueError(f"Published artifact is yanked: {filename}")
    if set(published) != expected:
        raise IndexNotReady("Index is missing an expected distribution")
    return published


def wait_for_index(manifest: dict, attempts: int = 12) -> dict:
    url = f"https://test.pypi.org/pypi/{PROJECT}/{manifest['version']}/json"
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                metadata = json.load(response)
            return published_files(metadata, manifest)
        except urllib.error.HTTPError as error:
            if error.code not in (404, 429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            reason = f"HTTP {error.code}"
        except (IndexNotReady, urllib.error.URLError, TimeoutError) as error:
            if attempt == attempts - 1:
                raise
            reason = str(error)
        print(f"Index not ready ({reason}); attempt {attempt + 1}/{attempts}", flush=True)
        time.sleep(5)
    raise ValueError("Index verification requires at least one attempt")


def main() -> None:
    bundle = Path(sys.argv[1]).resolve()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    published = wait_for_index(manifest)
    for filename, digest in manifest["sha256"].items():
        item = published[filename]
        local = bundle / "dist" / filename
        if local.name != filename or hashlib.sha256(local.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Local artifact does not match manifest: {filename}")
        with urllib.request.urlopen(item["url"], timeout=30) as response:
            # Bound a corrupt response by the exact size of the tested candidate.
            if hashlib.sha256(response.read(local.stat().st_size + 1)).hexdigest() != digest:
                raise ValueError(f"Published bytes mismatch: {filename}")
    with tempfile.TemporaryDirectory(prefix="soup-index-") as tmp:
        work = Path(tmp)
        runtime = work / "runtime"
        venv.create(runtime, with_pip=True, symlinks=os.name != "nt")
        python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        wheel_hash = next(d for name, d in manifest["sha256"].items() if name.endswith(".whl"))
        requirement = work / "published.txt"
        requirement.write_text(f"{PROJECT}=={version} --hash=sha256:{wheel_hash}\n")
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("PIP_", "PYTHON"))
        }
        env.update(
            PIP_CONFIG_FILE=os.devnull, PIP_NO_CACHE_DIR="1", PIP_DISABLE_PIP_VERSION_CHECK="1"
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--only-binary=:all:",
                "--require-hashes",
                "--index-url",
                "https://test.pypi.org/simple/",
                "-r",
                str(requirement),
            ],
            check=True,
            cwd=work,
            env=env,
            timeout=180,
        )
        subprocess.run(
            [str(python), "-I", "-m", "pip", "uninstall", "--yes", "pip", "setuptools", "wheel"],
            check=True,
            cwd=work,
            env=env,
            timeout=60,
        )
        subprocess.run(
            [str(python), "-I", str(ROOT / "tools/smoke.py")],
            check=True,
            cwd=work,
            env=env,
            timeout=60,
        )
    print(f"PASS: TestPyPI {PROJECT} {version}: published bytes and clean install verified")


if __name__ == "__main__":
    main()
