"""One-off installed-artifact CUDA contracts; no cloud credentials are needed here."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

CONTEXT = Path(sys.argv[1]).resolve()
WORK = Path(sys.argv[2]).resolve()
RESULTS = WORK / "results"
RESULTS.mkdir(parents=True, exist_ok=False)
UV = str(CONTEXT / "uv")
RUNTIME = WORK / "runtime"
PYTHON = RUNTIME / "bin/python"
ISOLATED = WORK / "isolated"
ISOLATED.mkdir()
ENV = {
    k: v
    for k, v in os.environ.items()
    if not k.startswith(("PYTHON", "PIP_", "UV_")) and k != "TRITON_INTERPRET"
}
ENV.update(
    UV_CACHE_DIR=str(WORK / "cache"),
    UV_PYTHON_INSTALL_DIR=str(WORK / "python"),
    UV_DEFAULT_INDEX="https://pypi.org/simple",
    UV_NO_PROGRESS="1",
    PIP_CONFIG_FILE=os.devnull,
    TRITON_CACHE_DIR=str(WORK / "triton-cache"),
)
SUMMARY = {"status": "running", "cases": [], "sanitizer": "not-run", "benchmark": "not-run"}


def save():
    (RESULTS / "summary.json").write_text(json.dumps(SUMMARY, indent=2) + "\n")


def run(name, command, *, timeout=180, allow_failure=False):
    print("RUN:", name, flush=True)
    started = time.monotonic()
    result = subprocess.run(
        list(map(str, command)),
        cwd=ISOLATED,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    (RESULTS / (name + ".log")).write_text(result.stdout + result.stderr)
    if result.returncode and not allow_failure:
        print((result.stdout + result.stderr)[-6000:], flush=True)
        raise RuntimeError(f"{name}: exit {result.returncode}")
    print(f"EXIT: {name}: {result.returncode}; {time.monotonic() - started:.1f}s", flush=True)
    return result


def probe(name, wheel, expected=None, sanitizer=None):
    run(
        name + "-install",
        [
            UV,
            "--no-config",
            "pip",
            "install",
            "--python",
            PYTHON,
            "--no-index",
            "--no-deps",
            "--reinstall",
            wheel,
        ],
    )
    report = RESULTS / (name + ".json")
    if report.exists():
        raise RuntimeError("Refusing stale report: " + str(report))
    command = [
        str(PYTHON),
        "-I",
        "-O",
        "-m",
        "soup_training_probe.cli",
        "--backend",
        "cuda",
        "--report",
        str(report),
    ]
    if sanitizer:
        command = [
            sanitizer,
            "--tool",
            "memcheck",
            "--error-exitcode",
            "86",
            "--target-processes",
            "all",
            *command,
        ]
    result = run(name, command, allow_failure=True, timeout=240)
    if not report.is_file():
        raise RuntimeError(f"{name}: probe produced no report")
    data = json.loads(report.read_text())
    if expected:
        if (
            result.returncode == 0
            or data.get("status") != "failed"
            or data.get("error", {}).get("code") != expected
        ):
            raise RuntimeError(f"{name}: failed for an unexpected reason: {data}")
    else:
        if (
            result.returncode
            or data.get("status") != "passed"
            or data.get("native_cuda") is not True
        ):
            raise RuntimeError(f"{name}: native CUDA contract failed: {data}")
        if data.get("torch") != "2.6.0+cu124" or data.get("triton") != "3.2.0":
            raise RuntimeError(f"{name}: unexpected numerical stack")
        if not Path(data["module"]).is_relative_to(RUNTIME):
            raise RuntimeError(f"{name}: imported outside the installed runtime")
        checks = {x["name"]: x for x in data["checks"]}
        expected_cases = {
            (dtype, n) for dtype in ("float32", "float16", "bfloat16") for n in (0, 1, 7, 257, 1025)
        }
        actual_cases = {
            (x["dtype"], x["elements"]) for x in checks["activation-forward-backward"]["cases"]
        }
        if actual_cases != expected_cases or checks["lora-two-step"]["steps"] != 2:
            raise RuntimeError(f"{name}: required CUDA cases were omitted")
    SUMMARY["cases"].append(
        {
            "name": name,
            "exit_code": result.returncode,
            "expected_error": expected,
            "verified": True,
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        }
    )
    save()


def main():
    receipt = json.loads((CONTEXT / "receipt.json").read_text())
    for name, digest in receipt["files"].items():
        if hashlib.sha256((CONTEXT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Input bytes differ: " + name)
    SUMMARY["receipt"] = receipt
    save()
    run(
        "hardware",
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
    )
    if shutil.which("gcc") is None and shutil.which("clang") is None:
        raise RuntimeError(
            "Triton requires a C compiler; stop rather than silently changing the VM"
        )
    run("python", [UV, "--no-config", "python", "install", "3.12"], timeout=180)
    run("runtime-create", [UV, "--no-config", "venv", "--python", "3.12", RUNTIME])
    run(
        "runtime-install",
        [
            UV,
            "--no-config",
            "pip",
            "install",
            "--python",
            PYTHON,
            "--require-hashes",
            "--only-binary",
            ":all:",
            "-r",
            CONTEXT / "cuda.txt",
        ],
        timeout=600,
    )
    run("runtime-check", [UV, "--no-config", "pip", "check", "--python", PYTHON])
    inventory = run(
        "runtime-inventory",
        [UV, "--no-config", "pip", "list", "--python", PYTHON, "--format", "json"],
    )
    SUMMARY["installed"] = json.loads(inventory.stdout)
    preflight = run(
        "device",
        [
            PYTHON,
            "-I",
            "-c",
            "import torch\n"
            "if not torch.cuda.is_available(): raise RuntimeError('CUDA unavailable')\n"
            "if torch.cuda.device_count()!=1: raise RuntimeError('Expected one GPU')\n"
            "if torch.cuda.get_device_capability()<(8,0): raise RuntimeError('Requires SM80+')\n"
            "print(torch.cuda.get_device_name(), torch.__version__, torch.version.cuda)",
        ],
    )
    if "A4000" not in preflight.stdout:
        raise RuntimeError("Provider supplied a GPU other than the approved A4000")
    bundles = CONTEXT / "bundles"
    fixed = next((bundles / "fixed/dist").glob("*.whl"))
    probe("fixed-wheel", fixed)
    builder = WORK / "builder"
    run("builder-create", [UV, "--no-config", "venv", "--python", "3.12", builder])
    builder_python = builder / "bin/python"
    run(
        "builder-tools",
        [
            UV,
            "--no-config",
            "pip",
            "install",
            "--python",
            builder_python,
            "--require-hashes",
            "--only-binary",
            ":all:",
            "-r",
            CONTEXT / "build.txt",
        ],
    )
    source = WORK / "sdist-source"
    source.mkdir()
    with tarfile.open(next((bundles / "fixed/dist").glob("*.tar.gz"))) as archive:
        archive.extractall(source, filter="data")
    roots = list(source.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise RuntimeError("Expected one sdist root")
    rebuilt = WORK / "rebuilt"
    run(
        "sdist-rebuild",
        [
            builder_python,
            "-I",
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            rebuilt,
            roots[0],
        ],
    )
    wheels = list(rebuilt.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected one rebuilt wheel")
    probe("fixed-sdist", wheels[0])
    for fault, expected in (
        ("backward", "gradient-mismatch"),
        ("adapter-detach", "adapter-gradient-missing"),
        ("missing-resource", "kernel-resource-missing"),
        ("tail-mask", "forward-mismatch"),
    ):
        probe(fault, next((bundles / fault / "dist").glob("*.whl")), expected)
    candidates = [shutil.which("compute-sanitizer"), "/usr/local/cuda/bin/compute-sanitizer"]
    sanitizer = next((x for x in candidates if x and Path(x).is_file()), None)
    if sanitizer:
        probe("memcheck", fixed, sanitizer=sanitizer)
        SUMMARY["sanitizer"] = "passed"
    else:
        SUMMARY["sanitizer"] = "not-run: compute-sanitizer is unavailable"
    SUMMARY["status"] = "passed"
    save()


try:
    main()
except BaseException as error:
    SUMMARY.update(status="failed", error=f"{type(error).__name__}: {error}")
    save()
    raise
