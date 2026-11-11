"""Run an installed training contract and emit explicit evidence for its actual backend."""

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import sys
from importlib.resources import files
from pathlib import Path

from . import __version__
from .errors import ContractError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--backend", choices=("cpu", "interpreter", "cuda"), default="cpu")
    parser.add_argument("--check", choices=("forward", "training"), default="training")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = {
        "schema": 1,
        "status": "running",
        "backend": args.backend,
        "native_cuda": False,
        "checks": [],
        "python": platform.python_version(),
        "platform": sys.platform,
        "package": __version__,
        "module": str(Path(__file__).resolve()),
    }
    code = 0
    try:
        if args.backend == "interpreter":
            os.environ["TRITON_INTERPRET"] = "1"
        if args.backend == "cuda" and os.environ.get("TRITON_INTERPRET") == "1":
            raise ContractError(
                "interpreter-is-not-gpu", "Native CUDA validation cannot use interpreter mode"
            )
        try:
            contract = json.loads(
                files("soup_training_probe").joinpath("kernel-contract.json").read_text()
            )
        except FileNotFoundError as error:
            raise ContractError(
                "kernel-resource-missing", "Installed wheel lacks kernel-contract.json"
            ) from error
        if contract.get("schema") != 1 or contract.get("operation") != "swiglu":
            raise ContractError(
                "kernel-contract-invalid", "Unexpected kernel contract schema/operation"
            )
        if importlib.util.find_spec("torch") is None:
            raise ContractError(
                "training-dependencies-missing", "Install the train extra or a reviewed profile"
            )
        import torch

        torch.set_num_threads(1)
        report.update(
            torch=torch.__version__,
            cuda_runtime=torch.version.cuda,
            cuda_available=torch.cuda.is_available(),
        )
        if args.backend == "cuda":
            if not torch.cuda.is_available():
                raise ContractError(
                    "gpu-unavailable", "A real CUDA GPU is required; no GPU pass is recorded"
                )
            if torch.cuda.get_device_capability() < (8, 0):
                raise ContractError(
                    "gpu-unsupported", "The native contract requires NVIDIA SM80 or newer"
                )
            report.update(
                gpu=torch.cuda.get_device_name(),
                capability=list(torch.cuda.get_device_capability()),
            )
        if args.backend != "cpu":
            if importlib.util.find_spec("triton") is None:
                raise ContractError(
                    "kernel-dependencies-missing", "Triton is required for this backend"
                )
            report["triton"] = importlib.metadata.version("triton")
        from .checks import activation_checks, forward_check, training_check

        device = "cuda" if args.backend == "cuda" else "cpu"
        report["checks"].append(
            forward_check(
                args.backend, contract["block_size"], contract["tolerances"]["float32"], device
            )
        )
        if args.check == "training":
            report["checks"].append(activation_checks(args.backend, contract, device))
            report["checks"].append(training_check(args.backend, contract, device))
        if args.backend == "cuda":
            torch.cuda.synchronize()
            report["native_cuda"] = True
        report["status"] = "passed"
    except ContractError as error:
        report.update(status="failed", error={"code": error.code, "message": str(error)})
        code = (
            3
            if error.code in ("gpu-unavailable", "gpu-unsupported", "interpreter-is-not-gpu")
            else 1
        )
    except Exception as error:
        report.update(
            status="failed",
            error={"code": "unexpected-error", "message": f"{type(error).__name__}: {error}"},
        )
        code = 1
    serialized = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="", flush=True)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
