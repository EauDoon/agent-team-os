import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.install_skill import compare, install, skill_files
from scripts.version import package_version
from scripts.workflows import RecordError

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skill/agent-team-os'


def link_directory(link: Path, target: Path) -> bool:
    """Point ``link`` at ``target`` with a symlink, or a junction on Windows without symlink rights."""
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    if sys.platform != 'win32':
        return False
    made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)],
                          capture_output=True, text=True, timeout=30)
    return made.returncode == 0 and link.exists()


def directory_links_supported() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        return link_directory(Path(directory) / 'link', Path(directory))


def tree(path: Path) -> list[str]:
    return sorted(item.relative_to(path).as_posix() for item in path.rglob('*'))


class InstallSkillTests(unittest.TestCase):
    def test_install_copies_exactly_the_skill_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = install(project)
            destination = project / '.agents/skills/agent-team-os'
            self.assertEqual(Path(result['destination']), destination.resolve())
            self.assertEqual(result['package_version'], package_version())
            self.assertEqual([item['path'] for item in result['files']], ['SKILL.md', 'agents/openai.yaml'])
            for item in result['files']:
                source = (SKILL / item['path']).read_bytes()
                self.assertEqual((destination / item['path']).read_bytes(), source)
                self.assertEqual(item['bytes'], len(source))
            self.assertEqual(tree(project), ['.agents', '.agents/skills', '.agents/skills/agent-team-os',
                                             '.agents/skills/agent-team-os/SKILL.md',
                                             '.agents/skills/agent-team-os/agents',
                                             '.agents/skills/agent-team-os/agents/openai.yaml'])

    def test_existing_skill_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            destination = project / '.agents/skills/agent-team-os'
            destination.mkdir(parents=True)
            (destination / 'SKILL.md').write_bytes(b'local edits')
            with self.assertRaises(RecordError) as raised:
                install(project)
            self.assertIn('never replaced', raised.exception.reason)
            self.assertEqual(tree(destination), ['SKILL.md'])
            self.assertEqual((destination / 'SKILL.md').read_bytes(), b'local edits')

    def test_missing_project_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            for project in (Path(directory) / 'absent', Path(__file__)):
                with self.assertRaises(RecordError) as raised:
                    install(project)
                self.assertEqual(raised.exception.reason, 'the project must be an existing directory')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_a_file_in_place_of_the_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / '.agents').write_bytes(b'not a directory')
            with self.assertRaises(RecordError):
                install(project)
            self.assertEqual((project / '.agents').read_bytes(), b'not a directory')

    @unittest.skipUnless(directory_links_supported(), 'directory links are unavailable')
    def test_redirected_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / 'outside'
            outside.mkdir()
            for linked in ('.agents', '.agents/skills'):
                with self.subTest(linked=linked):
                    project = Path(directory) / linked.replace('/', '-').strip('.')
                    project.mkdir()
                    if linked == '.agents/skills':
                        (project / '.agents').mkdir()
                    self.assertTrue(link_directory(project / linked, outside))
                    with self.assertRaises(RecordError) as raised:
                        install(project)
                    self.assertIn('must not redirect', raised.exception.reason)
                    self.assertEqual(list(outside.iterdir()), [])

    def test_write_failure_removes_only_what_the_run_created(self):
        with tempfile.TemporaryDirectory() as directory:
            fresh = Path(directory) / 'fresh'
            fresh.mkdir()
            with patch('scripts.install_skill.os.fsync', side_effect=[None, OSError('disk full')]):
                with self.assertRaises(OSError):
                    install(fresh)
            self.assertEqual(list(fresh.iterdir()), [])
            kept = Path(directory) / 'kept'
            (kept / '.agents/skills/other-skill').mkdir(parents=True)
            (kept / '.agents/skills/other-skill/SKILL.md').write_bytes(b'other')
            with patch('scripts.install_skill.os.fsync', side_effect=[None, OSError('disk full')]):
                with self.assertRaises(OSError):
                    install(kept)
            self.assertEqual(tree(kept), ['.agents', '.agents/skills', '.agents/skills/other-skill',
                                          '.agents/skills/other-skill/SKILL.md'])

    def test_compare_reports_each_difference_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            absent = compare(project)
            self.assertEqual((absent['ok'], absent['installed']), (False, False))
            self.assertEqual(list(project.iterdir()), [])
            install(project)
            destination = project / '.agents/skills/agent-team-os'
            same = compare(project)
            self.assertTrue(same['ok'])
            self.assertEqual(same['identical'], ['SKILL.md', 'agents/openai.yaml'])
            (destination / 'SKILL.md').write_bytes(b'edited')
            (destination / 'agents/openai.yaml').unlink()
            (destination / 'notes.txt').write_bytes(b'local')
            before = tree(project)
            report = compare(project)
            self.assertFalse(report['ok'])
            self.assertEqual((report['changed'], report['missing'], report['extra'], report['identical']),
                             (['SKILL.md'], ['agents/openai.yaml'], ['notes.txt'], []))
            self.assertEqual(tree(project), before)
            (destination / 'agents').rmdir()
            (destination / 'agents').write_bytes(b'')
            self.assertEqual(compare(project)['missing'], ['agents/openai.yaml'])

    def test_cli_exit_codes_in_script_and_module_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, entry in enumerate((['scripts/install_skill.py'], ['-m', 'scripts.install_skill'])):
                project = Path(directory) / f'project-{index}'
                project.mkdir()
                for args, code in ((['--compare'], 1), ([], 0), (['--compare'], 0), ([], 1)):
                    result = subprocess.run([sys.executable, *entry, '--project', str(project), *args], cwd=ROOT,
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    self.assertEqual(json.loads(result.stdout)['ok'], code == 0)
                    self.assertEqual(result.stderr, '')
            missing = str(Path(directory) / 'absent-project-dir')
            result = subprocess.run([sys.executable, 'scripts/install_skill.py', '--project', missing],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(json.loads(result.stdout)['reason'], 'the project must be an existing directory')
            self.assertNotIn('absent-project-dir', result.stdout)

    def test_installer_runs_from_an_extracted_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            built = subprocess.run([sys.executable, 'scripts/package.py', '--output', str(root / 'dist')], cwd=ROOT,
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            archive = root / 'dist' / f'agent-team-{package_version()}.zip'
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(root / 'expanded')
            extracted = root / 'expanded' / f'agent-team-{package_version()}'
            project = root / 'project'
            project.mkdir()
            result = subprocess.run([sys.executable, str(extracted / 'scripts/install_skill.py'),
                                     '--project', str(project)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual([path for path, _ in skill_files(extracted)], ['SKILL.md', 'agents/openai.yaml'])
            for relative in ('SKILL.md', 'agents/openai.yaml'):
                self.assertEqual((project / '.agents/skills/agent-team-os' / relative).read_bytes(),
                                 (SKILL / relative).read_bytes())


if __name__ == '__main__':
    unittest.main()
