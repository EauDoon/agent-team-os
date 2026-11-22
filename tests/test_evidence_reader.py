import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.check import MAX_BYTES, load_json_snapshot, read_json_bytes
from scripts.inspect_records import GENERIC_ERROR

ROOT = Path(__file__).resolve().parents[1]


class EvidenceReaderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'evidence.json'
        self.path.write_bytes(b'{}')

    def test_snapshot_hashes_original_utf8_and_line_endings(self):
        raw = '{\r\n  "source": "caf\u00e9"\r\n}\r\n'.encode('utf-8')
        self.path.write_bytes(raw)
        self.assertEqual(load_json_snapshot(self.path), ({'source': 'caf\u00e9'}, hashlib.sha256(raw).hexdigest()))

    def test_exact_byte_limit_is_accepted(self):
        raw = b'{}' + b' ' * (MAX_BYTES - 2)
        self.path.write_bytes(raw)
        self.assertEqual(read_json_bytes(self.path), raw)

    def test_one_byte_over_limit_is_rejected(self):
        self.path.write_bytes(b'{}' + b' ' * (MAX_BYTES - 1))
        with self.assertRaisesRegex(ValueError, 'exceeds 1 MiB'):
            read_json_bytes(self.path)

    def test_regular_file_through_symlink_is_accepted(self):
        link = self.path.with_name('linked.json')
        try:
            link.symlink_to(self.path)
        except (NotImplementedError, OSError):
            self.skipTest('symlink creation unavailable')
        self.assertEqual(read_json_bytes(link), b'{}')

    def test_nonregular_path_modes_are_rejected_before_open(self):
        for mode in (stat.S_IFIFO, stat.S_IFSOCK, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFDIR):
            with self.subTest(mode=mode), patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=mode)), \
                    patch('os.open', wraps=os.open) as opened:
                with self.assertRaisesRegex(ValueError, 'regular file'):
                    read_json_bytes(self.path)
                opened.assert_not_called()

    def test_nonregular_descriptor_is_closed_without_reading(self):
        with self.path.open('rb') as handle, patch('builtins.open', return_value=handle), \
                patch('os.fstat', return_value=SimpleNamespace(st_mode=stat.S_IFIFO)) as status, \
                patch.object(handle, 'read', wraps=handle.read) as read:
            descriptor = handle.fileno()
            with self.assertRaisesRegex(ValueError, 'regular file'):
                read_json_bytes(self.path)
            status.assert_called_with(descriptor)
            read.assert_not_called()
            self.assertTrue(handle.closed)

    def test_open_uses_read_only_and_available_nonblocking_flags(self):
        with patch('os.open', wraps=os.open) as opened:
            self.assertEqual(read_json_bytes(self.path), b'{}')
        opened.assert_called_once()
        flags = opened.call_args.args[1]
        self.assertEqual(flags & (os.O_WRONLY | os.O_RDWR), 0)
        if hasattr(os, 'O_NONBLOCK'):
            self.assertEqual(flags & os.O_NONBLOCK, os.O_NONBLOCK)

    def test_stat_error_is_propagated_before_open(self):
        with patch.object(Path, 'stat', side_effect=PermissionError), patch('os.open', wraps=os.open) as opened:
            with self.assertRaises(PermissionError):
                read_json_bytes(self.path)
            opened.assert_not_called()

    def test_missing_path_still_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            read_json_bytes(self.path.with_name('missing.json'))

    def test_directory_uses_generic_evidence_cli_error(self):
        result = subprocess.run([sys.executable, 'scripts/inspect_records.py', 'evidence', str(self.path.parent)],
                                cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {'ok': False, 'error': GENERIC_ERROR})
        self.assertEqual(result.stderr, '')
