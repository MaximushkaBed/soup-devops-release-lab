"""Registry delays may be retried; identity or integrity failures must stop immediately."""

import copy
import io
import json
import urllib.error

import pytest

from tools import verify_index

MANIFEST = {"version": "0.9.3", "sha256": {"candidate.whl": "a" * 64, "candidate.tar.gz": "b" * 64}}


def metadata():
    return {
        "info": {"name": verify_index.PROJECT, "version": "0.9.3"},
        "urls": [
            {
                "filename": name,
                "digests": {"sha256": digest},
                "url": f"https://test-files.pythonhosted.org/packages/{name}",
                "yanked": False,
            }
            for name, digest in MANIFEST["sha256"].items()
        ],
    }


def responses(monkeypatch, outcomes):
    calls = []
    sleeps = []

    def fetch(url, timeout):
        calls.append(url)
        result = outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return io.BytesIO(json.dumps(result).encode())

    monkeypatch.setattr(verify_index.urllib.request, "urlopen", fetch)
    monkeypatch.setattr(verify_index.time, "sleep", sleeps.append)
    return calls, sleeps


def test_complete_index_is_accepted():
    assert set(verify_index.published_files(metadata(), MANIFEST)) == set(MANIFEST["sha256"])


def test_partial_upload_is_retried(monkeypatch):
    partial = metadata()
    partial["urls"].pop()
    calls, sleeps = responses(monkeypatch, [partial, metadata()])
    assert len(verify_index.wait_for_index(MANIFEST)) == 2
    assert len(calls) == 2 and sleeps == [5]


@pytest.mark.parametrize("status", [404, 429, 500, 502, 503, 504])
def test_transient_registry_status_is_retried(monkeypatch, status):
    error = urllib.error.HTTPError("https://test.pypi.org/", status, "temporary", {}, None)
    calls, sleeps = responses(monkeypatch, [error, metadata()])
    verify_index.wait_for_index(MANIFEST)
    assert len(calls) == 2 and sleeps == [5]


def test_index_wait_has_a_hard_attempt_limit(monkeypatch):
    partial = metadata()
    partial["urls"] = []
    calls, sleeps = responses(monkeypatch, [partial, partial])
    with pytest.raises(verify_index.IndexNotReady):
        verify_index.wait_for_index(MANIFEST, attempts=2)
    assert len(calls) == 2 and sleeps == [5]


@pytest.mark.parametrize("fault", ["identity", "digest", "origin", "yanked", "duplicate", "extra"])
def test_corrupt_index_is_never_retried_or_accepted(monkeypatch, fault):
    bad = metadata()
    if fault == "identity":
        bad["info"]["version"] = "999.0.0"
    elif fault == "digest":
        bad["urls"][0]["digests"]["sha256"] = "c" * 64
    elif fault == "origin":
        bad["urls"][0]["url"] = "http://other.example/candidate.whl"
    elif fault == "yanked":
        bad["urls"][0]["yanked"] = True
    elif fault == "duplicate":
        bad["urls"].append(copy.deepcopy(bad["urls"][0]))
    else:
        extra = copy.deepcopy(bad["urls"][0])
        extra["filename"] = "unexpected.whl"
        bad["urls"].append(extra)
    calls, sleeps = responses(monkeypatch, [bad, metadata()])
    with pytest.raises(ValueError):
        verify_index.wait_for_index(MANIFEST)
    assert len(calls) == 1 and not sleeps
