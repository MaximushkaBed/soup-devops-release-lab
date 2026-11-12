"""Apply one documented incident; only the demonstration dispatch uses this."""

import argparse
from pathlib import Path

FAULTS = ("fixed", "python310", "windows", "missing-data", "entrypoint")


def replace(path: str, before: str, after: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(before) != 1:
        raise SystemExit(f"Expected exactly one replacement in {path}: {before!r}")
    # Build and consumer jobs must produce identical candidate bytes on Windows too.
    with target.open("w", encoding="utf-8", newline="\n") as output:
        output.write(text.replace(before, after))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fault", choices=FAULTS)
    fault = parser.parse_args().fault
    if fault == "python310":
        replace(
            "src/soup_release_lab/cli.py",
            "from datetime import datetime, timezone",
            "from datetime import UTC, datetime",
        )
        replace("src/soup_release_lab/cli.py", "datetime.now(timezone.utc)", "datetime.now(UTC)")
    elif fault == "windows":
        replace(
            "src/soup_release_lab/cli.py", "import getpass\nimport json", "import json\nimport pwd"
        )
        replace("src/soup_release_lab/cli.py", "getpass.getuser()", "pwd.getpwuid(0).pw_name")
    elif fault == "missing-data":
        replace("pyproject.toml", 'soup_release_lab = ["greeting.txt"]', "soup_release_lab = []")
    elif fault == "entrypoint":
        replace("pyproject.toml", "soup_release_lab.cli:main", "soup_release_lab.cli:missing_main")
    print(f"Incident: {fault}")


if __name__ == "__main__":
    main()
