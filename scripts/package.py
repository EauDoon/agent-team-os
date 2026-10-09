#!/usr/bin/env python3
"""Build a deterministic installable ZIP and SHA-256 checksum.

Members are stored uncompressed, so the archive bytes depend only on the
manifest, the source bytes and this builder, never on the interpreter's zlib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from shutil import copyfile, rmtree
from tempfile import mkdtemp
from zipfile import ZIP_STORED, ZipFile, ZipInfo

try:
    from .version import add_version_flag, package_version
except ImportError:
    from version import add_version_flag, package_version


class IncompleteRollbackError(RuntimeError):
    """Recovery copies must survive when automatic restoration fails."""


def version_for(root: Path) -> str:
    return package_version(root)


def files_for(root: Path) -> list[Path]:
    manifest_path = root / "package-manifest.json"
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries or any(not isinstance(item, str) for item in entries):
        raise ValueError("package-manifest.json must be a non-empty string array")
    if len(entries) != len(set(entries)):
        raise ValueError("package-manifest.json contains duplicate entries")
    result: list[Path] = []
    for entry in sorted(entries):
        try:
            entry.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError(f"unsafe package manifest entry: {entry!r}") from exc
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


def promote_pair(
    staged_archive: Path,
    staged_checksum: Path,
    archive: Path,
    checksum: Path,
) -> None:
    rollback_dir = staged_archive.parent / "rollback"
    rollback_dir.mkdir()
    snapshots: list[tuple[Path, bool, Path]] = []
    for target in (archive, checksum):
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f"release target is not a regular file: {target}")
        existed = target.is_file()
        backup = rollback_dir / target.name
        if existed:
            copyfile(target, backup)
        snapshots.append((target, existed, backup))

    promoted = 0
    try:
        for staged, target in (
            (staged_archive, archive),
            (staged_checksum, checksum),
        ):
            staged.replace(target)
            promoted += 1
    except OSError as promotion_error:
        rollback_errors: list[str] = []
        for target, existed, backup in reversed(snapshots[:promoted]):
            try:
                if existed:
                    backup.replace(target)
                else:
                    target.unlink(missing_ok=True)
            except OSError as rollback_error:
                rollback_errors.append(f"{target.name}: {rollback_error}")
        if rollback_errors:
            detail = "; ".join(rollback_errors)
            raise IncompleteRollbackError(
                f"release promotion failed and rollback was incomplete: {detail}; "
                f"recovery copies retained at {rollback_dir}"
            ) from promotion_error
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_version_flag(parser)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    root = Path(__file__).resolve().parents[1]
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    version = version_for(root)
    archive = output_dir / f"agent-team-{version}.zip"
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    files = files_for(root)
    prefix = f"agent-team-{version}"
    staging = Path(mkdtemp(dir=output_dir, prefix=".agent-team-package-"))
    preserve_recovery = False
    try:
        staged_archive = Path(staging) / archive.name
        staged_checksum = Path(staging) / checksum.name
        # Deflate output differs between zlib and zlib-ng (CPython 3.14 builds),
        # which made the release digest depend on the interpreter. Stored
        # members keep the checksum reproducible from source on any Python.
        with ZipFile(staged_archive, "w", compression=ZIP_STORED) as handle:
            for path in files:
                relative = path.relative_to(root).as_posix()
                info = ZipInfo(f"{prefix}/{relative}")
                info.date_time = (2020, 1, 1, 0, 0, 0)
                info.compress_type = ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                handle.writestr(info, path.read_bytes())
        digest = hashlib.sha256(staged_archive.read_bytes()).hexdigest()
        staged_checksum.write_bytes(f"{digest}  {archive.name}\n".encode("ascii"))
        promote_pair(staged_archive, staged_checksum, archive, checksum)
    except IncompleteRollbackError:
        preserve_recovery = True
        raise
    finally:
        if not preserve_recovery:
            rmtree(staging)
    print(archive)
    print(checksum)
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
