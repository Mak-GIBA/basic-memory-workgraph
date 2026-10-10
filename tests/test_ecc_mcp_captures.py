"""Validate regrading controls without model, network or MCP calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'tools/ecc-on-demand/evaluation'
spec = importlib.util.spec_from_file_location('ecc_capture_check', ROOT / 'check_captures.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ecc-capture-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'captures'
        shutil.copytree(ROOT, self.root)

    def update_reasoning(self, change, *, record_hash=True):
        path = self.root / 'evidence/reasoning-results.json'
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data, ensure_ascii=False))
        if record_hash:
            manifest_path = self.root / 'capture-manifest.json'
            manifest = json.loads(manifest_path.read_text())
            for row in manifest:
                if row['path'] == 'evidence/reasoning-results.json':
                    row['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))

    def test_negative_results_and_documentation_lineage_are_preserved(self):
        result = capture.check(self.root)
        self.assertEqual(result['summary']['file'], {'A': {'correct': 8, 'total': 8}, 'B': {'correct': 6, 'total': 8}})
        self.assertEqual(result['summary']['documentation_retrieval_capture'], ['evidence/pilot/browser-invalid-arguments-tools-results.json'])
        self.assertEqual(sum(row['output'] == {} for row in result['trials']), 2)

    def test_actual_answer_changes_grade_without_trusting_saved_correct_count(self):
        self.update_reasoning(lambda d: d['rows'][0]['outputs'].update({'deadline-boundary': [1000, 1100, 1300, 1700]}))
        result = capture.check(self.root)
        self.assertEqual(result['summary']['reasoning']['A'], {'correct': 11, 'total': 12})

    def test_missing_trial_and_missing_mcp_invocation_are_rejected(self):
        for change in [lambda d: d['rows'].pop(), lambda d: d['rows'][1].update(tool_calls=[])]:
            with self.subTest(change=change):
                shutil.copytree(ROOT, self.root, dirs_exist_ok=True)
                self.update_reasoning(change)
                with self.assertRaises(AssertionError):
                    capture.check(self.root)

    def test_changed_capture_hash_is_rejected(self):
        self.update_reasoning(lambda d: d['rows'][0]['outputs'].update({'critical-path': 0}), record_hash=False)
        with self.assertRaises(AssertionError):
            capture.check(self.root)

    def test_boolean_and_number_do_not_count_as_the_same_answer(self):
        self.assertFalse(capture.same_json(True, 1))
        self.assertFalse(capture.same_json({'value': False}, {'value': 0}))
        self.assertFalse(capture.same_json([1, 2], [2, 1]))
        self.assertTrue(capture.same_json({'a': 1, 'b': True}, {'b': True, 'a': 1}))
