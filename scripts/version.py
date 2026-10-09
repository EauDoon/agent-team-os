#!/usr/bin/env python3
"""Print the Agent Team package version from the VERSION file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
INVALID = "VERSION must contain a semantic X.Y.Z version"


def package_version(root: Path = ROOT) -> str:
    """Return the validated package version; the only reader of VERSION.

    The file must hold one strict UTF-8 X.Y.Z line. Anything else, including a
    pre-release suffix or a leading zero, raises ValueError, because the value
    becomes part of archive names and paths.
    """
    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(INVALID) from exc
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(INVALID)
    return version


class _VersionAction(argparse.Action):
    """Report the package version only when asked, then exit.

    VERSION is read lazily, so a damaged file never breaks the tool's normal
    commands, and importing a CLI module reads nothing.
    """

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS,
                 help="show the Agent Team package version and exit"):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        try:
            version = package_version()
        except (OSError, ValueError):
            parser.exit(1, f"agent-team version is unavailable: {INVALID}\n")
        sys.stdout.write(f"agent-team {version}\n")
        sys.stdout.flush()
        parser.exit(0)


def add_version_flag(parser: argparse.ArgumentParser) -> None:
    """Register ``--version`` on a tool's top-level parser."""
    parser.add_argument("--version", action=_VersionAction)


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(package_version())
    except (OSError, ValueError):
        print(INVALID, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
