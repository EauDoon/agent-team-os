#!/usr/bin/env python3
"""Build a deterministic installable ZIP and SHA-256 checksum."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def files_for(root: Path) -> list[Path]:
    manifest_path = root / "package-manifest.json"
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries or any(not isinstance(item, str) for item in entries):
        raise ValueError("package-manifest.json must be a non-empty string array")
    if len(entries) != len(set(entries)):
        raise ValueError("package-manifest.json contains duplicate entries")
    result: list[Path] = []
    for entry in sorted(entries):
        relative = PurePosixPath(entry)
        if relative.is_absolute() or entry != relative.as_posix() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError(f"unsafe package manifest entry: {entry!r}")
        try:
            path = root.joinpath(*relative.parts)
            safe = path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve())
        except (OSError, RuntimeError, UnicodeError, ValueError):
            safe = False
        if not safe:
            raise ValueError(f"missing or unsafe package file: {entry!r}")
        result.append(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    archive = output_dir / f"agent-team-{version}.zip"
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    if archive.exists():
        archive.unlink()
    if checksum.exists():
        checksum.unlink()
    prefix = f"agent-team-{version}"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as handle:
        for path in files_for(root):
            relative = path.relative_to(root).as_posix()
            info = ZipInfo(f"{prefix}/{relative}")
            info.date_time = (2020, 1, 1, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            handle.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    print(archive)
    print(checksum)
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
