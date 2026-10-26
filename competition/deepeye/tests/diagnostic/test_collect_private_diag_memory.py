"""New Reader allocation/identity controls; no runtime or board import/execution."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

RECORDS = []


class ObservedFile:
    def __init__(self, f, path, bound, mutation):
        self.f, self.path, self.bound, self.mutation = f, path, bound, mutation

    def __enter__(self):
        self.f.__enter__()
        return self

    def __exit__(self, *args):
        return self.f.__exit__(*args)

    def fileno(self):
        return self.f.fileno()

    def read(self, size=-1):
        RECORDS.append({'path': str(self.path), 'requested_bytes': size, 'bound': self.bound})
        if self.mutation:
            self.mutation()
        if size < 0 or size > self.bound:
            raise AssertionError('read request exceeds observed-file-size sentinel bound')
        return self.f.read(size)


class ReaderMemoryControls(unittest.TestCase):
    def setUp(self):
        self.root = OUTPUT / self._testMethodName
        self.root.mkdir()
        self.path = self.root / 'input.bin'
        self.path.write_bytes(b'original bytes\n')
        self.reader = C.Reader(self.root / 'output')

    def observed(self, bound, mutation=None):
        original = Path.open
        path = self.path

        def opened(p, *args, **kwargs):
            f = original(p, *args, **kwargs)
            return ObservedFile(f, p, bound, mutation) if p == path and args == ('rb',) else f
        return patch.object(Path, 'open', opened)

    def unchanged(self):
        self.assertEqual(self.reader.total, 0)
        self.assertEqual(self.reader.identities, set())

    def test_tiny_file_uses_size_plus_one(self):
        expected = self.path.read_bytes()
        with self.observed(len(expected) + 1):
            self.assertEqual(self.reader.read(self.path), expected)
        self.assertEqual(RECORDS[-1]['requested_bytes'], len(expected) + 1)
        self.assertEqual(self.reader.total, len(expected))

    def test_four_mib_file_does_not_request_max_file(self):
        expected = bytes(range(256)) * (4 * 1024 * 1024 // 256)
        self.path.write_bytes(expected)
        with self.observed(len(expected) + 1):
            actual = self.reader.read(self.path)
        self.assertEqual(hashlib.sha256(actual).digest(), hashlib.sha256(expected).digest())
        self.assertEqual(RECORDS[-1]['requested_bytes'], 4 * 1024 * 1024 + 1)

    def test_exact_limit_accepted(self):
        size = self.path.stat().st_size
        with self.observed(size + 1):
            self.assertEqual(len(self.reader.read(self.path, size)), size)

    def test_over_limit_rejected_before_read(self):
        count = len(RECORDS)
        with self.observed(0), self.assertRaisesRegex(C.Rejected, 'size limit'):
            self.reader.read(self.path, self.path.stat().st_size - 1)
        self.assertEqual(len(RECORDS), count)
        self.unchanged()

    def test_total_limit_rejected_before_read(self):
        self.reader.total = C.MAX_SELECTED_TOTAL
        count = len(RECORDS)
        with self.observed(0), self.assertRaisesRegex(C.Rejected, 'size limit'):
            self.reader.read(self.path)
        self.assertEqual(len(RECORDS), count)
        self.assertEqual(self.reader.total, C.MAX_SELECTED_TOTAL)
        self.assertEqual(self.reader.identities, set())

    def test_empty_file_rejected(self):
        self.path.write_bytes(b'')
        with self.observed(0), self.assertRaisesRegex(C.Rejected, 'size limit'):
            self.reader.read(self.path)
        self.unchanged()

    def test_growth_rejected_without_state_commit(self):
        size = self.path.stat().st_size
        def grow():
            with self.path.open('ab') as f:
                f.write(b'growth')
        with self.observed(C.MAX_FILE + 1, grow), self.assertRaisesRegex(C.Rejected, 'changed'):
            self.reader.read(self.path)
        self.unchanged()
        self.assertGreater(self.path.stat().st_size, size)

    def test_truncation_rejected_without_state_commit(self):
        def shrink():
            with self.path.open('r+b') as f:
                f.truncate(2)
        with self.observed(C.MAX_FILE + 1, shrink), self.assertRaisesRegex(C.Rejected, 'changed'):
            self.reader.read(self.path)
        self.unchanged()

    def test_mtime_change_rejected_without_state_commit(self):
        before = self.path.stat()
        def touch():
            os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns + 10_000_000_000))
        with self.observed(C.MAX_FILE + 1, touch), self.assertRaisesRegex(C.Rejected, 'changed'):
            self.reader.read(self.path)
        self.unchanged()

    def test_same_input_reuse_rejected(self):
        first = self.reader.read(self.path)
        with self.assertRaisesRegex(C.Rejected, 'alias'):
            self.reader.read(self.path)
        self.assertEqual(self.reader.total, len(first))
        self.assertEqual(len(self.reader.identities), 1)

    def test_hardlink_rejected(self):
        alias = self.root / 'alias.bin'
        os.link(self.path, alias)
        with self.assertRaisesRegex(C.Rejected, 'alias'):
            self.reader.read(alias)
        self.unchanged()

    def test_output_contains_input_rejected(self):
        self.reader = C.Reader(self.root)
        with self.assertRaisesRegex(C.Rejected, 'aliases'):
            self.reader.read(self.path)
        self.unchanged()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--collector', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    OUTPUT = args.output.resolve()
    OUTPUT.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('collector_memory_target', args.collector)
    C = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = C
    spec.loader.exec_module(C)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReaderMemoryControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'collector_sha256': hashlib.sha256(args.collector.read_bytes()).hexdigest(),
              'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'tests_run': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'skipped': len(result.skipped),
              'read_requests': RECORDS, 'board': 'not_run; A-only'}
    (OUTPUT / 'RESULT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
