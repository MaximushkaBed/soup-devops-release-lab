"""Check a local release candidate and preserve evidence before using remote CI."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source_snapshot(root: Path, paths: str | None = None) -> dict[str, str]:
    """Hash Git-visible files, including additions not yet tracked."""
    if paths is None:
        paths = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            encoding="utf-8",
            timeout=30,
        )
    return {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in paths.split("\0")
        if name and (root / name).is_file()
    }


def require_same_sources(before: dict[str, str], after: dict[str, str]) -> None:
    changed = sorted(
        name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
    )
    if changed:
        raise ValueError(f"Source changed during preflight; rerun this candidate: {changed}")


def stop_process(process: subprocess.Popen) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        if process.poll() is None:
            process.kill()
    process.wait(timeout=15)


class Recorder:
    def __init__(self, directory: Path):
        self.directory = directory
        self.summary = {
            "status": "running",
            "python": sys.version,
            "platform": platform.platform(),
            "steps": [],
            "skipped": [],
        }
        self.save()

    def save(self) -> None:
        temporary = self.directory / "summary.json.tmp"
        temporary.write_text(json.dumps(self.summary, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.directory / "summary.json")

    def step(
        self,
        name: str,
        command: list[str],
        *,
        cwd: Path = ROOT,
        timeout: float = 600,
        extra_env: dict[str, str] | None = None,
    ) -> str:
        log = self.directory / f"{len(self.summary['steps']) + 1:02d}-{name}.log"
        step = {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "log": log.name,
            "status": "running",
        }
        self.summary["steps"].append(step)
        self.save()
        started = time.monotonic()
        print(f"RUN: {name}", flush=True)
        with log.open("w", encoding="utf-8") as output:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env={**os.environ, **(extra_env or {})},
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=os.name == "posix",
                )
                try:
                    code = process.wait(timeout=timeout)
                except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                    stop_process(process)
                    code = 124 if isinstance(error, subprocess.TimeoutExpired) else 130
                    output.write(
                        f"\n{'TIMEOUT' if code == 124 else 'INTERRUPTED'} after {timeout} seconds\n"
                    )
            except OSError as error:
                output.write(f"{error}\n")
                code = 127
        step.update(
            exit_code=code,
            seconds=round(time.monotonic() - started, 3),
            status="passed" if code == 0 else "failed",
        )
        if code:
            self.summary["status"] = "failed"
        self.save()
        output = log.read_text(encoding="utf-8", errors="replace")
        if code:
            print(output, end="", flush=True)
            raise RuntimeError(f"{name} failed (exit {code}); full log: {log}")
        print(f"PASS: {name} ({step['seconds']}s)", flush=True)
        return output


def check_docker(recorder: Recorder, bundle: Path) -> None:
    # Use the repository's actual Dockerfile/ignore rules with this candidate only.
    # Keep Buildx state separate from the user's registry credentials/configuration.
    config = recorder.directory / "docker-config"
    config.mkdir()
    env = {"DOCKER_CONFIG": str(config)}
    image = "soup-release:preflight-" + recorder.directory.name.lower()
    container = recorder.directory.name.lower()
    with tempfile.TemporaryDirectory(prefix="soup-docker-") as temporary:
        context = Path(temporary)
        for name in ("Dockerfile", ".dockerignore"):
            shutil.copy2(ROOT / name, context / name)
        shutil.copytree(bundle, context / "bundle")
        recorder.step(
            "docker-build",
            ["docker", "build", "--network=none", "-t", image, "."],
            cwd=context,
            extra_env=env,
        )
        try:
            output = recorder.step(
                "docker-run",
                [
                    "docker",
                    "run",
                    "--name",
                    container,
                    "--network=none",
                    "--read-only",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges",
                    "--memory=128m",
                    "--cpus=1",
                    "--pids-limit=64",
                    image,
                    "--name",
                    "Soup",
                    "--json",
                ],
                extra_env=env,
                timeout=60,
            )
            data = json.loads(output)
            if data.get("greeting") != "Hello, Soup!" or data.get("version") != "0.9.4":
                raise ValueError(f"Unexpected Docker CLI output: {data}")
        finally:
            try:
                recorder.step(
                    "docker-container-cleanup",
                    ["docker", "container", "rm", "--force", container],
                    extra_env=env,
                    timeout=30,
                )
            finally:
                recorder.step(
                    "docker-cleanup", ["docker", "image", "rm", image], extra_env=env, timeout=30
                )


def check_ml(recorder: Recorder, runtime_path: Path | None) -> None:
    python = sys.executable
    directory = recorder.directory
    with tempfile.TemporaryDirectory(prefix="soup-preflight-ml-") as ml_temporary:
        runtime = runtime_path.resolve() if runtime_path else Path(ml_temporary) / "profile"
        if not runtime_path:
            recorder.step(
                "ml-profile",
                [python, "tools/ml_lab.py", "provision", "floor", str(runtime)],
                timeout=900,
            )
        shutil.copy2(runtime / "profile.json", directory / "ml-profile.json")
        ml_bundle = directory / "training-bundle"
        recorder.step("ml-build", [python, "tools/ml_lab.py", "build", "fixed", str(ml_bundle)])
        recorder.step(
            "ml-bare",
            [
                python,
                "tools/ml_lab.py",
                "bare",
                str(ml_bundle),
                "--report",
                str(directory / "ml-bare.json"),
            ],
        )
        for backend in ("cpu", "interpreter"):
            for artifact in ("wheel", "sdist"):
                name = f"ml-{backend}-{artifact}"
                recorder.step(
                    name,
                    [
                        python,
                        "tools/ml_lab.py",
                        "test",
                        str(ml_bundle),
                        str(runtime),
                        "--backend",
                        backend,
                        "--artifact",
                        artifact,
                        "--report",
                        str(directory / f"{name}.json"),
                    ],
                )
        recorder.step(
            "ml-gpu-guard",
            [
                python,
                "tools/ml_lab.py",
                "gpu-guard",
                str(runtime),
                "--report",
                str(directory / "ml-gpu-unavailable.json"),
            ],
        )
        recorder.step(
            "ml-fault-experiments",
            [
                python,
                "tools/ml_lab.py",
                "experiment",
                str(directory / "ml-experiments"),
                str(runtime),
            ],
            timeout=1200,
        )
        recorder.summary["native_gpu"] = "not-run; CPU/interpreter evidence only"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actionlint", default="actionlint", help="Path to the actionlint binary")
    parser.add_argument("--skip-docker", action="store_true", help="Produce a partial report")
    parser.add_argument(
        "--with-ml", action="store_true", help="Also validate the separate ML fixture"
    )
    parser.add_argument("--ml-runtime", type=Path, help="Reuse a verified CPU ML profile directory")
    args = parser.parse_args()
    if args.ml_runtime and not args.with_ml:
        parser.error("--ml-runtime requires --with-ml")
    evidence = ROOT / ".evidence"
    evidence.mkdir(exist_ok=True)
    prefix = "preflight-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=evidence))
    recorder = Recorder(directory)
    python = sys.executable
    bundle = directory / "bundle"
    print(f"Evidence: {directory}", flush=True)
    try:
        recorder.summary["commit"] = recorder.step("commit", ["git", "rev-parse", "HEAD"]).strip()
        recorder.summary["working_tree"] = recorder.step("status", ["git", "status", "--short"])
        recorder.step("whitespace", ["git", "diff", "--check"])
        paths = recorder.step(
            "source-files", ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        recorder.summary["source_sha256"] = source_snapshot(ROOT, paths)
        recorder.save()
        for path in (ROOT, Path(tempfile.gettempdir())):
            if shutil.disk_usage(path).free < 100 * 1024 * 1024:
                raise ValueError(
                    f"Less than 100 MiB free at {path}; cannot create clean test environments"
                )
        recorder.step("actionlint", [args.actionlint, "-color", "-shellcheck="])
        recorder.step("lint", [python, "-m", "ruff", "check", "."])
        recorder.step("format", [python, "-m", "ruff", "format", "--check", "."])
        recorder.step("tests", [python, "-m", "pytest", "-q"])
        recorder.step(
            "build", [python, "-m", "build", "--no-isolation", "--outdir", str(bundle / "dist")]
        )
        artifacts = sorted(str(path) for path in (bundle / "dist").iterdir())
        recorder.step("metadata", [python, "-m", "twine", "check", "--strict", *artifacts])
        recorder.step(
            "wheel-contract",
            [
                python,
                "tools/check_wheel.py",
                *sorted(str(p) for p in (bundle / "dist").glob("*.whl")),
            ],
        )
        recorder.step("record", [python, "tools/provenance.py", "record", str(bundle)])
        recorder.step("verify", [python, "-O", "tools/provenance.py", "verify", str(bundle)])
        for flags, name in (([], "guards"), (["-O"], "optimized-guards")):
            recorder.step(name, [python, *flags, "tools/check_supply_chain.py", str(bundle)])
        for pattern, name in (("*.whl", "wheel"), ("*.tar.gz", "sdist")):
            recorder.step(name, [python, "tools/test_artifact.py", str(bundle / "dist" / pattern)])
        if args.with_ml:
            check_ml(recorder, args.ml_runtime)
        if args.skip_docker:
            recorder.summary["skipped"].append("docker")
        else:
            check_docker(recorder, bundle)
        final_sources = source_snapshot(ROOT)
        recorder.summary["final_source_sha256"] = final_sources
        require_same_sources(recorder.summary["source_sha256"], final_sources)
        recorder.summary["status"] = "partial" if args.skip_docker else "passed"
    except (RuntimeError, ValueError, OSError, KeyboardInterrupt) as error:
        recorder.summary.update(status="failed", error=str(error))
        print(f"FAIL: {error}", file=sys.stderr)
    finally:
        recorder.save()
    print(f"Result: {recorder.summary['status']}; {directory / 'summary.json'}", flush=True)
    return 1 if recorder.summary["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
