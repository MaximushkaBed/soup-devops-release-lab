# Training contracts relevant to Soup

Soup describes local post-training, LoRA and a gradient bug that survived releases in its
[engineering story](https://trysoup.dev/about). Its
[source](https://github.com/MakazhanAlpamys/Soup) includes optional training dependencies and
Triton kernels. This fixture illustrates numerical release gates that could be adapted to them.
It is independently written: it does not import Soup, reproduce a confirmed Soup defect, claim
compatibility with its full training extra, or train a model.

## What is checked

The installed base CLI shows help/version without PyTorch or Triton; training fails clearly with
`training-dependencies-missing`. Optional `train` and Linux `kernels` extras declare ML dependencies.

Custom autograd SwiGLU is compared with independent native PyTorch autograd. CPU FP32/FP16/BF16
cases cover 0, 1, 7, 257 and 1025 elements with strided inputs. FP64 finite-difference gradcheck
provides another derivative oracle. The real Triton CPU interpreter executes kernels in FP32;
its BF16 limitation is explicit in the
[official guide](https://triton-lang.org/main/programming-guide/chapter-3/debugging.html).
Sentinel NaNs make missing stores deterministic failures; NaNs never compare equal.

A two-projection LoRA fixture starts B at zero and freezes base weights. Two SGD steps are
compared with independent `functional.linear` projections and native autograd, including the
exact trainable set, every A/B gradient, updates and unchanged base weights. Zero first-step A
gradients are valid with zero-initialized B; missing gradients are not. Decreasing loss alone
cannot pass. No model weights, dataset or training GPU are required.

## Four controlled failures

- `backward`: remove a sigmoid derivative term in CPU and Triton backward. Naive forward passes;
  installed training fails with `gradient-mismatch`.
- `adapter-detach`: detach LoRA A. Forward values remain correct; installed training fails with
  `adapter-gradient-missing`.
- `missing-resource`: omit `kernel-contract.json` from package data. Source forward finds it;
  installed wheel and rebuilt sdist fail with `kernel-resource-missing`.
- `tail-mask`: skip the last element in the Triton store mask. CPU source forward passes;
  real interpreter execution fails with `forward-mismatch` and a NaN sentinel.

Fault patches affect temporary copies only. The experiment retains 17 reports: five positive
controls, four naive controls and eight expected failures, covering wheel and rebuilt sdist for
each fault. Nonzero exit alone cannot pass: the structured error must match the expected cause.
Resolver/build/import failures cannot count as the intended numerical failure. Logs and artifacts
are retained, including unexpected outcomes. Dispatch fault modes also leave CI jobs red.

## Versions and provenance

The `floor` target is PyTorch 2.6.0+cpu / Triton 3.2.0 / SymPy 1.13.1. The `modern` target is
PyTorch 2.14.0+cpu / Triton 3.8.0 / SymPy 1.14.0. Both use NumPy 2.2.6. These are explicit tested
targets, not a claim about all intermediate versions or floating latest dependencies.
Linux Python 3.11–3.13 runs both; Windows Python 3.12 runs CPU contracts only.

Official Torch CPU wheel URLs/SHA256s and PyPI Triton hashes are reviewed in `ml-wheels.json`.
Other requirements/build tools use hashed locks. Downloads are verified before offline install;
no mixed extra index, inherited site packages, editable install or restored cache is used.
Exact package inventory and `pip check` verify the dependency closure; inventory drift rejects
subsequent tests. Setuptools remains as an explicit legitimate Torch requirement. The fixture
is force-installed separately for each artifact test into the selected isolated profile.

One build produces a wheel from sdist and binds commit/run/attempt, profile hashes, source snapshot
and both distributions. Consumers verify this manifest. Sdist consumers also rebuild it in a
separate locked builder. Installed probes run outside the checkout with `-I -O`; the reported
module path must be inside the runtime. Reports retain backend, versions, cases, artifact identity
and exit status. The training workflow gates the tag publisher; the fixture itself is not published.

Refresh catalog inputs with `python tools/lock_ml_profiles.py`; regenerate each small dependency
lock with `uv pip compile --universal --python-version 3.11 --generate-hashes --no-annotate
--no-header requirements/ml-floor.in -o requirements/ml-floor.txt` (repeat for `modern`). Review
all changes and rerun the matrix. Catalog refresh reads official metadata without downloading
the large CUDA Torch distribution or buying cloud compute.

## Native GPU boundary

`soup-training-probe --backend cuda --report cuda.json` is implemented for Linux NVIDIA SM80+ with
a separately prepared compatible CUDA Torch/Triton environment. It runs the forward/backward
kernels and numerical contracts on CUDA and synchronizes before success. Interpreter mode and
absent/unsupported devices fail with exit 3. CPU CI explicitly proves that missing CUDA produces
`gpu-unavailable`, `status=failed`, `native_cuda=false`.

No native GPU execution, compiled-kernel correctness, CUDA races, OOM recovery, throughput or
memory improvement is claimed. CPU profiles cannot provision native CUDA. Before enabling a
real GPU release gate, pin a CUDA/driver/image profile, test installed artifacts there, add
sanitizer/failure-path checks and measure warm/cold performance on stable hardware. The
[broker and budget controls](gpu-ci.md) remain a design; no paid GPU was rented.
