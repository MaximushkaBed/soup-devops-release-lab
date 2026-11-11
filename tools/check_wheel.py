"""Check RECORD, the CLI's file contract, and source bytes before installation.

Run in the locked build environment. A consistent RECORD is not proof of safety;
the explicit content contract also rejects unexpected startup hooks and modules.
"""

import argparse
import configparser
from pathlib import Path

from wheel.wheelfile import WheelFile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "soup_release_lab"
PACKAGE_FILES = ("__init__.py", "cli.py", "greeting.txt")
DIST_FILES = (
    "METADATA",
    "WHEEL",
    "entry_points.txt",
    "top_level.txt",
    "RECORD",
    "licenses/LICENSE",
)


def check(wheel: Path) -> None:
    with WheelFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate wheel member")
        # Reading every member makes WheelFile check each RECORD hash.
        contents = {name: archive.read(name) for name in names}
        info = archive.dist_info_path
        expected = {f"{PACKAGE}/{name}" for name in PACKAGE_FILES}
        expected.update(f"{info}/{name}" for name in DIST_FILES)
        if set(names) != expected:
            raise ValueError(
                f"Wheel contents differ: missing={sorted(expected - set(names))}; "
                f"unexpected={sorted(set(names) - expected)}"
            )
        for name in PACKAGE_FILES:
            if contents[f"{PACKAGE}/{name}"] != (ROOT / "src" / PACKAGE / name).read_bytes():
                raise ValueError(f"Wheel/source bytes differ: {name}")
        if contents[f"{info}/licenses/LICENSE"] != (ROOT / "LICENSE").read_bytes():
            raise ValueError("Wheel/source license bytes differ")
        entrypoints = configparser.ConfigParser(interpolation=None)
        entrypoints.optionxform = str
        entrypoints.read_string(contents[f"{info}/entry_points.txt"].decode("utf-8"))
        if entrypoints.sections() != ["console_scripts"] or dict(
            entrypoints["console_scripts"]
        ) != {"soup-release": "soup_release_lab.cli:main"}:
            raise ValueError("Unexpected wheel entry points")
    print(f"PASS: RECORD, content contract and source bytes: {wheel.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheels", type=Path, nargs="+")
    for wheel in parser.parse_args().wheels:
        check(wheel)


if __name__ == "__main__":
    main()
