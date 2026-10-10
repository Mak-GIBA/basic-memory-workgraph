"""Reject corrupted or self-certified saved results without model calls."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import hashlib

ROOT=Path(__file__).resolve().parents[1]/'tools/ecc-on-demand/evaluation'
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('workflow_check',ROOT/'check_workflows.py')
check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)


class WorkflowCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'workflows';shutil.copytree(ROOT/'workflows',self.root)

    def change(self,study,mutation,rehash=True):
        path=self.root/study/'results.json';data=json.loads(path.read_text());mutation(data)
        path.write_text(json.dumps(data,ensure_ascii=False))
        if rehash:
            manifest=self.root/'manifest.json';entries=json.loads(manifest.read_text())
            for row in entries:
                if row['path']==str(path.relative_to(self.root)):
                    row['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(entries))

    def test_real_captures_regrade_with_negative_information_results(self):
        summary=check.check(self.root)
        self.assertEqual(summary['information']['token-optimizer']['correct'],6)
        self.assertEqual(summary['implementation-executed']['context7']['correct'],8)
        self.assertEqual(summary['playwright-independent-state']['playwright']['correct'],4)

    def test_tampered_hash_rejected(self):
        self.change('documentation',lambda x:x['rows'][0]['outputs'].update({'httpx-pool':'wrong'}),False)
        with self.assertRaises(AssertionError):check.check(self.root)

    def test_self_reported_correct_count_cannot_override_wrong_answer(self):
        self.change('documentation',lambda x:x['rows'][0]['outputs'].update({'httpx-pool':'wrong'}))
        with self.assertRaises(AssertionError):check.check(self.root)

    def test_target_mcp_must_actually_be_used(self):
        self.change('documentation',lambda x:x['rows'][1].update(tool_calls=[]))
        with self.assertRaises(AssertionError):check.check(self.root)

    def test_answer_only_does_not_prove_browser_completion(self):
        self.change('playwright-independent-state',lambda x:x['rows'][1]['server_observations'].update(orders=[]))
        with self.assertRaises(AssertionError):check.check(self.root)
