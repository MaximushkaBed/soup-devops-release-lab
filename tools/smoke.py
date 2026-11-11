"""Run with the installed environment's Python -I, outside the source tree."""

import importlib.metadata
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

DIST = "soup-release-lab-maximushkabed"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def invoke(executable: Path, *args: str, expected_code: int = 0) -> str:
    result = subprocess.run(
        [str(executable), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
        timeout=30,
    )
    if result.returncode != expected_code:
        print(result.stdout, end="", flush=True)
        print(result.stderr, end="", file=sys.stderr, flush=True)
        raise ValueError(f"CLI {args!r}: expected exit {expected_code}, got {result.returncode}")
    if expected_code:
        require(not result.stdout, f"Invalid arguments produced stdout: {result.stdout!r}")
        require("error:" in result.stderr, f"Missing argument error diagnostic: {result.stderr!r}")
    else:
        require(not result.stderr, f"Unexpected CLI stderr: {result.stderr!r}")
    return result.stdout


def validate_report(data: dict, name: str) -> None:
    require(data.get("greeting") == f"Hello, {name}!", f"Wrong greeting: {data}")
    require(data.get("version") == "0.9.3", f"Wrong version: {data}")
    require(bool(data.get("user")), f"Missing user: {data}")
    timestamp = datetime.fromisoformat(data["timestamp"])
    require(timestamp.utcoffset() == timedelta(0), f"Timestamp must be UTC: {data}")


def main() -> None:
    import soup_release_lab

    require(bool(sys.flags.isolated), "Smoke test must run with Python -I")
    distributions = {dist.metadata["Name"] for dist in importlib.metadata.distributions()}
    require(distributions == {DIST}, f"Unexpected installed distributions: {distributions}")
    installed = Path(soup_release_lab.__file__).resolve()
    require(
        installed.is_relative_to(Path(sys.prefix).resolve()), f"Not installed in venv: {installed}"
    )
    require(
        importlib.metadata.version(DIST) == soup_release_lab.__version__ == "0.9.3",
        "Installed distribution and module versions must both be 0.9.3",
    )
    executable = Path(sys.executable).with_name(
        "soup-release.exe" if os.name == "nt" else "soup-release"
    )
    for name in ("Soup", "Кот 🍲", "", "a{b}"):
        validate_report(json.loads(invoke(executable, "--name", name, "--json")), name)
    require(invoke(executable).strip() == "Hello, world!", "Wrong default text greeting")
    require(invoke(executable, "--name", "Soup").strip() == "Hello, Soup!", "Wrong text greeting")
    require(invoke(executable, "--version").strip() == "0.9.3", "Wrong CLI version")
    require("usage:" in invoke(executable, "--help"), "Missing CLI help")
    invoke(executable, "--invalid", expected_code=2)
    invoke(executable, "--name", expected_code=2)
    print(f"PASS: {sys.version.split()[0]} {sys.platform}: {installed}")


if __name__ == "__main__":
    main()
