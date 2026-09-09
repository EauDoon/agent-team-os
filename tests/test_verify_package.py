import contextlib
import io
import json
import lzma
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import BadZipFile, ZipFile, ZipInfo, ZIP_STORED, ZIP_DEFLATED, ZIP_BZIP2, ZIP_LZMA
import zlib

from scripts.package import main as package_main, files_for, version_for
from scripts.verify_package import verify

ROOT = Path(__file__).resolve().parents[1]


class PackageVerificationTests(unittest.TestCase):
    def test_supported_and_rejected_codecs_with_real_valid_and_corrupt_members(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'codec.zip'
            for method, decoding_error in [(ZIP_LZMA, lzma.LZMAError), (ZIP_BZIP2, OSError),
                                            (ZIP_STORED, BadZipFile), (ZIP_DEFLATED, zlib.error)]:
                with ZipFile(archive, 'w') as handle:
                    for index, path in enumerate(files_for(ROOT)):
                        info = ZipInfo(f'agent-team-{version_for(ROOT)}/' + path.relative_to(ROOT).as_posix())
                        info.external_attr = 0o100644 << 16
                        info.compress_type = method if index == 0 else ZIP_DEFLATED
                        handle.writestr(info, path.read_bytes())
                original = archive.read_bytes()
                with ZipFile(archive) as handle:
                    first = handle.infolist()[0]
                    # Establish that each unmodified codec fixture is valid.
                    self.assertEqual(handle.read(first), files_for(ROOT)[0].read_bytes())
                name_length, extra_length = struct.unpack_from('<HH', original, first.header_offset + 26)
                compressed_start = first.header_offset + 30 + name_length + extra_length
                corrupt = bytearray(original)
                if method == ZIP_LZMA:
                    corrupt[compressed_start + 4] = 255  # Invalid LZMA filter properties.
                elif method == ZIP_DEFLATED:
                    corrupt[compressed_start] = 7  # Reserved deflate block type.
                else:
                    corrupt[compressed_start] ^= 255  # BZIP2 header or stored-content CRC failure.
                archive.write_bytes(corrupt)
                with ZipFile(archive) as handle, self.assertRaises(decoding_error):
                    handle.read(handle.infolist()[0])
                for raw, corrupted in [(corrupt, True), (original, False)]:
                    archive.write_bytes(raw)
                    accepted = not corrupted and method in {ZIP_STORED, ZIP_DEFLATED}
                    for entry in [['scripts/verify_package.py'], ['-m', 'scripts.verify_package']]:
                        result = subprocess.run([sys.executable, *entry, str(archive)], cwd=ROOT,
                                                capture_output=True, text=True, timeout=5)
                        self.assertEqual(result.returncode, 0 if accepted else 1)
                        self.assertEqual(result.stderr, '')
                        payload = json.loads(result.stdout)
                        if accepted:
                            self.assertTrue(payload['ok'])
                        else:
                            self.assertEqual(payload, {'ok': False, 'error': 'archive could not be verified against the current source tree'})
                    if method not in {ZIP_STORED, ZIP_DEFLATED}:
                        with patch.object(ZipFile, 'open', side_effect=AssertionError('decoder must not be opened')):
                            with self.assertRaisesRegex(ValueError, 'compression method'):
                                verify(archive, ROOT)

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
                               (unsupported_method, ValueError)]:
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
