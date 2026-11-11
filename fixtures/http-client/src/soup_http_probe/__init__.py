"""Fetch release information with bounded retries and explicit response validation."""

import argparse
import importlib.metadata
import json

import httpx
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_none


def transient(error: BaseException) -> bool:
    return isinstance(error, httpx.TransportError) or (
        isinstance(error, httpx.HTTPStatusError)
        and error.response.status_code in (429, 502, 503, 504)
    )


def fetch_release(transport: httpx.BaseTransport, url: str = "https://release.invalid/current"):
    attempts = 0
    with httpx.Client(timeout=5.0, trust_env=False, transport=transport) as client:
        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_none(),
            retry=retry_if_exception(transient),
            reraise=True,
        ):
            with attempt:
                attempts += 1
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("version"), str):
                    raise ValueError("Release response must contain a string version")
                if not isinstance(data.get("files"), list) or not data["files"]:
                    raise ValueError("Release response must contain nonempty files")
                return {**data, "attempts": attempts}
    raise RuntimeError("Retry policy returned without a response")


def self_test() -> dict:
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"version": "0.1.0", "files": ["candidate.whl"]})

    result = fetch_release(httpx.MockTransport(handler))
    if result != {"version": "0.1.0", "files": ["candidate.whl"], "attempts": 2}:
        raise ValueError(f"Unexpected successful retry result: {result}")

    for status, expected_calls in ((404, 1), (503, 3)):
        failed_calls = []

        def failure(request, calls=failed_calls, status_code=status):
            calls.append(request)
            return httpx.Response(status_code)

        try:
            fetch_release(httpx.MockTransport(failure))
        except httpx.HTTPStatusError:
            pass
        else:
            raise ValueError(f"HTTP {status} was silently accepted")
        if len(failed_calls) != expected_calls:
            raise ValueError(
                f"HTTP {status}: expected {expected_calls} attempts, got {len(failed_calls)}"
            )

    invalid_calls = []

    def invalid(request):
        invalid_calls.append(request)
        return httpx.Response(200, json={"version": 1, "files": []})

    try:
        fetch_release(httpx.MockTransport(invalid))
    except ValueError as error:
        if "string version" not in str(error) or len(invalid_calls) != 1:
            raise ValueError("Invalid response must fail without retries") from error
    else:
        raise ValueError("Invalid release response was silently accepted")
    return {
        "status": "passed",
        "httpx": httpx.__version__,
        "httpcore": importlib.metadata.version("httpcore"),
        "tenacity": importlib.metadata.version("tenacity"),
        "checks": ["503 recovery", "404 no retry", "retry limit", "response schema"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test",
        action="store_true",
        required=True,
        help="Run deterministic HTTP scenarios without network requests",
    )
    parser.parse_args()
    print(json.dumps(self_test()))
