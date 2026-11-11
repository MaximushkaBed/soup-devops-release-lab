# Follow-up validation, 11 November 2026

The published 0.9.3 release, original tag, original runs and original exported results remain the
baseline. This iteration strengthens checks and adds a separate installable dependency fixture;
it does not republish 0.9.3 or claim that every possible defect can be detected.

## Additional failure classes

The dependency fixture makes an HTTP request through HTTPX's in-memory transport, retries transient
errors using Tenacity, validates the returned data, and checks permanent failures and retry limits.
It never contacts a real API. Two direct-dependency profiles and their complete transitive hashes
are committed under `requirements/compat-*`.

The `removed-api` experiment introduces the real HTTPX `proxies` compatibility break. The same
wheel works with HTTPX 0.27.2 but raises `TypeError` with 0.28.1. The `undeclared-runtime` experiment
omits Tenacity from metadata; a development environment masks this, while a clean installation
fails with `ModuleNotFoundError`, despite a successful dependency resolution and `pip check`.
See the [upstream removal notice](https://github.com/encode/httpx/blob/0.28.1/CHANGELOG.md#0280-28th-november-2024).

The local experiment command tests two valid installations and two naive/clean failure pairs.
It requires a matching error message, preserves each return code and never treats an arbitrary
failure as proof. The dedicated Actions matrix covers two operating systems, two Python extremes
and two library profiles. This supplements the original ten-target Python/OS matrix.

## Guards and operational failures

- Negative release guards and installed smoke checks use explicit exceptions and are exercised
  under optimized Python. The previous negative checker could falsely report success with `-O`;
  a regression test first reproduced this failure and now rejects it.
- Missing or duplicated package identity headers are rejected before upload. Stale commit/run/
  attempt, changed bytes, unexpected dependencies, Python range and wrong tags have negative tests.
- Registry propagation delays and temporary errors receive bounded retries. Wrong identity,
  duplicate or unexpected files, yanked files, incorrect digests and download origins stop at once.
- Pip/Python environment overrides are removed from isolated installation commands. A missing
  artifact glob cannot silently skip a requested check.
- Preflight keeps logs and an atomic JSON report, records dirty source hashes, rejects source
  changes during a run, stops timed-out process trees and cleans up its Docker container/image.

One local fixture experiment failed before application execution because the host filesystem had
only about 196 MiB free and Python's venv builder copied large interpreter binaries. This was an
environment failure, not evidence of a dependency defect. The failed log is preserved. POSIX test
venvs now use interpreter symlinks; Windows retains copies. Preflight also checks available space.

## Boundaries

Local Linux / CPython 3.13.9 validation passed 65 regression/unit tests, both installed artifacts
with normal and optimized smoke checks, all six dependency comparisons, actionlint, Ruff, strict
metadata checks and Docker. Full logs and hashes are under the timestamped `.evidence/preflight-*`
directory; GitHub runs below must be inspected separately before claiming cross-platform success.

GitHub's API returned HTTP 403 when inspecting rulesets and protected main for this private
repository, with a requirement to upgrade the account or make the repository public. Enforced
main/tag review protection therefore remains unavailable on the present plan. The repository
has not been made public and no subscription change was made. The tag-only TestPyPI environment
exists, but it cannot substitute for protected workflow and maintainer access.

No new TestPyPI upload, production PyPI publication, paid GPU lease or employer email is part of
these follow-up checks. The earlier applicant's personal installation verification applies to
published 0.9.3 only. All new verification is AI-assisted until independently checked by the applicant.
