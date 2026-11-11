# Evidence ledger

This ledger records the original published baseline. The later validation work and dependency
experiments are recorded separately in [iteration-2.md](iteration-2.md).

Repository: https://github.com/MaximushkaBed/soup-devops-release-lab (public).
Repository and Actions run pages are public; exported logs are also included with the submission.
No failed run is deleted, hidden, or changed to success. All conclusions below were collected from the GitHub API.

## Local checks

Completed on local Linux / CPython 3.13.9:

- Ruff lint and formatting; three pytest unit tests; actionlint v1.7.12; `git diff --check`.
- Wheel and sdist build; strict twine metadata check.
- Fresh wheel installation and independent sdist rebuild followed by fresh installation.
  Bootstrap packages were removed before installed CLI tests; source paths were excluded.
- Negative integration checks rejected a modified wheel, a substituted commit and tag mismatch.
- Docker image built from a digest-pinned base; CLI succeeded as UID 65532 with no network,
  read-only root filesystem, no capabilities and no-new-privileges.

The checks above were executed by Codex. Separately, the applicant personally created a fresh
venv, installed `soup-release-lab-maximushkabed==0.9.3` from TestPyPI and ran
`soup-release --name Soup --json`. The command returned `Hello, Soup!` and version `0.9.3`
at `2026-11-10T06:36:03.788713+00:00`. The pasted terminal transcript is in ai-usage.md.

## Primary evidence

Demonstration commit: `7fee1977f2b876e7705d4f98c1826dadda126897`.

### python310

[Naive: green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768813463) / [Hardened: red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768819205).
Observed: `ImportError: cannot import name 'UTC' from 'datetime' (/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/datetime.py)`.
Failed jobs: `artifact-tests (windows-2022, 3.10)`, `artifact-tests (ubuntu-24.04, 3.10)`.

### windows

[Naive: green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768825741) / [Hardened: red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768830630).
Observed: `ModuleNotFoundError: No module named 'pwd'`.
Failed jobs: `artifact-tests (windows-2022, 3.12)`, `artifact-tests (windows-2022, 3.14)`, `artifact-tests (windows-2022, 3.11)`, `artifact-tests (windows-2022, 3.13)`, `artifact-tests (windows-2022, 3.10)`.

### missing-data

[Naive: green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768836351) / [Hardened: red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768840516).
Observed: `FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\RUNNER~1\\AppData\\Local\\Temp\\soup-artifact-qkc26yrc\\runtime\\Lib\\site-packages\\soup_release_lab\\greeting.txt'`.
Failed jobs: `docker`, `artifact-tests (ubuntu-24.04, 3.12)`, `artifact-tests (ubuntu-24.04, 3.13)`, `artifact-tests (ubuntu-24.04, 3.11)`, `artifact-tests (ubuntu-24.04, 3.10)`, `artifact-tests (ubuntu-24.04, 3.14)`, `artifact-tests (windows-2022, 3.10)`, `artifact-tests (windows-2022, 3.11)`, `artifact-tests (windows-2022, 3.13)`, `artifact-tests (windows-2022, 3.12)`, `artifact-tests (windows-2022, 3.14)`.

### entrypoint

[Naive: green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768847957) / [Hardened: red](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768853743).
Observed: `ImportError: cannot import name 'missing_main' from 'soup_release_lab.cli' (/tmp/soup-artifact-_th0naog/runtime/lib/python3.13/site-packages/soup_release_lab/cli.py)`.
Failed jobs: `docker`, `artifact-tests (ubuntu-24.04, 3.14)`, `artifact-tests (ubuntu-24.04, 3.11)`, `artifact-tests (windows-2022, 3.10)`, `artifact-tests (windows-2022, 3.13)`, `artifact-tests (windows-2022, 3.11)`, `artifact-tests (windows-2022, 3.14)`, `artifact-tests (ubuntu-24.04, 3.10)`, `artifact-tests (windows-2022, 3.12)`, `artifact-tests (ubuntu-24.04, 3.12)`, `artifact-tests (ubuntu-24.04, 3.13)`.

## Corrected version and TestPyPI

[Fixed matrix and Docker: green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768783598).
[Tag v0.9.3: OIDC upload and index check green](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768719990).
[Published package](https://test.pypi.org/project/soup-release-lab-maximushkabed/0.9.3/).

The tag points to c4ad4a1; the later 7fee197 change only prints a failing CLI's
captured stderr. Package source and packaging configuration are identical.

## All runs, including the original demonstrations

- [42768853743: Release checks / entrypoint](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768853743) - failure (`7fee197`).
- [42768847957: Naive / entrypoint](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768847957) - success (`7fee197`).
- [42768840516: Release checks / missing-data](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768840516) - failure (`7fee197`).
- [42768836351: Naive / missing-data](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768836351) - success (`7fee197`).
- [42768830630: Release checks / windows](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768830630) - failure (`7fee197`).
- [42768825741: Naive / windows](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768825741) - success (`7fee197`).
- [42768819205: Release checks / python310](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768819205) - failure (`7fee197`).
- [42768813463: Naive / python310](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768813463) - success (`7fee197`).
- [42768783598: Release checks / main](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768783598) - success (`7fee197`).
- [42768719990: Release checks / v0.9.3](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768719990) - success (`c4ad4a1`).
- [42768602891: Release checks / main](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768602891) - success (`c4ad4a1`).
- [42768327674: Release checks / entrypoint](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768327674) - failure (`0cc1adc`).
- [42768317765: Naive / entrypoint](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768317765) - success (`0cc1adc`).
- [42768313706: Release checks / missing-data](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768313706) - failure (`0cc1adc`).
- [42768309241: Naive / missing-data](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768309241) - success (`0cc1adc`).
- [42768305053: Release checks / windows](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768305053) - failure (`0cc1adc`).
- [42768301209: Naive / windows](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768301209) - success (`0cc1adc`).
- [42768297080: Release checks / python310](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768297080) - failure (`0cc1adc`).
- [42768291458: Naive / python310](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768291458) - success (`0cc1adc`).
- [42768282579: Release checks / main](https://github.com/MaximushkaBed/soup-devops-release-lab/actions/runs/42768282579) - success (`0cc1adc`).

## Unexpected local failures and corrections

Local actionlint found invalid YAML quoting around :all:. Docker initially failed
because the ignore file excluded the wheel, after a separate sandbox permission
issue writing Buildx state. Those were fixed before the first Actions run.
The first four red runs proved CLI failure but captured its stderr without printing
it. The smoke helper was corrected and all eight comparisons were repeated so the
original ImportError/ModuleNotFoundError/FileNotFoundError is visible. The initial
runs remain linked above; no failures were deleted or changed to green.

Machine-readable metadata is in runs.json; selected links/errors are in proofs.json.
Raw primary-run log archives are in the local .evidence directory and submission ZIP.
Artifacts have a 30-day retention period; exported logs are preserved in the submission archive.
