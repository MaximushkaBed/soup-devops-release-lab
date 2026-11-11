# HTTP dependency fixture

This is a separate installable test package; it is never published to an index.
It exercises HTTPX and Tenacity with deterministic HTTP responses, bounded retries,
non-retriable errors and response validation. No real endpoint is contacted.

`soup-http-probe --self-test` tests recovery after HTTP 503, the three-attempt limit,
no retry on HTTP 404, and rejection of an invalid response body.

Two hash-locked profiles intentionally cover the historical HTTPX 0.27.2 API and
HTTPX 0.28.1, with Tenacity 8.5.0 and 9.1.2. These are fixed compatibility targets,
not a claim to test every published version or to select the latest dependencies.

The `removed-api` patch uses HTTPX's removed `proxies` argument. The
`undeclared-runtime` patch omits Tenacity from wheel metadata. An old development
environment hides both failures; clean declared-dependency installs expose them.
