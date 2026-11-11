"""A Windows-style Git checkout must preserve the lock bytes bound into the bundle."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dependency_lock_hashes_survive_autocrlf_checkout(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    git = ["git", "-C", str(repository), "-c", "core.autocrlf=true", "-c", "core.safecrlf=false"]
    subprocess.run([*git, "init", "--quiet"], check=True, capture_output=True)
    shutil.copy2(ROOT / ".gitattributes", repository / ".gitattributes")
    (repository / "requirements").mkdir()
    for profile in ("minimum", "current"):
        name = f"requirements/compat-{profile}.txt"
        shutil.copy2(ROOT / name, repository / name)
    subprocess.run([*git, "add", ".gitattributes", "requirements"], check=True, capture_output=True)
    checkout = tmp_path / "windows-checkout"
    subprocess.run(
        [*git, "checkout-index", "--all", f"--prefix={checkout.as_posix()}/"],
        check=True,
        capture_output=True,
    )
    for profile in ("minimum", "current"):
        name = f"requirements/compat-{profile}.txt"
        assert (checkout / name).read_bytes() == (ROOT / name).read_bytes(), (
            f"Git changed {name} to CRLF; Linux and Windows will disagree on the profile hash"
        )
