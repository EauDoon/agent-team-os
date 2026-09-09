#!/usr/bin/env python3
"""Compare a ZIP with the current reviewed source tree without extracting it."""

import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile
import zlib

try:
    from .package import files_for, version_for
except ImportError:
    from package import files_for, version_for

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024


def verify(archive: Path, root: Path, expected_sha256: str | None = None) -> dict:
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('archive exceeds 32 MiB')
    with archive.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if expected_sha256 is not None:
        if not re.fullmatch('[0-9a-fA-F]{64}', expected_sha256):
            raise ValueError('expected SHA-256 must be 64 hexadecimal characters')
        if digest != expected_sha256.lower():
            raise ValueError('archive SHA-256 does not match expected digest')
    prefix = f'agent-team-{version_for(root)}/'
    expected = {prefix + path.relative_to(root).as_posix(): path for path in files_for(root)}
    with ZipFile(archive) as handle:
        entries = handle.infolist()
        names = [info.filename for info in entries]
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('archive entries differ from the source manifest')
        for info in entries:
            path = expected[info.filename]
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 != 0o100000:
                raise ValueError('archive entry is not a regular file')
            if info.flag_bits & 1 or info.file_size != path.stat().st_size:
                raise ValueError('archive entry encryption or size differs from source')
            # Bound decompression to the exact source size, even with dishonest metadata.
            with handle.open(info) as member, path.open('rb') as source:
                remaining = info.file_size
                while remaining:
                    size = min(65536, remaining)
                    data = member.read(size)
                    if not data or data != source.read(size):
                        raise ValueError('archive content differs from source')
                    remaining -= len(data)
                if member.read(1) or source.read(1):
                    raise ValueError('archive content length differs from source')
    return {'ok': True, 'sha256': digest, 'files': len(expected), 'source_version': version_for(root)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--sha256', help='digest obtained through a trusted channel')
    args = parser.parse_args()
    try:
        result = verify(args.archive, Path(__file__).resolve().parents[1], args.sha256)
    # RuntimeError includes unsupported-method NotImplementedError; malformed
    # compressed streams can raise zlib.error directly while reading a member.
    except (OSError, ValueError, BadZipFile, RuntimeError, EOFError, zlib.error):
        print(json.dumps({'ok': False, 'error': 'archive could not be verified against the current source tree'}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
