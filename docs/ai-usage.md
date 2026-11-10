# AI usage and verification

Codex assisted with interpreting the brief, designing the CLI and incident patches, writing the
workflows, drafting documentation, checking official documentation and executing commands.
Claude Code was not used. AI-generated code and prose were reviewed and changed during this work;
AI-generated claims are not treated as evidence without tool output.

## Recorded tool checks

Actual commands, Actions links, outputs and corrections are recorded in evidence.md and Git
history. Local checks executed by Codex are **AI-assisted checks**, not checks independently
performed by the applicant. GPU execution and reviewer access must not be claimed without evidence.

## Corrections made during AI-assisted review

The local actionlint check rejected an unquoted YAML command containing `:all:`; it was changed
to a block scalar. The first Docker build failed because `.dockerignore` excluded the wheel;
the context now explicitly allows only the Dockerfile and candidate wheel. Security-critical
manifest checks originally used Python assertions; these were replaced with explicit exceptions
so `python -O` cannot disable them. Review also found that Python 3.10's ensurepip can leave
setuptools in a runtime venv; the smoke environments now remove pip/setuptools/wheel and assert
that the candidate is the only installed distribution. These are documented AI-assisted fixes,
not evidence of independent applicant review.

## Applicant's independent checks (complete before submission)

This section deliberately makes no claim that the applicant has run checks yet. The applicant
should run the README commands, open each linked red and green run, inspect one failing log for each
incident, and explain why the failure is the intended one. They should register the TestPyPI
publisher, verify the published installation themselves, and read the two-page verdict and costs.
Replace this paragraph with an honest account of what was personally checked, changed or redone.
Do not present this checklist or AI-executed commands as completed personal verification.
