# AI usage and verification

Codex assisted with interpreting the brief, designing the CLI and incident patches, writing the
workflows, drafting documentation, checking official documentation and executing commands.
Accepted suggestions included the src layout, separate source/artifact checks, the cross-platform
matrix and OIDC publishing. Claude Code was not used. AI-generated code and prose were reviewed and changed during this work;
AI-generated claims are not treated as evidence without tool output.

## Recorded tool checks

Actual commands, Actions links, outputs and corrections are recorded in evidence.md and Git
history. Local checks executed by Codex are **AI-assisted checks**, not checks independently
performed by the applicant. No GPU execution or reviewer access is claimed.

## Corrections made during AI-assisted review

The local actionlint check rejected an unquoted YAML command containing `:all:`; it was changed
to a block scalar. The first Docker build failed because `.dockerignore` excluded the wheel;
the context now explicitly allows only the Dockerfile and candidate wheel. Security-critical
manifest checks originally used Python assertions; these were replaced with explicit exceptions
so `python -O` cannot disable them. Review also found that Python 3.10's ensurepip can leave
setuptools in a runtime venv; the smoke environments now remove pip/setuptools/wheel and assert
that the candidate is the only installed distribution. These are documented AI-assisted fixes,
separate from the applicant checks below.

## Applicant's independent checks

The applicant personally configured the Pending Trusted Publisher on TestPyPI with the repository,
workflow and environment names, without providing an API token to Codex.

On 2026-11-10 the applicant ran these commands in their own terminal:

```sh
python3 -m venv /tmp/soup-manual-check
/tmp/soup-manual-check/bin/python -m pip install --index-url https://test.pypi.org/simple/ --no-deps soup-release-lab-maximushkabed==0.9.3
/tmp/soup-manual-check/bin/soup-release --name Soup --json
```

They pasted the actual output into the conversation: the wheel was downloaded from
`test-files.pythonhosted.org`, installation succeeded, and the installed console command returned:

```json
{"greeting": "Hello, Soup!", "user": "maksim", "timestamp": "2026-11-10T06:36:03.788713+00:00", "version": "0.9.3"}
```

This is independent verification of the TestPyPI installation and basic Linux CLI behavior.
Windows, the broader version matrix, negative tests and hash verification were automated checks
executed through Codex and GitHub Actions. No independent manual review of all Actions logs is claimed.
