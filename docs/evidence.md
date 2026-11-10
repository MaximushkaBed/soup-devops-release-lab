# Evidence ledger

Repository: https://github.com/MaximushkaBed/soup-devops-release-lab (private).
Actions links require repository access; invite reviewers before submission or include exported logs.
No failed run is deleted, hidden, or changed to success. Results below will be populated from actual runs.

## Local checks

Completed on local Linux / CPython 3.13.9:

- Ruff lint and formatting; three pytest unit tests; actionlint v1.7.12; `git diff --check`.
- Wheel and sdist build; strict twine metadata check.
- Fresh wheel installation and independent sdist rebuild followed by fresh installation.
  Bootstrap packages were removed before installed CLI tests; source paths were excluded.
- Negative integration checks rejected a modified wheel, a substituted commit and tag mismatch.
- Docker image built from a digest-pinned base; CLI succeeded as UID 65532 with no network,
  read-only root filesystem, no capabilities and no-new-privileges.

These checks were executed by Codex, not independently by the applicant.

## Actions runs

Pending.

## TestPyPI publication

Pending account-side Trusted Publisher registration. No successful upload is claimed yet.

## Unexpected failures and corrections

Local preflight found and corrected an invalid YAML plain scalar (`:all:`) and a Docker
ignore rule that excluded the candidate wheel. The Docker build also initially needed sandbox
permission to write Buildx state in `~/.docker`; this was an environment restriction, not a
package defect. See ai-usage.md and the corrective commit. No Actions failure has been removed.
