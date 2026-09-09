import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.packet import inspect_packet, record_path

ROOT = Path(__file__).resolve().parents[1]


class PacketTests(unittest.TestCase):
    def test_bundled_packet_checks_actual_bytes(self):
        result = inspect_packet(ROOT / 'templates/operator-packet.json')
        self.assertTrue(result['ok'])
        for record in result['records']:
            self.assertEqual(record['sha256'], hashlib.sha256((ROOT / 'templates' / record['path']).read_bytes()).hexdigest())

    def test_unsafe_paths_fail_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['../outside.json', '/outside.json', 'C:/outside.json', 'file.json:stream', 'a\\b.json', './file.json', 'a//b.json']:
                with self.assertRaises(ValueError, msg=name):
                    record_path(root, name)

    def test_bad_record_preserves_other_results_and_duplicates_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'plan.json').write_bytes((ROOT / 'templates/routing-plan.json').read_bytes())
            packet = {'packet_version': 'agent-team-packet/v0.1', 'task_id': 'fictional-task',
                      'records': [{'id': 'plan', 'kind': 'plan', 'path': 'plan.json'},
                                  {'id': 'brief', 'kind': 'brief', 'path': 'missing.json'}]}
            path = root / 'packet.json'
            path.write_text(json.dumps(packet))
            result = inspect_packet(path)
            self.assertFalse(result['ok'])
            self.assertTrue(result['records'][0]['ok'])
            packet['records'][1]['id'] = 'plan'
            path.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                inspect_packet(path)

    def test_actual_packet_cli_in_both_modes(self):
        for entry in [['scripts/packet.py'], ['-m', 'scripts.packet']]:
            result = subprocess.run([sys.executable, *entry, 'templates/operator-packet.json'],
                                    cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
