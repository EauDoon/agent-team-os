import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.version import package_version

ROOT = Path(__file__).resolve().parents[1]
CLIS = ('check', 'author', 'inspect_records', 'evaluate', 'packet', 'validate', 'package', 'verify_package')


class VersionTests(unittest.TestCase):
    def test_every_cli_reports_the_package_version_in_both_modes(self):
        expected = f'agent-team {package_version()}\n'
        for name in CLIS:
            for entry in [[f'scripts/{name}.py'], ['-m', f'scripts.{name}']]:
                with self.subTest(entry=entry):
                    result = subprocess.run([sys.executable, *entry, '--version'], cwd=ROOT,
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected)
                    self.assertEqual(result.stderr, '')

    def test_version_script_prints_the_bare_version(self):
        for entry in [['scripts/version.py'], ['-m', 'scripts.version']]:
            result = subprocess.run([sys.executable, *entry], cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, package_version() + '\n')
            self.assertEqual(result.stdout.strip(), (ROOT / 'VERSION').read_text(encoding='utf-8').strip())

    def test_package_version_requires_a_strict_semantic_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for valid in ('1.2.3', '0.6.0\n', ' 10.0.1 '):
                (root / 'VERSION').write_text(valid, encoding='utf-8')
                self.assertEqual(package_version(root), valid.strip())
            for invalid in ('1.2', '01.2.3', '1.2.3-alpha', 'v1.2.3', '1.2.3\n4.5.6', ''):
                with self.subTest(version=invalid):
                    (root / 'VERSION').write_text(invalid, encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, 'semantic X.Y.Z'):
                        package_version(root)
            (root / 'VERSION').write_bytes(b'\xff1.2.3')
            with self.assertRaisesRegex(ValueError, 'semantic X.Y.Z'):
                package_version(root)

    def test_damaged_version_fails_only_the_version_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'scripts', root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / 'schemas', root / 'schemas')
            (root / 'VERSION').write_text('not-a-version\n', encoding='utf-8')
            brief = root / 'brief.json'
            brief.write_text(json.dumps(dict.fromkeys(
                ['role', 'access_scope', 'task', 'evidence', 'output_contract', 'stop_condition'],
                'Supplied fictional task.')), encoding='utf-8')
            checked = subprocess.run([sys.executable, str(root / 'scripts/check.py'), 'brief', str(brief)],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            reported = subprocess.run([sys.executable, str(root / 'scripts/check.py'), '--version'],
                                      capture_output=True, text=True, timeout=30)
            self.assertEqual(reported.returncode, 1)
            self.assertEqual(reported.stdout, '')
            self.assertIn('semantic X.Y.Z', reported.stderr)
            self.assertNotIn('Traceback', reported.stderr)

    def test_author_subcommands_keep_the_connect_wire_version_option(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief = root / 'brief.json'
            brief.write_text(json.dumps({**dict.fromkeys(
                ['role', 'access_scope', 'task', 'evidence', 'output_contract', 'stop_condition'],
                'Supplied fictional task.'), 'role_brief_version': 'agent-team-role-brief/v0.1'}), encoding='utf-8')
            output = root / 'handoff.json'
            result = subprocess.run([sys.executable, 'scripts/author.py', 'handoff',
                                     '--version', 'agent-team-connect/v0.2', '--from', 'orchestrator',
                                     '--to', 'maker', '--message-id', 'h1', '--correlation-id', 'c1',
                                     '--brief', str(brief), '--output', str(output)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['connect_version'],
                             'agent-team-connect/v0.2')


if __name__ == '__main__':
    unittest.main()
