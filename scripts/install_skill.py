#!/usr/bin/env python3
"""Install the Agent Team skill into a named project, or compare an installed copy.

The skill files are read from this tool's own package root, a reviewed source
checkout or an extracted and verified release, never from an archive. An
installation creates only a new skill directory and never merges into or
replaces an existing one. It grants no permissions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath

try:
    from .package import files_for
    from .version import add_version_flag, package_version
    from .workflows import RecordError
except ImportError:
    from package import files_for
    from version import add_version_flag, package_version
    from workflows import RecordError

ROOT = Path(__file__).resolve().parents[1]
SKILL_SOURCE = 'skill/agent-team-os/'
SKILL_TARGET = ('.agents', 'skills', 'agent-team-os')
MAX_SKILL_FILE_BYTES = 1024 * 1024
GENERIC_ERROR = 'skill could not be installed or compared; name an existing project directory'


def skill_files(root: Path = ROOT) -> list[tuple[str, bytes]]:
    """Return ``(relative path, bytes)`` for every manifest entry under the skill folder."""
    files = []
    for path in files_for(root):
        entry = path.relative_to(root).as_posix()
        if entry.startswith(SKILL_SOURCE):
            data = path.read_bytes()
            if len(data) > MAX_SKILL_FILE_BYTES:
                raise RecordError('a skill file exceeds 1 MiB')
            files.append((entry[len(SKILL_SOURCE):], data))
    if not files:
        raise RecordError('the package manifest lists no skill files')
    return files


def project_root(project: Path) -> Path:
    if not Path(project).is_dir():
        raise RecordError('the project must be an existing directory')
    return Path(project).resolve(strict=True)


def same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _create_file(path: Path, data: bytes, created: list[Path]) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags, 0o644)
    created.append(path)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(descriptor, view):]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rollback(created: list[Path]) -> None:
    """Remove, newest first, only what this run created."""
    for path in reversed(created):
        try:
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink()
        except OSError:
            pass


def install(project: Path, root: Path = ROOT) -> dict:
    """Copy the skill into ``<project>/.agents/skills/agent-team-os``, creating only new entries."""
    base = project_root(project)
    files = skill_files(root)
    version = package_version(root)
    created: list[Path] = []
    try:
        parent = base
        for name in SKILL_TARGET[:-1]:
            parent = parent / name
            try:
                os.mkdir(parent)
                created.append(parent)
            except FileExistsError:
                pass
            if not parent.is_dir():
                raise RecordError('the .agents and .agents/skills paths must be directories')
            # A symlink or junction resolves elsewhere. Refuse it before creating
            # anything below it, so nothing is written outside the named project.
            if not same_path(parent.resolve(strict=True), parent):
                raise RecordError('the .agents/skills directory must not redirect outside the project')
        destination = parent / SKILL_TARGET[-1]
        try:
            os.mkdir(destination)
        except FileExistsError:
            raise RecordError('the skill is already installed; an existing skill is never replaced') from None
        created.append(destination)
        written = []
        for relative, data in files:
            target = destination.joinpath(*PurePosixPath(relative).parts)
            folder = destination
            for name in PurePosixPath(relative).parts[:-1]:
                folder = folder / name
                if not folder.exists():
                    os.mkdir(folder)
                    created.append(folder)
            _create_file(target, data, created)
            written.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    except BaseException:
        _rollback(created)
        raise
    return {'ok': True, 'destination': str(destination), 'package_version': version, 'files': written}


def _installed_entries(destination: Path) -> tuple[dict[str, Path], list[str]]:
    """Walk an installed skill without following links: regular files and other entries."""
    files: dict[str, Path] = {}
    others: list[str] = []
    pending = [(destination, '')]
    while pending:
        folder, prefix = pending.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                relative = prefix + entry.name
                if entry.is_dir(follow_symlinks=False):
                    pending.append((Path(entry.path), relative + '/'))
                elif entry.is_file(follow_symlinks=False):
                    files[relative] = Path(entry.path)
                else:
                    others.append(relative)
    return files, others


def compare(project: Path, root: Path = ROOT) -> dict:
    """Compare an installed skill with this package's skill files. Reads only."""
    base = project_root(project)
    expected = dict(skill_files(root))
    destination = base.joinpath(*SKILL_TARGET)
    report = {'destination': str(destination), 'package_version': package_version(root), 'installed': False,
              'identical': [], 'changed': [], 'missing': [], 'extra': [], 'not_regular': []}
    try:
        mode = os.lstat(destination).st_mode
    except FileNotFoundError:
        mode = None
    if mode is None or not stat.S_ISDIR(mode):
        if mode is not None:
            report['not_regular'].append('.')
        report['ok'] = False
        return report
    report['installed'] = True
    installed, others = _installed_entries(destination)
    for relative in sorted(expected):
        if relative in installed:
            with installed[relative].open('rb') as handle:
                data = handle.read(MAX_SKILL_FILE_BYTES + 1)
            report['identical' if data == expected[relative] else 'changed'].append(relative)
        elif relative in others or any(item.startswith(relative + '/') for item in installed):
            report['not_regular'].append(relative)
        else:
            report['missing'].append(relative)
    report['extra'] = sorted(set(installed) - set(expected))
    report['not_regular'] = sorted(set(report['not_regular']) | (set(others) - set(expected)))
    report['ok'] = not (report['changed'] or report['missing'] or report['extra'] or report['not_regular'])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_version_flag(parser)
    parser.add_argument('--project', type=Path, required=True,
                        help='an existing project directory; the skill goes to .agents/skills/agent-team-os in it')
    parser.add_argument('--compare', action='store_true',
                        help='read only: compare an installed skill with this package and exit 0 only if identical')
    args = parser.parse_args()
    try:
        result = compare(args.project) if args.compare else install(args.project)
    except RecordError as exc:
        print(json.dumps({'ok': False, 'error': GENERIC_ERROR, **exc.details()}))
        return 1
    except (OSError, ValueError, UnicodeError, RuntimeError):
        print(json.dumps({'ok': False, 'error': GENERIC_ERROR}))
        return 1
    ordered = {'ok': result.pop('ok'), **result}
    print(json.dumps(ordered, indent=2))
    return 0 if ordered['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
