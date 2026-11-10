"""CLI with observable behavior exercised after installation."""

import argparse
import getpass
import json
from datetime import datetime, timezone
from importlib.resources import files

from soup_release_lab import __version__


def report(name: str) -> dict[str, str]:
    template = files("soup_release_lab").joinpath("greeting.txt").read_text(encoding="utf-8")
    return {
        "greeting": template.strip().format(name=name),
        "user": getpass.getuser(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Say hello from an installed Python artifact.")
    parser.add_argument("--name", default="world")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    result = report(args.name)
    print(json.dumps(result, ensure_ascii=False) if args.json else result["greeting"])
