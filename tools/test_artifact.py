"""Rebuild sdists separately and test wheels in a dependency-free runtime."""

import argparse
import glob
import os
import subprocess
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def python_in(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(args: list[str], cwd: Path) -> None:
    env = {
        key: value for key, value in os.environ.items() if not key.startswith(("PIP_", "PYTHON"))
    }
    env.update(PIP_CONFIG_FILE=os.devnull, PIP_NO_CACHE_DIR="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, cwd=cwd, env=env, timeout=240)


def test(artifact: Path) -> None:
    artifact = artifact.resolve()
    with tempfile.TemporaryDirectory(prefix="soup-artifact-") as tmp:
        work = Path(tmp)
        wheel = artifact
        if artifact.name.endswith(".tar.gz"):
            builder = work / "builder"
            venv.create(builder, with_pip=True, symlinks=os.name != "nt")
            python = str(python_in(builder))
            run(
                [
                    python,
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--require-hashes",
                    "--only-binary=:all:",
                    "-r",
                    str(ROOT / "requirements/build.txt"),
                ],
                work,
            )
            rebuilt = work / "rebuilt"
            run(
                [
                    python,
                    "-I",
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "--no-build-isolation",
                    "--no-index",
                    "--wheel-dir",
                    str(rebuilt),
                    str(artifact),
                ],
                work,
            )
            wheels = list(rebuilt.glob("*.whl"))
            if len(wheels) != 1:
                raise ValueError(f"Expected exactly one rebuilt wheel, found: {wheels}")
            wheel = wheels[0]
        runtime = work / "runtime"
        venv.create(runtime, with_pip=True, symlinks=os.name != "nt")
        python = str(python_in(runtime))
        run([python, "-I", "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], work)
        run([python, "-I", "-m", "pip", "check"], work)
        run([python, "-I", "-m", "pip", "uninstall", "--yes", "pip", "setuptools", "wheel"], work)
        run([python, "-I", str(ROOT / "tools/smoke.py")], work)
        run([python, "-I", "-O", str(ROOT / "tools/smoke.py")], work)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifacts", nargs="+")
    args = parser.parse_args()
    artifacts = set()
    for pattern in args.artifacts:
        matches = [Path(path) for path in glob.glob(pattern)]
        if not matches:
            parser.error(f"No matching artifacts: {pattern}")
        for artifact in matches:
            if not artifact.is_file() or not artifact.name.endswith((".whl", ".tar.gz")):
                parser.error(f"Expected a wheel or sdist file: {artifact}")
            artifacts.add(artifact.resolve())
    for artifact in sorted(artifacts):
        test(artifact)


if __name__ == "__main__":
    main()
