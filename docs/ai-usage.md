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

## Follow-up AI-assisted checks

Follow-up on 2026-11-11: Codex added a separate HTTPX/Tenacity compatibility fixture, two hashed
dependency profiles, six local comparisons and an eight-combination Actions workflow. Codex also
reproduced an optimization-sensitive false positive, strengthened metadata and registry checks,
and added a logged local preflight. The original applicant checks below were not repeated by the
applicant for this follow-up. One local experiment initially failed for lack of disk space; its
log was retained and POSIX venv creation was corrected to avoid copying large Python binaries.
The installed DevOps skills supplied workflow guidance; their assertions were checked against
code and actual output. Claude Code and subagents were not used.

The next follow-up added an independently written LoRA/SwiGLU fixture, optional ML imports,
two pinned PyTorch/Triton CPU stacks, gradient/update contracts, fault injection and a reusable
release gate. Codex ran CPU and actual Triton-interpreter checks and recorded the exact backend.
Native CUDA and performance were not verified. Local actionlint caught an unquoted `:all:`
command before upload; block scalars fixed YAML parsing. No new applicant-independent check
is claimed for this follow-up.

Research follow-up compared immutable workflow/script snapshots from Soup, pipx, NumPy and PEFT.
Codex research subagents collected primary sources and produced local reports; this does not
establish successful upstream runs or private repository settings. Implementation added an
explicit success-only release gate, wheel RECORD/content/source checks and a separate floating
dependency canary. The unrelated ML fixture now has independent triggers and an opt-in local
preflight. Regression checks cover skipped/cancelled jobs, stale reports, tampered or unexpected
wheel contents, including under optimized Python. All execution and review in this follow-up
remain AI-assisted; no new applicant-independent checks or native GPU results are claimed.

At the applicant's request, Codex moved personal submission materials outside the source tree
and configured GitHub main protection and immutable release-tag rules. Main requires a PR and
the up-to-date `release-ready` check even for admins. Independent approval is disabled while
there is only one maintainer; policy definitions are versioned in `.github/repository-policy/`.

A further AI review supplied by the applicant identified a false source-byte rejection in the
demonstration path. Codex reproduced it and corrected consumer candidate reconstruction and LF
output. The original source-byte guard had been added without repeating all four demonstrations;
the new regression and repeated Actions runs are separate from the original submission evidence.

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
