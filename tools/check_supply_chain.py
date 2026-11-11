"""Negative integration checks against the actual built release bundle."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("provenance.py").resolve()


def verify_command(bundle: Path) -> list[str]:
    flags = ["-O"] if sys.flags.optimize else []
    return [sys.executable, *flags, str(SCRIPT), "verify", str(bundle)]


def rejected(bundle: Path, expected: str, extra_env: dict[str, str] | None = None) -> None:
    env = {**os.environ, **(extra_env or {})}
    result = subprocess.run(
        verify_command(bundle),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        raise ValueError("Guard accepted an invalid bundle")
    if expected not in result.stderr:
        raise ValueError(f"Expected rejection {expected!r}; received:\n{result.stderr}")
    print(f"PASS: rejected {expected}")


def main() -> None:
    source = Path(sys.argv[1]).resolve()
    # A broken guard that rejects everything must not pass negative experiments.
    subprocess.run(verify_command(source), check=True, timeout=30)
    with tempfile.TemporaryDirectory(prefix="soup-guards-") as tmp:
        root = Path(tmp)
        for scenario in ("tamper", "stale", "tag"):
            bundle = root / scenario
            shutil.copytree(source, bundle)
            if scenario == "tamper":
                wheel = next((bundle / "dist").glob("*.whl"))
                wheel.write_bytes(wheel.read_bytes() + b"tampered")
                rejected(bundle, "Stale or modified artifact")
            elif scenario == "stale":
                path = bundle / "manifest.json"
                data = json.loads(path.read_text())
                data["commit"] = "0" * 40
                path.write_text(json.dumps(data))
                rejected(bundle, "Stale or modified artifact")
            else:
                rejected(
                    bundle,
                    "Version/tag mismatch",
                    {"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v999.0.0"},
                )


if __name__ == "__main__":
    main()
