import contextlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED
import zlib

from scripts.package import main as package_main
from scripts.verify_package import verify

ROOT = Path(__file__).resolve().parents[1]


class PackageVerificationTests(unittest.TestCase):
    def test_archive_decoding_failures_return_generic_json_in_both_cli_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['package.py', '--output', directory]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(package_main(), 0)
            archive = next(Path(directory).glob('*.zip'))
            original = archive.read_bytes()
            with ZipFile(archive) as handle:
                first = handle.infolist()[0]
                self.assertEqual(first.compress_type, ZIP_DEFLATED)
                self.assertGreater(first.compress_size, 0)
            local = first.header_offset
            name_length, extra_length = struct.unpack_from('<HH', original, local + 26)
            compressed_start = local + 30 + name_length + extra_length
            end_record = original.rfind(b'PK\x05\x06')
            central_start = struct.unpack_from('<I', original, end_record + 16)[0]
            self.assertEqual(original[central_start:central_start + 4], b'PK\x01\x02')
            corrupt_deflate = bytearray(original)
            # BFINAL=1 and reserved BTYPE=3 are an invalid raw deflate block.
            corrupt_deflate[compressed_start] = 0x07
            unsupported_method = bytearray(original)
            struct.pack_into('<H', unsupported_method, local + 8, 99)
            struct.pack_into('<H', unsupported_method, central_start + 10, 99)
            for raw, error in [(original, None), (corrupt_deflate, zlib.error),
                               (unsupported_method, NotImplementedError)]:
                archive.write_bytes(raw)
                if error is not None:
                    with self.assertRaises(error):
                        verify(archive, ROOT)
                for entry in [['scripts/verify_package.py'], ['-m', 'scripts.verify_package']]:
                    result = subprocess.run([sys.executable, *entry, str(archive)], cwd=ROOT,
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 0 if error is None else 1)
                    self.assertEqual(result.stderr, '')
                    payload = json.loads(result.stdout)
                    if error is None:
                        self.assertTrue(payload['ok'])
                    else:
                        self.assertEqual(payload, {'ok': False, 'error': 'archive could not be verified against the current source tree'})

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
