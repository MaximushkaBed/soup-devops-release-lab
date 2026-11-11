"""Compare real dependency profiles using the same HTTP-client wheel."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAULTS = ("fixed", "removed-api", "undeclared-runtime")


def identity() -> dict:
    return {
        "commit": os.environ.get("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "run": os.environ.get("GITHUB_RUN_ID", "local"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "profiles": {
            name: hashlib.sha256(
                (ROOT / f"requirements/compat-{name}.txt").read_bytes()
            ).hexdigest()
            for name in ("minimum", "current")
        },
    }


def python_in(directory: Path) -> str:
    return str(directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def clean_env() -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items() if not key.startswith(("PIP_", "PYTHON"))
    }
    return {
        **env,
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_NO_CACHE_DIR": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONUTF8": "1",
    }


def run(command: list[str], cwd: Path, *, capture: bool = False) -> str:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=clean_env(),
        timeout=240,
        capture_output=capture,
        text=True,
        encoding="utf-8",
    )
    if capture:
        print(result.stdout, end="", flush=True)
        print(result.stderr, end="", file=sys.stderr, flush=True)
    result.check_returncode()
    return result.stdout or ""


def build(fault: str, bundle: Path) -> None:
    if bundle.exists():
        raise ValueError(f"Use a new bundle directory; refusing stale output: {bundle}")
    bundle.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="soup-dependency-build-") as temporary:
        source = Path(temporary) / "source"
        shutil.copytree(
            ROOT / "fixtures/http-client",
            source,
            ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__"),
        )
        if fault == "removed-api":
            target = source / "src/soup_http_probe/__init__.py"
            before = "httpx.Client(timeout=5.0, trust_env=False, transport=transport)"
            after = "httpx.Client(timeout=5.0, trust_env=False, transport=transport, proxies=None)"
        elif fault == "undeclared-runtime":
            target = source / "pyproject.toml"
            before, after = ', "tenacity>=8.5,<10"', ""
        else:
            target = None
        if target is not None:
            content = target.read_text(encoding="utf-8")
            if content.count(before) != 1:
                raise ValueError(f"Expected exactly one fault patch in {target}")
            target.write_text(content.replace(before, after), encoding="utf-8")
            print(f"Fault {fault}: {before!r} -> {after!r}", flush=True)
        run(
            [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(bundle / "dist")],
            source,
        )
    files = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((bundle / "dist").iterdir())
    }
    if len(files) != 2 or len(list((bundle / "dist").glob("*.whl"))) != 1:
        raise ValueError("Expected one fixture wheel and one sdist")
    manifest = {**identity(), "fault": fault, "sha256": files}
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


def test(bundle: Path, profile: str, naive: bool) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    mismatches = [key for key, value in identity().items() if manifest.get(key) != value]
    if mismatches:
        raise ValueError(f"Dependency fixture identity or profile locks differ: {mismatches}")
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((bundle / "dist").iterdir())
    }
    if actual != manifest["sha256"]:
        raise ValueError("Dependency fixture bundle was altered")
    wheel = next((bundle / "dist").glob("*.whl"))
    lock = ROOT / f"requirements/compat-{profile}.txt"
    with tempfile.TemporaryDirectory(prefix="soup-dependency-test-") as temporary:
        work = Path(temporary)
        downloader, runtime = work / "downloader", work / "runtime"
        venv.create(downloader, with_pip=True, symlinks=os.name != "nt")
        wheelhouse = work / "wheelhouse"
        run(
            [
                python_in(downloader),
                "-I",
                "-m",
                "pip",
                "download",
                "--require-hashes",
                "--only-binary=:all:",
                "--dest",
                str(wheelhouse),
                "-r",
                str(lock),
            ],
            work,
        )
        venv.create(runtime, with_pip=True, symlinks=os.name != "nt")
        python = python_in(runtime)
        pip = [python, "-I", "-m", "pip"]
        offline = ["--no-index", "--find-links", str(wheelhouse)]
        if naive:
            # Development tooling has already installed all dependencies, declared or not.
            run([*pip, "install", *offline, "--require-hashes", "-r", str(lock)], work)
            run([*pip, "install", "--no-deps", "--no-index", str(wheel)], work)
        else:
            # Resolve only what the wheel actually declares, from the hash-verified wheelhouse.
            run([*pip, "install", *offline, "--only-binary=:all:", str(wheel)], work)
            run([*pip, "check"], work)
            run([*pip, "uninstall", "--yes", "pip", "setuptools", "wheel"], work)
        executable = Path(python).with_name(
            "soup-http-probe.exe" if os.name == "nt" else "soup-http-probe"
        )
        output = run([str(executable), "--self-test"], work, capture=True)
        result = json.loads(output)
        expected_httpx = "0.27.2" if profile == "minimum" else "0.28.1"
        if result.get("status") != "passed" or result.get("httpx") != expected_httpx:
            raise ValueError(f"Unexpected fixture result: {result}")
        print(
            f"PASS: {manifest['fault']}; {profile}; {'naive' if naive else 'clean'}; {sys.platform}"
        )


def experiment(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    results = []
    for fault in FAULTS:
        bundle = directory / fault
        build(fault, bundle)
        cases = (
            [("minimum", False, ""), ("current", False, "")]
            if fault == "fixed"
            else [
                ("minimum", True, ""),
                (
                    "current",
                    False,
                    "unexpected keyword argument 'proxies'"
                    if fault == "removed-api"
                    else "ModuleNotFoundError: No module named 'tenacity'",
                ),
            ]
        )
        for profile, naive, expected in cases:
            name = f"{fault}-{profile}-{'naive' if naive else 'clean'}"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "test",
                str(bundle),
                "--profile",
                profile,
                *(["--naive"] if naive else []),
            ]
            log = directory / f"{name}.log"
            with log.open("w", encoding="utf-8") as output:
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    env=clean_env(),
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=300,
                )
            content = log.read_text(encoding="utf-8")
            valid = (
                (result.returncode != 0 and expected in content)
                if expected
                else result.returncode == 0
            )
            results.append(
                {
                    "case": name,
                    "exit_code": result.returncode,
                    "expected_error": expected or None,
                    "verified": valid,
                    "log": log.name,
                }
            )
            (directory / "results.json").write_text(
                json.dumps(results, indent=2) + "\n", encoding="utf-8"
            )
            print(
                f"{'PASS' if valid else 'FAIL'}: {name}; observed exit {result.returncode}",
                flush=True,
            )
            if not valid:
                raise ValueError(f"Unexpected dependency experiment result; inspect {log}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    builder = subparsers.add_parser("build")
    builder.add_argument("fault", choices=FAULTS)
    builder.add_argument("bundle", type=Path)
    tester = subparsers.add_parser("test")
    tester.add_argument("bundle", type=Path)
    tester.add_argument("--profile", choices=("minimum", "current"), required=True)
    tester.add_argument("--naive", action="store_true")
    experiments = subparsers.add_parser("experiment")
    experiments.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        build(args.fault, args.bundle.resolve())
    elif args.action == "test":
        test(args.bundle.resolve(), args.profile, args.naive)
    else:
        experiment(args.directory.resolve())


if __name__ == "__main__":
    main()
