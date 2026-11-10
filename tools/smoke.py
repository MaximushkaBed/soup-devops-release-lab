"""Run with the installed environment's Python -I, outside the source tree."""

import importlib.metadata
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DIST = "soup-release-lab-maximushkabed"


def main() -> None:
    import soup_release_lab

    assert sys.flags.isolated, "Smoke test must run with Python -I"
    assert {dist.metadata["Name"] for dist in importlib.metadata.distributions()} == {DIST}
    installed = Path(soup_release_lab.__file__).resolve()
    assert installed.is_relative_to(Path(sys.prefix).resolve()), installed
    assert importlib.metadata.version(DIST) == soup_release_lab.__version__ == "0.9.3"
    executable = Path(sys.executable).with_name(
        "soup-release.exe" if os.name == "nt" else "soup-release"
    )
    result = subprocess.run(
        [str(executable), "--name", "Soup", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        print(result.stdout, end="", flush=True)
        print(result.stderr, end="", file=sys.stderr, flush=True)
        result.check_returncode()
    data = json.loads(result.stdout)
    assert data["greeting"] == "Hello, Soup!", data
    assert data["version"] == "0.9.3" and data["user"], data
    assert datetime.fromisoformat(data["timestamp"]).utcoffset().total_seconds() == 0
    assert (
        subprocess.check_output([str(executable), "--version"], text=True, timeout=30).strip()
        == "0.9.3"
    )
    bad = subprocess.run([str(executable), "--invalid"], capture_output=True, timeout=30)
    assert bad.returncode == 2
    print(f"PASS: {sys.version.split()[0]} {sys.platform}: {installed}")


if __name__ == "__main__":
    main()
