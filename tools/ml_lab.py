"""Exercise installed LoRA/Triton artifacts against reviewed CPU dependency profiles."""

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAULTS = ("fixed", "backward", "adapter-detach", "missing-resource", "tail-mask")
PATCHES = {
    "backward": [
        (
            "src/soup_training_probe/activation.py",
            "sigmoid + xf * sigmoid * (1.0 - sigmoid)  # BACKWARD_DERIVATIVE",
            "sigmoid",
        ),
        (
            "src/soup_training_probe/kernels.py",
            "derivative = sigmoid + x * sigmoid * (1.0 - sigmoid)",
            "derivative = sigmoid",
        ),
    ],
    "adapter-detach": [
        ("src/soup_training_probe/model.py", "x @ self.a.T", "x @ self.a.detach().T"),
    ],
    "missing-resource": [("pyproject.toml", '["kernel-contract.json"]', "[]")],
    "tail-mask": [
        (
            "src/soup_training_probe/kernels.py",
            "offsets < N  # TAIL_MASK",
            "offsets < N - 1  # TAIL_MASK",
        ),
    ],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def python_in(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def environment():
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PIP_", "PYTHON", "TRITON_"))
    }
    return {
        **env,
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_NO_CACHE_DIR": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONUTF8": "1",
    }


def run(command, cwd, *, check=True):
    print("+", " ".join(map(str, command)), flush=True)
    result = subprocess.run(
        list(map(str, command)),
        cwd=cwd,
        env=environment(),
        timeout=900,
        text=True,
        encoding="utf-8",
    )
    if check:
        result.check_returncode()
    return result.returncode


def identity():
    return {
        "commit": os.environ.get("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "run": os.environ.get("GITHUB_RUN_ID", "local"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "locks": {
            name: digest(ROOT / "requirements" / name)
            for name in (
                "ml-floor.txt",
                "ml-modern.txt",
                "ml-wheels.json",
                "build.txt",
            )
        },
    }


def file_hashes(directory):
    return {
        path.relative_to(directory).as_posix(): digest(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def inject(source, fault):
    for relative, before, after in PATCHES.get(fault, []):
        path = source / relative
        content = path.read_text(encoding="utf-8")
        if content.count(before) != 1:
            raise ValueError(f"Fault patch is ambiguous: {fault}/{relative}")
        path.write_text(content.replace(before, after), encoding="utf-8")


def build(fault, bundle):
    bundle.mkdir(parents=True, exist_ok=False)
    source = bundle / "source"
    shutil.copytree(
        ROOT / "fixtures/training",
        source,
        ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__"),
    )
    inject(source, fault)
    run([sys.executable, "-m", "build", "--no-isolation", "--outdir", bundle / "dist"], source)
    # Build writes egg-info; retain a clean, hashed source snapshot for the naive control.
    for path in source.rglob("*.egg-info"):
        shutil.rmtree(path)
    shutil.rmtree(source / "build", ignore_errors=True)
    if (
        len(list((bundle / "dist").glob("*.whl"))) != 1
        or len(list((bundle / "dist").glob("*.tar.gz"))) != 1
    ):
        raise ValueError("Expected one wheel and one sdist")
    save(bundle / "manifest.json", {**identity(), "fault": fault, "files": file_hashes(bundle)})


def verify(bundle):
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if any(manifest.get(key) != value for key, value in identity().items()):
        raise ValueError("Artifact identity or reviewed dependency locks differ")
    actual = file_hashes(bundle)
    actual.pop("manifest.json", None)
    if actual != manifest["files"]:
        raise ValueError("Training bundle was altered")
    return manifest


def profile_spec(profile):
    if platform.machine().lower() not in ("x86_64", "amd64"):
        raise ValueError("Reviewed profiles support x86_64 only")
    catalog = json.loads((ROOT / "requirements/ml-wheels.json").read_text(encoding="utf-8"))
    spec = catalog["profiles"][profile]
    key = f"{sys.version_info.major}.{sys.version_info.minor}-{sys.platform}"
    if key not in spec["torch_wheels"]:
        raise ValueError(f"No reviewed CPU profile for {key}")
    return spec, key


def provision(profile, directory):
    spec, key = profile_spec(profile)
    directory.mkdir(parents=True, exist_ok=False)
    runtime = directory / "runtime"
    venv.create(runtime, with_pip=True, symlinks=os.name != "nt")
    python = python_in(runtime)
    pip = [python, "-I", "-m", "pip"]
    lock = ROOT / f"requirements/ml-{profile}.txt"
    with tempfile.TemporaryDirectory(prefix="soup-ml-download-") as temporary:
        work = Path(temporary)
        wheelhouse = work / "wheels"
        selected = {"torch": spec["torch_wheels"][key]}
        if sys.platform == "linux":
            selected["triton"] = spec["triton_wheels"][key]
        urls = work / "urls.txt"
        urls.write_text(
            "".join(
                f"{name} @ {item['url']} --hash=sha256:{item['sha256']}\n"
                for name, item in selected.items()
            ),
            encoding="utf-8",
        )
        run(
            [
                *pip,
                "download",
                "--require-hashes",
                "--only-binary=:all:",
                "--no-deps",
                "--index-url",
                "https://pypi.org/simple",
                "--dest",
                wheelhouse,
                "-r",
                lock,
            ],
            work,
        )
        # Direct official URLs avoid combining CPU and PyPI indexes during resolution.
        run(
            [
                *pip,
                "download",
                "--require-hashes",
                "--no-deps",
                "--no-index",
                "--dest",
                wheelhouse,
                "-r",
                urls,
            ],
            work,
        )
        local = work / "local.txt"
        lines = []
        for name, item in selected.items():
            wheels = list(wheelhouse.glob(f"{name}-*.whl"))
            if len(wheels) != 1 or digest(wheels[0]) != item["sha256"]:
                raise ValueError(f"Downloaded {name} wheel differs from reviewed hash")
            lines.append(f"{wheels[0].as_uri()} --hash=sha256:{item['sha256']}\n")
        local.write_text("".join(lines), encoding="utf-8")
        run(
            [
                *pip,
                "install",
                "--force-reinstall",
                "--no-index",
                "--find-links",
                wheelhouse,
                "--require-hashes",
                "-r",
                lock,
                "-r",
                local,
            ],
            work,
        )
        run([*pip, "check"], work)
    expected = dict(re.findall(r"^([\w-]+)==([^\s;\\]+)", lock.read_text(), re.M))
    expected = {name.replace("_", "-").lower(): version for name, version in expected.items()}
    expected["torch"] = spec["torch"]
    if sys.platform == "linux":
        expected["triton"] = spec["triton"]
    output = subprocess.check_output(
        [python, "-I", "-m", "pip", "list", "--format=json"], env=environment(), text=True
    )
    installed = {
        item["name"].lower().replace("_", "-"): item["version"] for item in json.loads(output)
    }
    if {k: v for k, v in installed.items() if k != "pip"} != expected:
        raise ValueError(f"Installed closure differs from lock: {installed}; expected {expected}")
    save(
        directory / "profile.json",
        {
            "profile": profile,
            "key": key,
            "locks": identity()["locks"],
            "installed": installed,
        },
    )


def validate_report(report, backend, check):
    expected_names = ["forward"]
    if check == "training":
        expected_names += ["activation-forward-backward", "lora-two-step"]
    if (
        report.get("status") != "passed"
        or report.get("backend") != backend
        or (report.get("native_cuda") is not (backend == "cuda"))
        or [item.get("name") for item in report.get("checks", [])] != expected_names
        or any(item.get("status") != "passed" for item in report.get("checks", []))
    ):
        raise ValueError(f"Incomplete or inconsistent training evidence: {report}")
    if check == "training":
        activation, training = report["checks"][1:]
        dtypes = ["float32"] if backend == "interpreter" else ["float32", "float16", "bfloat16"]
        expected_cases = [
            {"dtype": dtype, "elements": n} for dtype in dtypes for n in (0, 1, 7, 257, 1025)
        ]
        if (
            activation.get("cases") != expected_cases
            or activation.get("finite_difference") is not (backend == "cpu")
            or training.get("steps") != 2
            or training.get("frozen_base") != "unchanged"
            or (training.get("zero_initialized_b") is not True)
            or len(training.get("losses", [])) != 2
            or not all(
                isinstance(value, (float, int)) and math.isfinite(value)
                for value in training.get("losses", [])
            )
        ):
            raise ValueError("Training evidence omitted required numerical cases or updates")


def require_new_report(report_path):
    if report_path.exists() or report_path.is_symlink():
        raise ValueError(f"Report already exists; use a new output path: {report_path}")


def test(bundle, directory, backend, artifact, report_path, naive=False):
    require_new_report(report_path)
    manifest = verify(bundle)
    profile = json.loads((directory / "profile.json").read_text(encoding="utf-8"))
    if profile["locks"] != identity()["locks"]:
        raise ValueError("Runtime was provisioned with different profile locks")
    python = python_in(directory / "runtime")
    output = subprocess.check_output(
        [python, "-I", "-m", "pip", "list", "--format=json"], env=environment(), text=True
    )
    installed = {
        item["name"].lower().replace("_", "-"): item["version"]
        for item in json.loads(output)
        if item["name"] != "soup-training-contract-lab"
    }
    if installed != profile["installed"]:
        raise ValueError("Runtime dependencies changed after provisioning")
    with tempfile.TemporaryDirectory(prefix="soup-ml-test-") as temporary:
        work = Path(temporary)
        probe_report = work / "probe.json"
        check = "forward" if naive else "training"
        if naive:
            command = [
                python,
                "-I",
                "-c",
                (
                    "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));"
                    "runpy.run_module('soup_training_probe.cli',run_name='__main__')"
                ),
                bundle / "source/src",
            ]
        else:
            wheel = next((bundle / "dist").glob("*.whl"))
            if artifact == "sdist":
                builder = work / "builder"
                venv.create(builder, with_pip=True, symlinks=os.name != "nt")
                builder_pip = [python_in(builder), "-I", "-m", "pip"]
                run(
                    [
                        *builder_pip,
                        "install",
                        "--require-hashes",
                        "--only-binary=:all:",
                        "-r",
                        ROOT / "requirements/build.txt",
                    ],
                    work,
                )
                run(
                    [
                        *builder_pip,
                        "wheel",
                        "--no-index",
                        "--no-deps",
                        "--no-build-isolation",
                        "--wheel-dir",
                        work / "rebuilt",
                        next((bundle / "dist").glob("*.tar.gz")),
                    ],
                    work,
                )
                wheel = next((work / "rebuilt").glob("*.whl"))
            run(
                [
                    python,
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--force-reinstall",
                    "--no-index",
                    "--no-deps",
                    wheel,
                ],
                work,
            )
            run([python, "-I", "-m", "pip", "check"], work)
            executable = python.with_name(
                "soup-training-probe.exe" if os.name == "nt" else "soup-training-probe"
            )
            run([executable, "--version"], work)
            command = [python, "-I", "-O", "-m", "soup_training_probe.cli"]
        code = run(
            [*command, "--backend", backend, "--check", check, "--report", probe_report],
            work,
            check=False,
        )
        if not probe_report.is_file():
            raise ValueError("Probe exited without writing its contract report")
        report = json.loads(probe_report.read_text(encoding="utf-8"))
        report.update(
            artifact=artifact,
            naive=naive,
            fault=manifest["fault"],
            artifact_identity=manifest,
            profile=profile,
            exit_code=code,
        )
        if code:
            save(report_path, report)
            raise RuntimeError(f"Training contract failed: {report.get('error')}")
        validate_report(report, backend, check)
        if report.get("torch") != profile["installed"]["torch"] or (
            backend != "cpu" and report.get("triton") != profile["installed"].get("triton")
        ):
            raise ValueError("Probe used a different PyTorch/Triton version than the profile")
        if not naive and not Path(report["module"]).is_relative_to(directory / "runtime"):
            raise ValueError("Training probe was imported outside the installed runtime")
        save(report_path, report)


def bare(bundle, report_path):
    require_new_report(report_path)
    verify(bundle)
    with tempfile.TemporaryDirectory(prefix="soup-ml-bare-") as temporary:
        work = Path(temporary)
        probe_report = work / "probe.json"
        runtime = work / "runtime"
        venv.create(runtime, with_pip=True, symlinks=os.name != "nt")
        python = python_in(runtime)
        run(
            [
                python,
                "-I",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                next((bundle / "dist").glob("*.whl")),
            ],
            work,
        )
        run([python, "-I", "-m", "pip", "uninstall", "--yes", "pip", "setuptools"], work)
        command = [
            python.with_name(
                "soup-training-probe.exe" if os.name == "nt" else "soup-training-probe"
            )
        ]
        run([*command, "--help"], work)
        run([*command, "--version"], work)
        code = run([*command, "--report", probe_report], work, check=False)
        report = json.loads(probe_report.read_text(encoding="utf-8"))
        if code != 1 or report.get("error", {}).get("code") != "training-dependencies-missing":
            raise ValueError(f"Bare CLI failed for the wrong reason: {report}")
        save(report_path, report)


def gpu_guard(directory, report_path):
    require_new_report(report_path)
    python = python_in(directory / "runtime")
    with tempfile.TemporaryDirectory(prefix="soup-gpu-guard-") as temporary:
        probe_report = Path(temporary) / "probe.json"
        code = run(
            [
                python,
                "-I",
                "-O",
                "-m",
                "soup_training_probe.cli",
                "--backend",
                "cuda",
                "--report",
                probe_report,
            ],
            directory,
            check=False,
        )
        report = json.loads(probe_report.read_text(encoding="utf-8"))
    if (
        code != 3
        or report.get("error", {}).get("code") != "gpu-unavailable"
        or (report.get("native_cuda") is not False or report.get("status") != "failed")
    ):
        raise ValueError(f"CPU worker incorrectly accepted a GPU gate: {report}")
    save(report_path, report)


def experiment(directory, runtime):
    directory.mkdir(parents=True, exist_ok=False)
    results = []
    for fault in FAULTS:
        bundle = directory / fault
        build(fault, bundle)
        cases = [("cpu", True, "")]
        if fault == "fixed":
            cases += [("cpu", False, ""), ("interpreter", False, "")]
        else:
            backend = "interpreter" if fault == "tail-mask" else "cpu"
            expected = {
                "backward": "gradient-mismatch",
                "adapter-detach": "adapter-gradient-missing",
                "missing-resource": "kernel-resource-missing",
                "tail-mask": "forward-mismatch",
            }[fault]
            cases += [(backend, False, expected)]
        for backend, naive, expected in cases:
            for artifact in ["wheel"] if naive else ["wheel", "sdist"]:
                name = f"{fault}-{backend}-{'source' if naive else artifact}"
                report = directory / f"{name}.json"
                command = [
                    sys.executable,
                    Path(__file__).resolve(),
                    "test",
                    bundle,
                    runtime,
                    "--backend",
                    backend,
                    "--artifact",
                    artifact,
                    "--report",
                    report,
                ]
                if naive:
                    command.append("--naive")
                with (directory / f"{name}.log").open("w", encoding="utf-8") as log:
                    process = subprocess.run(
                        list(map(str, command)),
                        cwd=ROOT,
                        env=environment(),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=900,
                    )
                observed = json.loads(report.read_text()) if report.exists() else {}
                valid = (
                    (
                        process.returncode != 0
                        and observed.get("exit_code") == 1
                        and observed.get("error", {}).get("code") == expected
                        and observed.get("status") == "failed"
                    )
                    if expected
                    else process.returncode == 0 and observed.get("status") == "passed"
                )
                results.append(
                    {
                        "case": name,
                        "verified": valid,
                        "expected_error": expected,
                        "exit_code": process.returncode,
                        "report": report.name,
                    }
                )
                save(directory / "results.json", results)
                print(
                    f"{'PASS' if valid else 'FAIL'}: {name}; expected={expected or 'green'}",
                    flush=True,
                )
                if not valid:
                    raise ValueError(f"Unexpected fault outcome; inspect {directory / name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    builder = commands.add_parser("build")
    builder.add_argument("fault", choices=FAULTS)
    builder.add_argument("bundle", type=Path)
    provisioner = commands.add_parser("provision")
    provisioner.add_argument("profile", choices=("floor", "modern"))
    provisioner.add_argument("directory", type=Path)
    tester = commands.add_parser("test")
    tester.add_argument("bundle", type=Path)
    tester.add_argument("directory", type=Path)
    tester.add_argument("--backend", choices=("cpu", "interpreter", "cuda"), required=True)
    tester.add_argument("--artifact", choices=("wheel", "sdist"), default="wheel")
    tester.add_argument("--report", type=Path, required=True)
    tester.add_argument("--naive", action="store_true")
    bare_parser = commands.add_parser("bare")
    bare_parser.add_argument("bundle", type=Path)
    bare_parser.add_argument("--report", type=Path, required=True)
    guard = commands.add_parser("gpu-guard")
    guard.add_argument("directory", type=Path)
    guard.add_argument("--report", type=Path, required=True)
    experiments = commands.add_parser("experiment")
    experiments.add_argument("directory", type=Path)
    experiments.add_argument("runtime", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        build(args.fault, args.bundle.resolve())
    elif args.action == "provision":
        provision(args.profile, args.directory.resolve())
    elif args.action == "bare":
        bare(args.bundle.resolve(), args.report.resolve())
    elif args.action == "gpu-guard":
        gpu_guard(args.directory.resolve(), args.report.resolve())
    elif args.action == "experiment":
        experiment(args.directory.resolve(), args.runtime.resolve())
    else:
        test(
            args.bundle.resolve(),
            args.directory.resolve(),
            args.backend,
            args.artifact,
            args.report.resolve(),
            args.naive,
        )


if __name__ == "__main__":
    main()
