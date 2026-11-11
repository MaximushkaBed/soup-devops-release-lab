"""Keep floating dependency resolution isolated and evidence outputs fresh."""

import pytest

from tools.dependency_lab import clean_env
from tools.dependency_lab import test as probe_dependencies


def test_user_indexes_caches_and_pythonpath_do_not_enter_the_probe(monkeypatch):
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", "https://unexpected.invalid/simple")
    monkeypatch.setenv("PIP_CONSTRAINT", "/unexpected/constraints.txt")
    monkeypatch.setenv("PYTHONPATH", "/unexpected/source")
    env = clean_env()
    assert "PIP_EXTRA_INDEX_URL" not in env
    assert "PIP_CONSTRAINT" not in env
    assert "PYTHONPATH" not in env
    assert env["PIP_NO_CACHE_DIR"] == "1"


def test_fresh_probe_rejects_a_prepopulated_runtime_before_doing_work(tmp_path):
    with pytest.raises(ValueError, match="require the clean installed-artifact test"):
        probe_dependencies(tmp_path / "missing-bundle", "fresh", True)


@pytest.mark.parametrize("symlink", [False, True])
def test_existing_canary_evidence_cannot_be_overwritten(tmp_path, symlink):
    report = tmp_path / "old.json"
    if symlink:
        try:
            report.symlink_to(tmp_path / "missing.json")
        except OSError:
            pytest.skip("Creating symlinks requires privileges on this Windows host")
    else:
        report.write_text('{"status": "passed"}')
    with pytest.raises(ValueError, match="refusing stale output"):
        probe_dependencies(tmp_path / "missing-bundle", "fresh", False, report)
    if not symlink:
        assert report.read_text() == '{"status": "passed"}'
