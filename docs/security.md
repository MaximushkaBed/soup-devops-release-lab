# Supply-chain safeguards and remaining risks

## Implemented

1. **Unpinned or substituted tools.** The CLI has no runtime dependencies; artifact metadata rejects
   unexpected `Requires-Dist`. Build and CI tools, including transitive dependencies, use exact
   versions and SHA-256 hashes with `--require-hashes --only-binary=:all:`. Build isolation is
   deliberately disabled after provisioning the locked build environment. Actions use full commit
   SHAs and the Docker base uses a digest. Dependency identities and updates still require review:
   a hash can pin malware as accurately as a legitimate wheel. Never mix TestPyPI and PyPI via
   `--extra-index-url` for this project.
2. **Resolver/cache masking.** No CI package or environment cache is restored. Builders install
   locked tools; wheel runtimes install only the artifact, offline, into new venvs. Sdist building
   happens in another venv so its build dependencies cannot hide missing runtime dependencies.
   Tests execute outside the checkout with Python `-I` and no PYTHONPATH. The lock can still be
   wrong; fresh resolution makes that failure visible rather than falling back to cached state.
3. **Stale or altered artifacts.** One build creates wheel and sdist together. An immutable upload
   is named with commit, run ID and attempt. Its manifest binds both file hashes, version and run
   identity. Every matrix job and the publisher verify it. Publication downloads this same upload,
   never a latest-by-name artifact or a new build. Docker installs that wheel. Negative integration
   checks alter a wheel, substitute a commit and mismatch a tag; each must be rejected.
4. **Fork PR credential exposure.** Use `pull_request`, never `pull_request_target` or a privileged
   `workflow_run` handoff. Default token permissions are contents:read; checkout does not persist
   credentials. There are no PyPI API tokens. Only the tag-only publish job gets id-token:write,
   in the tag-restricted `testpypi` environment. Never run fork code on privileged GPU runners.
5. **Version/tag divergence.** Both distribution metadata versions must agree and an upload tag
   must equal `v<version>` exactly. A tag must point into main's history. Installed CLI version and
   package metadata are checked together. TestPyPI bytes are checked again after publication.

## What green does not prove

This is one tiny CLI with a few smoke assertions. It does not prove application correctness,
absence of malicious code, absence of vulnerabilities in pinned tools, reproducible builds,
or availability of TestPyPI. macOS, ARM, PyPy, future Python versions, restricted permissions,
locales, proxy configurations and conflicting user environments are outside the advertised matrix.
GitHub runners, setup-python interpreter patch versions, registry availability, the publisher's
own transitive tooling and maintainer accounts remain trusted. A compromised maintainer could
change the workflow and push a tag; tag reachability alone is not a code-review policy. Configure
protected main/tags and required review before any real PyPI use. OIDC removes stored upload keys;
it does not make arbitrary repository code trustworthy. Attestations establish origin, not safety.

The JSON/hash check after upload can detect an incident only **after** users can fetch that release.
A green check cannot guarantee rollback. Contrary to the scenario's shorthand, PyPI supports yanking
and deletion, but neither reliably recalls installed or mirrored files; do not depend on deletion.
Yank the bad release, notify users, and publish a new version rather than overwriting 0.9.3.

## First ten minutes of an incident

Cancel queued releases and stop new publishing; disable the Trusted Publisher if needed. Revoke
and rotate any exposed credentials, preserving run IDs and redacted evidence. Determine whether an
OIDC exchange or upload occurred. Yank the affected version, communicate the impact, audit changes
and dependency hashes, then issue a reviewed version bump. Purging logs is not credential rotation.

Sources: [GitHub secure use](https://docs.github.com/en/actions/reference/security/secure-use),
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
[PyPI yanking](https://docs.pypi.org/project-management/yanking/).
