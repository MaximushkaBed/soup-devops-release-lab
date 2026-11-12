# One-off native CUDA validation

This supplemental experiment ran the independently written LoRA/SwiGLU fixture on a real
NVIDIA RTX A4000. The source commit is `463e000c81426b96da77455f9d9da12967957aaa`; every packaged
training source file was compared with the current tree and remains identical.

`run.json` records hardware, selected software, cost assumptions and verified deletion.
`summary.json` retains the actual input receipt, installed inventory and case outcomes.
Each JSON report has its corresponding raw `.txt` log; filenames were changed from `.log`
without changing contents. `SHA256SUMS` checks the recorded evidence files.

## Results

- `fixed-wheel.json` and `fixed-sdist.json`: native CUDA success, 15 activation cases each
  (three dtypes × five sizes), forward/backward comparisons and two LoRA optimizer updates.
- `backward.json`, `adapter-detach.json`, `missing-resource.json`, `tail-mask.json`: actual
  nonzero exits with the expected diagnostic. Missing resource fails before GPU execution.
- `memcheck.txt`: Compute Sanitizer memcheck returned exit 0 and `ERROR SUMMARY: 0 errors`.
  Its exact tool version was not recorded; racecheck was not run.

The runtime was Python 3.12.13, Torch 2.6.0+cu124 and Triton 3.2.0. The GPU driver was
535.54.03. The 679-second lease at the quoted $0.96/hour estimates $0.18 compute; billing
was not independently verified. The instance was deleted. This was one controlled session,
not a deployed nightly/release GPU scheduler or a monthly budget-enforcement service.

## Reproduce the numerical contracts

Use a Linux NVIDIA SM80+ host with a CUDA-compatible driver, Python 3.12 and enough free disk
for the pinned CUDA dependencies. Install the repository's locked build tools, then build:

```sh
python tools/ml_lab.py build fixed /tmp/soup-cuda-bundle
python3.12 -m venv /tmp/soup-cuda-runtime
/tmp/soup-cuda-runtime/bin/python -m pip install --require-hashes --only-binary=:all: -r docs/gpu-validation/2026-11-12/runtime-cuda.txt
/tmp/soup-cuda-runtime/bin/python -m pip install --no-deps /tmp/soup-cuda-bundle/dist/*.whl
mkdir /tmp/soup-cuda-isolated
cd /tmp/soup-cuda-isolated
/tmp/soup-cuda-runtime/bin/python -I -O -m soup_training_probe.cli --backend cuda --report wheel.json
compute-sanitizer --tool memcheck --error-exitcode 86 --target-processes all /tmp/soup-cuda-runtime/bin/python -I -O -m soup_training_probe.cli --backend cuda --report memcheck.json
```

Unset `TRITON_INTERPRET` and `PYTHONPATH` before execution. Use fresh output directories.
`run_cuda.py` and `bootstrap.sh` are the exact one-off runner scripts; they also rebuild the sdist
in a separate builder and exercise each fault with `tools/ml_lab.py build <fault>`. Their input
receipt and uploaded distributions were generated locally before leasing the GPU. The minimal
commands above reproduce the positive contract; they do not recreate the cloud lease.

No throughput, memory-saving, race-freedom or production Soup compatibility claim follows from
this run. Automatic rental/OIDC brokerage and the proposed $10/month cap remain undeployed.
