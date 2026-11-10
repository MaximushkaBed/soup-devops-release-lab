# Reproducible incidents

The corrected source is committed. Each demonstration starts from a fresh checkout and runs
`python tools/inject_bug.py <fault>`. The tool checks its patch preconditions; the workflow prints
the exact diff. This avoids four unrelated stale branches and keeps the comparison on one commit.
The release-on-tag path never runs the injector. Broken artifacts are retained for 30 days.

## 1. `python310`: use an API introduced in Python 3.11

Replace `timezone.utc` with the imported `datetime.UTC`. Source tests and the build pass on Linux
3.12, and wheel metadata still advertises Python >=3.10. The installed CLI raises ImportError on
3.10. Both Ubuntu and Windows 3.10 artifact jobs must fail; newer interpreters should pass.

## 2. `windows`: unconditional Unix-only import

Replace portable `getpass.getuser()` with `pwd.getpwuid(0).pw_name`. Linux source tests pass;
Windows cannot import `pwd`. All five Windows artifact jobs must fail with ModuleNotFoundError.
This is an OS/API problem, independent of the Python-version problem.

## 3. `missing-data`: omit the packaged resource

Remove `greeting.txt` from setuptools package data. Unit tests use `src/` and see the file. The
build and `twine check` pass because metadata validity does not prove runtime completeness.
The installed CLI raises FileNotFoundError. Wheel, rebuilt sdist, and Docker checks must fail.

## 4. `entrypoint`: publish a console script pointing to a missing function

Change the console entry point to `soup_release_lab.cli:missing_main`. Unit tests call `main()`
directly and pass. The installed command fails with ImportError even though importing the
package works. Wheel, rebuilt sdist, and Docker checks must fail.

## Reading results

`docs/evidence.md` records actual run URLs, conclusions and failing job names. Expected failures
remain red. If an unrelated failure occurs, retain it too and explain it; do not count it as proof
that an incident was caught. A fixed green run must cover all ten combinations and Docker.
