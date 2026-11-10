"""Verify published hashes and a fresh, hash-checked TestPyPI installation."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import venv
from pathlib import Path

PROJECT = "soup-release-lab-maximushkabed"
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    manifest = json.loads((Path(sys.argv[1]) / "manifest.json").read_text())
    version = manifest["version"]
    url = f"https://test.pypi.org/pypi/{PROJECT}/{version}/json"
    for attempt in range(12):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                metadata = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code != 404 or attempt == 11:
                raise
            time.sleep(5)
    published = {item["filename"]: item for item in metadata["urls"]}
    if set(published) != set(manifest["sha256"]):
        raise ValueError("Index has unexpected or missing files")
    for filename, digest in manifest["sha256"].items():
        item = published[filename]
        if item["digests"]["sha256"] != digest:
            raise ValueError(f"Published digest mismatch: {filename}")
        with urllib.request.urlopen(item["url"], timeout=30) as response:
            if hashlib.sha256(response.read()).hexdigest() != digest:
                raise ValueError(f"Published bytes mismatch: {filename}")
    with tempfile.TemporaryDirectory(prefix="soup-index-") as tmp:
        work = Path(tmp)
        runtime = work / "runtime"
        venv.create(runtime, with_pip=True)
        python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        wheel_hash = next(d for name, d in manifest["sha256"].items() if name.endswith(".whl"))
        requirement = work / "published.txt"
        requirement.write_text(f"{PROJECT}=={version} --hash=sha256:{wheel_hash}\n")
        env = {**os.environ, "PIP_CONFIG_FILE": os.devnull, "PIP_NO_CACHE_DIR": "1"}
        env.pop("PYTHONPATH", None)
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
