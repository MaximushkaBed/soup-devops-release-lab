# Soup DevOps release lab

A dependency-free Python CLI and a release pipeline that tests the **installed artifacts**.
Supported targets: CPython 3.10–3.14 on Ubuntu and Windows x64. This is an internship exercise,
not a production publisher. The only configured index is TestPyPI.

The follow-up [training fixture](docs/training-contracts.md) exercises LoRA gradients, optimizer
updates and Triton SwiGLU on two pinned PyTorch/Triton stacks. It is independently packaged,
supports Python 3.11–3.13, and leaves the published 0.9.3 baseline unchanged. CPU interpretation
is explicitly distinguished from native GPU execution.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements/ci.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m build --no-isolation --outdir bundle/dist
python -m twine check --strict bundle/dist/*
python tools/check_wheel.py bundle/dist/*.whl
python tools/provenance.py record bundle
python tools/test_artifact.py bundle/dist/*.whl
python tools/test_artifact.py bundle/dist/*.tar.gz
```

On Windows activate with `.venv\Scripts\Activate.ps1`. The artifact tester accepts a glob itself,
so the same arguments work in PowerShell. Building uses locked tools without build isolation;
sdist testing rebuilds in a separate environment, then installs into a fresh runtime environment.
No source checkout, editable install, dependency resolver cache, or test dependencies are available
in that runtime. Run the console command after installation: `soup-release --name Soup --json`.

## Local preflight

After installing the locked CI dependencies above, install
[actionlint 1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12), checking the release's
SHA-256 checksum. Make it available on PATH, or pass its absolute path with `--actionlint`.
Docker must be installed and its daemon running. Run from the repository root:

```sh
python tools/preflight.py
```

This checks workflow syntax (without optional ShellCheck), Ruff, all tests, a fresh build, strict
metadata, wheel RECORD/content/source-byte contracts, provenance, and negative guards with normal
and optimized Python. It then tests both
installed artifacts, builds Docker using the actual Dockerfile and ignore rules, and validates the
container's CLI output. Add `--with-ml` to also run the separate installed CPU/Triton-interpreter
training contracts and 17 controlled training comparisons. That optional fixture downloads roughly
0.5 GB and needs about 2 GB of temporary disk space. Reuse a verified existing profile with
`--with-ml --ml-runtime .evidence/ml-environments/floor`; its inventory is checked before each test.
Docker uses an isolated configuration directory, a temporary container and a temporary image tag;
both are removed even after a failed smoke test. Builder network access is needed for hashed tools;
application execution uses local deterministic data. No release is published by preflight.

Each run creates a separate `.evidence/preflight-*/` directory with the candidate wheel/sdist,
command output, exit codes, durations, commit, working-tree status, source hashes and `summary.json`.
The first failed gate stops the run with a nonzero exit code and keeps its log. Commands that time
out have their process trees terminated. Source hashes are checked again at completion, and a
changed candidate cannot receive a passing report. Added, removed and renamed Git-visible source
files are checked along with modified file contents; ignored generated output is excluded. Missing actionlint
or Docker is an error. `--skip-docker` explicitly produces a `partial` report, never `passed`.
These local checks cover the current OS/Python only; the remote ten-target matrix remains required.
The optional ML preflight requires Linux x86_64 and Python 3.11–3.13. The greeting package's
separate artifact tester covers its other targets. Native GPU validation remains unexecuted.

## Training contracts for Soup

After installing the locked CI tools above, run from the repository root:

```sh
python tools/ml_lab.py build fixed .evidence/training-bundle
python tools/ml_lab.py bare .evidence/training-bundle --report .evidence/training-bare.json
python tools/ml_lab.py provision floor .evidence/ml-environments/floor
python tools/ml_lab.py test .evidence/training-bundle .evidence/ml-environments/floor --backend cpu --report .evidence/training-cpu.json
python tools/ml_lab.py test .evidence/training-bundle .evidence/ml-environments/floor --backend interpreter --artifact sdist --report .evidence/training-interpreter.json
python tools/ml_lab.py experiment .evidence/training-experiments .evidence/ml-environments/floor
```

Use new build/profile/experiment directories for independent runs. For the other stack, provision
`modern` into another directory. The independent **Training contracts** workflow runs when its
code, tools or locks change, and on manual dispatch. Its matrix covers Linux Python
3.11/3.12/3.13 × two stacks, plus Windows Python 3.12 × two stacks.
Each tests the installed wheel and rebuilt sdist; Linux also executes real Triton interpretation
in FP32. A separate two-OS job verifies help/version without ML dependencies. Failed reports and
original fault logs are uploaded. It does not gate publication of the unrelated greeting CLI.
See [contracts and limits](docs/training-contracts.md).

Report output paths must also be new. Existing reports are preserved and rejected before work
starts. Each probe writes into a private temporary directory; its exit code alone cannot establish
success. Only a newly written and validated report is exported as successful evidence.

Pipeline regression tests live in `tests/pipeline/`; the deliberately naive workflow continues
to run only `tests/unit/`. Negative tests require the expected cause of rejection, including with
`python -O`. Installed CLI checks also cover default/text output, Unicode and empty names, help,
missing arguments, stderr and exit codes.

The wheel contract reads every member through the locked `wheel` library to validate RECORD
hashes. It rejects duplicate members, missing or unexpected files (including `.pth` startup hooks),
changed package/license bytes and altered entry points. It runs before the original wheel is
uploaded and on the wheel rebuilt from each sdist. Installed tests separately check the greeting
resource and entry-point metadata. RECORD consistency alone does not establish that code is safe.
Git attributes keep compared source, resource and license bytes in LF form on Windows as well
as Linux, including checkouts configured with `core.autocrlf=true`.

## Demonstrations

Dispatch **Naive CI** and **Release checks** with the same `fault` choice:
`python310`, `windows`, `missing-data`, or `entrypoint`. The naive workflow tests source on Linux
3.12; all four cases should be green. The hardened workflow tests wheel and sdist on ten OS/Python
combinations and in Docker; each incident should be red. `fixed` is the corrected version.
Faults are deterministic patches to a clean checkout, printed in logs, and never injected on a tag.
No failed run is deleted or masked with `continue-on-error`.

## Real dependency compatibility

The separate installable [HTTP client fixture](fixtures/http-client/README.md) adds real HTTPX and
Tenacity dependencies without changing the published greeting package. It handles retryable HTTP
errors, permanent errors, bounded retries and response validation using deterministic transports.

Run a complete local comparison (use a new output directory each time):

```sh
python tools/dependency_lab.py experiment .evidence/dependency-comparison
```

The fixed wheel must pass with both `httpx==0.27.2` / `tenacity==8.5.0` and `httpx==0.28.1` /
`tenacity==9.1.2`. These are explicit compatibility targets, not floating latest dependencies.
Both profiles lock transitive requirements with hashes. Downloads are checked in a separate
environment, then runtime dependencies are resolved offline from only those verified wheels.

Two additional incidents must pass in the old, pre-populated development environment:

- `removed-api`: the client uses `proxies`, removed in HTTPX 0.28. A clean current-profile install
  passes dependency resolution but its installed CLI raises the expected `TypeError`.
- `undeclared-runtime`: Tenacity is omitted from package metadata. Development tests pass, and
  even `pip check` is green after a clean installation; running the CLI exposes the missing import.

Each local comparison preserves the actual failing exit code and diagnostic in separate logs and
`results.json`; the comparison succeeds only when the expected specific failure was observed.
The dispatch-only historical **Dependency compatibility** workflow runs the same wheel on Ubuntu/Windows,
Python 3.10/3.14, and both dependency profiles (eight combinations). Its dispatch fault modes
leave broken combinations red; there is no publication job. See [iteration details](docs/iteration-2.md).

**Fresh dependency canary** runs weekly and on manual dispatch, separately from releases. It builds
the fixed HTTP fixture once and resolves fresh PyPI dependencies within its declared support ranges
on Python 3.10 and 3.14. It uses a single explicit index, no pip configuration/cache, and a clean
runtime outside the checkout; the HTTP scenarios themselves use deterministic offline transports.
Successful reports preserve exact installed versions, artifact hashes and run identity. A failed
probe remains red with its original Actions log; an old report cannot be reused. This complements
the two frozen historical profiles and does not automatically update their locks.

To reproduce on the current OS/Python after installing the locked build tools:

```sh
python tools/dependency_lab.py build fixed .evidence/fresh-bundle
python tools/dependency_lab.py test .evidence/fresh-bundle --profile fresh --report .evidence/fresh-report.json
```

Use new bundle/report paths for each run. The dependency-free greeting CLI itself has no runtime
dependency graph to float; this canary belongs to the HTTP fixture.

See [incident details](docs/incidents.md), [security and limits](docs/security.md),
[GPU design](docs/gpu-ci.md), [evidence](docs/evidence.md), and [AI disclosure](docs/ai-usage.md).
The two-page submission note and email draft are kept locally and sent separately.
Fresh matrix results and all six demonstrated failures are in
[iteration-2.md](docs/iteration-2.md); the original evidence remains available separately.

## Releases

See [TestPyPI setup](docs/testpypi.md). Baseline `v0.9.3` is already published; keep its tag unchanged.
For a future release, bump the version and version expectations, and use a new matching tag.
A release must be on `main`, match package metadata, pass all gates, and publish the same immutable
artifact that was tested. No rebuilding occurs in the publisher. Only that job receives OIDC access.
The always-running `release-ready` job checks the explicit results of build, the complete installed
artifact matrix and Docker: every result must be `success`. Failure, cancellation, skipped/missing
jobs and unknown results are rejected. Publish depends on this gate; its intentional skip on PRs
and ordinary main pushes is separate. GitHub enforces PRs and an up-to-date `release-ready` check
from GitHub Actions on `main`, including for administrators. Force pushes and branch deletion are
blocked; active rules also prevent updating or deleting `v*` release tags. The applied definitions
are in [.github/repository-policy/](.github/repository-policy/). Independent approval is currently
set to zero because this repository has one maintainer; a second reviewer is needed to enforce it.
Documentation-only pushes also run release checks.
A final clean install verifies the version and SHA-256 digests served by TestPyPI.
Index verification also runs after a failed upload attempt, since a two-file upload can leave
only part of the release published. It cannot turn the failed publisher green or undo uploaded
files. A cancelled workflow still requires manual inspection of the index before retrying.

## Updating tools

The `.in` files pin direct tools. Regenerate hashed, cross-platform locks with:

```sh
uv pip compile requirements/build.in --python-version 3.10 --universal --generate-hashes -o requirements/build.txt
uv pip compile requirements/ci.in --python-version 3.10 --universal --generate-hashes -o requirements/ci.txt
```

Review dependency identities and lock changes. Hashes verify selected bytes, not that a dependency is safe.
