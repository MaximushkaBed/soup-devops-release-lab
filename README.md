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

## Demonstrations

Dispatch **Naive CI** and **Release checks** with the same `fault` choice:
`python310`, `windows`, `missing-data`, or `entrypoint`. The naive workflow tests source on Linux
3.12; all four cases should be green. The hardened workflow tests wheel and sdist on ten OS/Python
combinations and in Docker; each incident should be red. `fixed` is the corrected version.
Faults are deterministic patches to a clean checkout, printed in logs, and never injected on a tag.
No failed run is deleted or masked with `continue-on-error`.

See [incident details](docs/incidents.md), [security and limits](docs/security.md),
[GPU design](docs/gpu-ci.md), [evidence](docs/evidence.md), and [AI disclosure](docs/ai-usage.md).
The submission note will be `docs/submission.pdf` (at most two pages).

## Releases

See [TestPyPI setup](docs/testpypi.md). Push `v0.9.3` only after its Trusted Publisher is registered.
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
