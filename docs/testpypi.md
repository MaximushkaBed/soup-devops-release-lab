# TestPyPI setup and release

Create a separate account at https://test.pypi.org/ and register a **pending publisher**:
https://test.pypi.org/manage/account/publishing/ . No API token is needed.

- Project: `soup-release-lab-maximushkabed`
- GitHub owner: `MaximushkaBed`
- Repository: `soup-devops-release-lab`
- Workflow filename: `release.yml`
- GitHub environment: `testpypi`

The repository environment permits only tags matching `v*`. There are no long-lived publishing
credentials. PRs receive read-only repository permissions and never enter the publisher environment.
The workflow file and tag writers remain part of the trust boundary; see security.md.

After registration and a green fixed run:

```sh
git tag v0.9.3
git push origin v0.9.3
```

The tag must point to a commit reachable from `main`. A tag/version mismatch fails before upload.
The publish job verifies the same run-scoped, checksummed bundle used by the OS matrix and Docker,
then uploads to TestPyPI using OIDC. The final job fetches the index metadata, checks both published
file hashes, and installs the pinned wheel from TestPyPI in a clean environment.

A post-publish failure is still a failed release and remains visible. Do not reuse an uploaded
version or hide partial uploads with `skip-existing`. Investigate, then increment package and CLI
versions together and publish a new tag. TestPyPI is a test service and can be unavailable or reset.
