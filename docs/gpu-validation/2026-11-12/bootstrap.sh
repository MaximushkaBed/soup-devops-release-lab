#!/bin/bash
set -euo pipefail
context=/tmp/soup-cuda-input-20261112
work=/tmp/soup-cuda-work-20261112
test ! -e "$work"
mkdir "$work"
cd "$context"
sha256sum -c SHA256SUMS
chmod u+x "$context/uv"
export UV_PYTHON_INSTALL_DIR="$work/python"
export UV_CACHE_DIR="$work/cache"
./uv --no-config python install 3.12
./uv --no-config venv --python 3.12 "$work/control"
timeout --signal=TERM --kill-after=30s 900s "$work/control/bin/python" \
  "$context/run_cuda.py" "$context" "$work"
