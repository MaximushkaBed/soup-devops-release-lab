"""Require explicit successful results, including after failed or skipped jobs."""

import argparse
import json
import os


def require_success(needs: dict, required: list[str]) -> None:
    if not required or len(required) != len(set(required)):
        raise ValueError("Expected a nonempty, unique list of required jobs")
    if not isinstance(needs, dict) or set(needs) != set(required):
        raise ValueError(f"Job inventory differs; expected {required}, got {needs}")
    failed = {
        name: job.get("result") if isinstance(job, dict) else None
        for name, job in needs.items()
        if not isinstance(job, dict) or job.get("result") != "success"
    }
    if failed:
        raise ValueError(f"Required jobs did not succeed: {failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("required", nargs="+")
    args = parser.parse_args()
    require_success(json.loads(os.environ["NEEDS_JSON"]), args.required)
    print("PASS: every required job succeeded: " + ", ".join(args.required))


if __name__ == "__main__":
    main()
