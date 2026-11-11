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

The first remote dependency matrix, run 42971946086, also failed on Windows before application
execution: Git's automatic CRLF conversion changed the lock-file bytes and therefore the profile
hash. A local regression test reproduced a Windows-style checkout and failed before correction.
The repository now enforces LF for requirements inputs/locks; identity verification remains
enabled. The initial run is retained and is not counted as proof of a dependency defect.

## Boundaries

Local Linux / CPython 3.13.9 validation passed 66 regression/unit tests, both installed artifacts
with normal and optimized smoke checks, all six dependency comparisons, actionlint, Ruff, strict
metadata checks and Docker. Full logs and hashes are under the timestamped `.evidence/preflight-*`
directory; GitHub runs below must be inspected separately before claiming cross-platform success.

During the initial private-repository setup, GitHub's API returned HTTP 403 when inspecting
rulesets and protected main, requiring a plan upgrade or a public repository. That response is
historical: the repository is now public. Main now requires a PR and an up-to-date `release-ready`
check, including for admins; branch force pushes/deletion and `v*` tag updates/deletion are blocked.
These settings were applied separately from workflows; definitions are in `.github/repository-policy/`.
Independent approval remains disabled because there is one maintainer. The tag-only TestPyPI
environment cannot substitute for protected workflow and maintainer access.

No new TestPyPI upload, production PyPI publication, paid GPU lease or employer email is part of
these follow-up checks. The earlier applicant's personal installation verification applies to
published 0.9.3 only. All new verification is AI-assisted until independently checked by the applicant.

## Verified remote results

[Fixed release matrix, ten OS/Python combinations](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972551690) and [fixed dependency matrix, eight combinations](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972551692) are green at `80d3de365cb0819065df51b11720ebc07237e8bd`.

- **python310**: [naive green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972041217) / [hardened red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972045975). Expected error: `ImportError: cannot import name 'UTC'`. Confirmed separately in all 2 failed-job logs; pair/fixture commit `6f9e1c4`.
- **windows**: [naive green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972050314) / [hardened red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972054409). Expected error: `ModuleNotFoundError: No module named 'pwd'`. Confirmed separately in all 5 failed-job logs; pair/fixture commit `6f9e1c4`.
- **missing-data**: [naive green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972058969) / [hardened red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972064123). Expected error: `FileNotFoundError:`. Confirmed separately in all 11 failed-job logs; pair/fixture commit `6f9e1c4`.
- **entrypoint**: [naive green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972069720) / [hardened red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972074373). Expected error: `ImportError: cannot import name 'missing_main'`. Confirmed separately in all 11 failed-job logs; pair/fixture commit `6f9e1c4`.
- **removed-api**: [naive green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972673465/job/130364641243) / [hardened red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972673465). Expected error: `unexpected keyword argument 'proxies'`. Confirmed separately in all 4 failed-job logs; pair/fixture commit `80d3de3`.
- **undeclared-runtime**: [naive green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972678006/job/130364668279) / [hardened red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42972678006). Expected error: `ModuleNotFoundError: No module named 'tenacity'`. Confirmed separately in all 8 failed-job logs; pair/fixture commit `80d3de3`.

The initial dependency runs 42971946086, 42972175181 and 42972179805 included Windows lock-byte mismatches. They are retained but excluded from the six primary demonstrations. All 16 follow-up run records and raw ZIP logs were exported; no failure was deleted or changed to success.

The updated index verifier also checked the already-published baseline against its original release bundle: both published file hashes and a fresh TestPyPI installation passed on Linux / CPython 3.13.9. This was an AI-assisted read-only verification, not a new publication.
