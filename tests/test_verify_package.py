import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.package import main as package_main
from scripts.verify_package import verify

ROOT = Path(__file__).resolve().parents[1]


class PackageVerificationTests(unittest.TestCase):
    def test_source_match_digest_and_unexpected_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['package.py', '--output', directory]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(package_main(), 0)
            archive = next(Path(directory).glob('*.zip'))
            result = verify(archive, ROOT)
            self.assertGreater(result['files'], 20)
            self.assertEqual(verify(archive, ROOT, result['sha256']), result)
            with self.assertRaises(ValueError):
                verify(archive, ROOT, '0' * 64)
            with ZipFile(archive, 'a') as handle:
                handle.writestr('../unexpected.txt', 'untrusted')
            with self.assertRaises(ValueError):
                verify(archive, ROOT)

    def test_modified_source_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'VERSION').write_text('1.0.0')
            (root / 'package-manifest.json').write_text('["payload.txt"]')
            (root / 'payload.txt').write_text('good')
            from zipfile import ZipInfo
            archive = root / 'fixture.zip'
            info = ZipInfo('agent-team-1.0.0/payload.txt')
            info.external_attr = 0o100644 << 16
            with ZipFile(archive, 'w') as handle:
                handle.writestr(info, 'evil')
            with self.assertRaisesRegex(ValueError, 'content differs'):
                verify(archive, root)


if __name__ == '__main__':
    unittest.main()
