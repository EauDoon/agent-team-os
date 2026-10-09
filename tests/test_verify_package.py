import contextlib
import io
import json
import lzma
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from zipfile import (
    ZIP_BZIP2,
    ZIP_DEFLATED,
    ZIP_LZMA,
    ZIP_STORED,
    BadZipFile,
    ZipFile,
    ZipInfo,
)

from scripts.package import files_for, version_for
from scripts.package import main as package_main
from scripts.verify_package import verify

ROOT = Path(__file__).resolve().parents[1]


class PackageVerificationTests(unittest.TestCase):
    def test_unicode_output_path_reports_success_with_ascii_process_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'caf\u00e9-\u6771\u4eac'
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/package.py'), '--output', str(output)],
                env={**os.environ, 'PYTHONIOENCODING': 'ascii'}, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            archive = next(output.glob('*.zip'))
            self.assertIn(str(archive.resolve()), result.stdout.decode('utf-8'))
            digest = archive.with_suffix('.zip.sha256').read_text(encoding='ascii').split()[0]
            self.assertTrue(verify(archive, ROOT, digest)['ok'])

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
            built = next(Path(directory).glob('*.zip'))
            # The builder stores members. Archives from 0.5.0 and earlier use
            # Deflate, so rewrite the built members to keep that path covered.
            archive = Path(directory) / 'deflate.zip'
            with ZipFile(built) as source, ZipFile(archive, 'w') as target:
                for member in source.infolist():
                    info = ZipInfo(member.filename, member.date_time)
                    info.create_system = member.create_system
                    info.external_attr = member.external_attr
                    info.compress_type = ZIP_DEFLATED
                    target.writestr(info, source.read(member))
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

    def test_builder_stores_members_without_any_compression_codec(self):
        # crc32 is a fixed function; a compressor is the only part whose bytes
        # vary between zlib implementations. Refusing it proves none is used.
        def refuse(*_args, **_kwargs):
            raise AssertionError('the builder must not compress')

        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['package.py', '--output', directory]), \
                 patch.object(zlib, 'compressobj', refuse), patch.object(zlib, 'compress', refuse), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(package_main(), 0)
            archive = next(Path(directory).glob('*.zip'))
            with ZipFile(archive) as handle:
                members = handle.infolist()
            self.assertEqual(len(members), len(files_for(ROOT)))
            self.assertEqual({member.compress_type for member in members}, {ZIP_STORED})
            self.assertTrue(verify(archive, ROOT)['ok'])

    def test_two_builds_are_byte_identical_despite_source_mtimes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'source'
            for path in files_for(ROOT):
                target = root / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
            for name in ('VERSION', 'package-manifest.json'):
                (root / name).write_bytes((ROOT / name).read_bytes())
            sources = sorted(path for path in root.rglob('*') if path.is_file())

            def build(output, stamp):
                for path in sources:
                    os.utime(path, (stamp, stamp))
                result = subprocess.run([sys.executable, str(root / 'scripts/package.py'), '--output', str(output)],
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                archive = next(output.glob('*.zip'))
                return archive.read_bytes(), archive.with_suffix('.zip.sha256').read_bytes()

            first = build(base / 'one', 1_000_000_000)
            second = build(base / 'two', 1_700_000_000)
            self.assertEqual(first, second)

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
