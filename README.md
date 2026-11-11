# Soup DevOps release lab

A dependency-free Python CLI and a release pipeline that tests the **installed artifacts**.
Supported targets: CPython 3.10–3.14 on Ubuntu and Windows x64. This is an internship exercise,
not a production publisher. The only configured index is TestPyPI.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements/ci.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m build --no-isolation --outdir bundle/dist
python -m twine check --strict bundle/dist/*
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
metadata, provenance, and negative guards with normal and optimized Python. It then tests both
installed artifacts, builds Docker using the actual Dockerfile and ignore rules, and validates the
container's CLI output. It also runs the six real dependency comparisons described below.
Docker uses an isolated configuration directory, a temporary container and a temporary image tag;
both are removed even after a failed smoke test. Builder network access is needed for hashed tools;
application execution uses local deterministic data. No release is published by preflight.

Each run creates a separate `.evidence/preflight-*/` directory with the candidate wheel/sdist,
command output, exit codes, durations, commit, working-tree status, source hashes and `summary.json`.
The first failed gate stops the run with a nonzero exit code and keeps its log. Commands that time
out have their process trees terminated. Source hashes are checked again at completion, and a
changed candidate cannot receive a passing report. Missing actionlint
or Docker is an error. `--skip-docker` explicitly produces a `partial` report, never `passed`.
These local checks cover the current OS/Python only; the remote ten-target matrix remains required.

Pipeline regression tests live in `tests/pipeline/`; the deliberately naive workflow continues
to run only `tests/unit/`. Negative tests require the expected cause of rejection, including with
`python -O`. Installed CLI checks also cover default/text output, Unicode and empty names, help,
missing arguments, stderr and exit codes.

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
The **Dependency compatibility** workflow also runs the same wheel on Ubuntu/Windows,
Python 3.10/3.14, and both dependency profiles (eight combinations). Its dispatch fault modes
leave broken combinations red; there is no publication job. See [iteration details](docs/iteration-2.md).

See [incident details](docs/incidents.md), [security and limits](docs/security.md),
[GPU design](docs/gpu-ci.md), [evidence](docs/evidence.md), and [AI disclosure](docs/ai-usage.md).
The baseline submission note is `docs/submission.pdf` (two pages). Historical evidence and the
submission describe the published baseline; local improvements require fresh CI evidence before
claiming the updated candidate is release-ready.

## Releases

See [TestPyPI setup](docs/testpypi.md). Baseline `v0.9.3` is already published; keep its tag unchanged.
For a future release, bump the version and version expectations, and use a new matching tag.
A release must be on `main`, match package metadata, pass all gates, and publish the same immutable
artifact that was tested. No rebuilding occurs in the publisher. Only that job receives OIDC access.
A final clean install verifies the version and SHA-256 digests served by TestPyPI.

## Updating tools

The `.in` files pin direct tools. Regenerate hashed, cross-platform locks with:

```sh
uv pip compile requirements/build.in --python-version 3.10 --universal --generate-hashes -o requirements/build.txt
uv pip compile requirements/ci.in --python-version 3.10 --universal --generate-hashes -o requirements/ci.txt
```

Review dependency identities and lock changes. Hashes verify selected bytes, not that a dependency is safe.
