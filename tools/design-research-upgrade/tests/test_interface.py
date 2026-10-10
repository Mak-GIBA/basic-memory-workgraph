from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=os.environ.get('CODEX_INTERFACE_SOURCE_ROOT')
SCRIPT=Path(SOURCE)/'tools/design-research/skill/scripts' if SOURCE else ROOT/'overlay/tools/design-research/skill/scripts'
sys.path[:0]=[str(ROOT), str(SCRIPT), str(ROOT/'core_upgrade/overlay/tools/design-research/skill/scripts')]
import codex_interface as ci
from command_assets import assets, COMMANDS


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'project with spaces'; self.root.mkdir()
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {}, clear=False).start(); os.environ.pop('DR_GAN_CHILD', None)
    def invoke(self,*args):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            code=ci.main(list(args)+['--project',str(self.root)])
        return code,json.loads(out.getvalue()) if out.getvalue().strip() else None
    def state(self,slug='old',run='run-1',status='research_complete',mode='research',phase='complete',workstream=None):
        p=self.root/f'docs/design-research/{slug}/runs/{run}/state.json'; p.parent.mkdir(parents=True,exist_ok=True)
        s={'schema_version':1,'run_id':run,'status':status,'phase':phase,
           'config':{'mode':mode,'project':str(self.root),'slug':slug,'brief':'説明用の研究'},'dossier':{'candidates':[]}}
        if workstream:s['workstream_context']=workstream
        p.write_text(json.dumps(s)); r=p.parent/'reports/report.md'; r.parent.mkdir(exist_ok=True); r.write_text('# 架空fixture\n実測ではない。')
        return p
    def req(self):
        p=self.root/'docs/upstream/requirements.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# Requirements\nExample requirements.\n');return p
    def tree(self):
        return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def plan(self):
        src=ROOT/'core_upgrade/examples/workstream-demo'
        shutil.copytree(src,self.root,dirs_exist_ok=True)
        return '.specify/workbench/research-plan.json'
    def test_empty_run_list_creates_nothing(self):
        before=self.tree();c,r=self.invoke('runs');self.assertEqual(c,0);self.assertEqual(r['runs'],[]);self.assertEqual(self.tree(),before)
    def test_prepare_reassess_auto_resolves_unique_input(self):
        self.state();self.req();before=self.tree();c,r=self.invoke('prepare','reassess','--brief','速度条件が変更された')
        self.assertEqual(c,0);self.assertEqual(r['mode'],'reassess');self.assertIn('--prior-run',r['argv']);self.assertIn('--requirements',r['argv']);self.assertEqual(r['target_methods'],5);self.assertFalse(r['executed']);self.assertEqual(before,self.tree());self.assertEqual(len(r['dispatch_sha256']),64)
    def test_reassess_never_silently_picks_latest(self):
        self.state();self.state('another','run-2');c,r=self.invoke('prepare','reassess','--brief','比較し直す')
        self.assertEqual(c,2);self.assertEqual(r['status'],'needs_selection');self.assertEqual(len(r['choices']),2)
    def test_topic_selects_real_unique_prior(self):
        self.state();self.state('another','run-2');c,r=self.invoke('prepare','reassess','--topic','another','--brief','比較し直す')
        self.assertEqual(c,0);self.assertEqual(r['selected_run']['run_id'],'run-2')
    def test_explicit_noncomplete_prior_refused(self):
        p=self.state(status='blocked');c,r=self.invoke('prepare','reassess','--prior-run',str(p),'--brief','比較')
        self.assertEqual(c,2);self.assertFalse(r['executed'])
    def test_missing_archive_not_completed(self):
        p=self.state();(p.parent/'reports/report.md').unlink();c,r=self.invoke('prepare','reassess','--brief','比較');self.assertEqual(c,2)
    def test_legacy_archive_supported(self):
        p=self.state();(p.parent/'reports/report.md').rename(p.parent/'reports/design-research.md');c,r=self.invoke('prepare','reassess','--brief','比較');self.assertEqual(c,0)
    def test_new_slug_avoids_previous_and_existing(self):
        self.state();(self.root/'docs/design-research/old-reassess').mkdir();c,r=self.invoke('prepare','reassess','--brief','比較');self.assertEqual(c,0);self.assertIn('old-reassess-2',r['argv'])
    def test_unsafe_slug_rejected(self):
        self.state();c,r=self.invoke('prepare','reassess','--slug','../../overwrite','--brief','比較');self.assertEqual(c,2)
    def test_symlink_prior_rejected(self):
        p=self.state();target=self.root/'real.json';p.rename(target);p.symlink_to(target);c,r=self.invoke('prepare','reassess','--prior-run',str(p),'--brief','比較');self.assertEqual(c,2)
    def test_state_path_identity_mismatch_rejected(self):
        p=self.state();s=json.loads(p.read_text());s['run_id']='fabricated';p.write_text(json.dumps(s));c,r=self.invoke('prepare','reassess','--prior-run',str(p),'--brief','比較');self.assertEqual(c,2)
    def test_malformed_state_reported_not_hidden(self):
        p=self.state();p.write_text('{');c,r=self.invoke('runs');self.assertEqual(c,0);self.assertFalse(r['complete']);self.assertTrue(r['warnings'])
    def test_missing_change_reason_refused(self):
        self.state();c,r=self.invoke('prepare','reassess');self.assertEqual(c,2)
    def test_outside_requirements_refused(self):
        c,r=self.invoke('prepare','research','--brief','比較','--requirements','../outside.md');self.assertEqual(c,2)
    def test_sensitive_requirements_refused(self):
        c,r=self.invoke('prepare','research','--brief','比較','--requirements','.env');self.assertEqual(c,2)
    def test_two_canonical_candidates_need_selection(self):
        self.req();p=self.root/'.specify/workbench.json';p.parent.mkdir();p.write_text(json.dumps({'docs_dir':'docs/spec'}));r=self.root/'docs/spec/requirements.md';r.parent.mkdir();r.write_text('other');c,v=self.invoke('prepare','research','--brief','比較');self.assertEqual(c,2);self.assertEqual(v['status'],'needs_selection')
    def test_shell_metacharacters_remain_one_argument(self):
        c,r=self.invoke('prepare','research','--brief','a; $(touch PWNED) "quote"');self.assertEqual(c,0);self.assertIn('a; $(touch PWNED) "quote"',r['argv']);self.assertFalse((self.root/'PWNED').exists())
    def test_default_network_is_offline(self):
        c,r=self.invoke('prepare','research','--brief','比較');self.assertEqual(c,0);self.assertIn('--offline',r['argv']);self.assertNotIn('--allow-network',r['argv'])
    def test_profile_and_purpose_are_frozen_in_dispatch(self):
        c,r=self.invoke('prepare','research','--brief','比較','--evaluation-purpose','effectiveness')
        self.assertEqual(c,0);self.assertEqual(r['report_profile'],'comparison')
        self.assertEqual(r['evaluation_purpose'],'effectiveness')
        c,v=self.invoke('run','research','--brief','比較','--evaluation-purpose','effectiveness',
                        '--report-profile','proposed-method','--expect-dispatch',r['dispatch_sha256'])
        self.assertEqual(c,2);self.assertFalse(v['executed'])
    def test_resume_profile_or_purpose_override_refused(self):
        self.state(status='blocked')
        for flag,value in (('--report-profile','comparison'),('--evaluation-purpose','design')):
            c,r=self.invoke('prepare','resume',flag,value);self.assertEqual(c,2)
    def test_allowed_network_passed_explicitly(self):
        c,r=self.invoke('prepare','research','--brief','比較','--allow-network');self.assertEqual(c,0);self.assertIn('--allow-network',r['argv'])
    def test_resume_same_run_and_no_new_conditions(self):
        self.state(status='blocked',phase='evaluating');c,r=self.invoke('prepare','resume');self.assertEqual(c,0);self.assertEqual(r['argv'][2:4],['resume','run-1']);c,r=self.invoke('prepare','resume','--brief','change');self.assertEqual(c,2)
    def test_completed_run_cannot_resume(self):
        self.state();c,r=self.invoke('prepare','resume');self.assertEqual(c,2)
    def test_interrupted_check_at_iteration_limit_not_resumable(self):
        p=self.state(status='cancelled',phase='experiments')
        value=json.loads(p.read_text());value['iteration']=1;value['config']['max_iterations']=1;p.write_text(json.dumps(value))
        c,r=self.invoke('prepare','resume');self.assertEqual(c,2)
    def test_interrupted_fixer_not_resumed(self):
        self.state(status='blocked',mode='run',phase='fixing');c,r=self.invoke('prepare','resume');self.assertEqual(c,2)
    def test_resume_network_cannot_be_changed(self):
        self.state(status='blocked');c,r=self.invoke('prepare','resume','--allow-network');self.assertEqual(c,2)
    def test_child_does_not_dispatch(self):
        with patch.dict(os.environ,{'DR_GAN_CHILD':'1'}):c,r=self.invoke('prepare','research','--brief','比較')
        self.assertEqual(c,2)
    def test_plan_inspection_does_not_run_experiments(self):
        plan=self.plan();before=self.tree();c,r=self.invoke('workstreams','--plan',plan);self.assertEqual(c,0);self.assertFalse(r['executed']);self.assertEqual(r['waves'],[['RP1','RP2'],['RP3']]);self.assertEqual(self.tree(),before)
    def test_single_workstream_uses_frozen_plan(self):
        plan=self.plan();c,r=self.invoke('prepare','workstream','--plan',plan,'--workstream-id','RP1');self.assertEqual(c,0);self.assertIn('logic-1',r['argv']);self.assertIn('--workstream-plan',r['argv'])
    def test_workstream_override_refused(self):
        self.plan();c,r=self.invoke('prepare','workstream','--workstream-id','RP1','--brief','override');self.assertEqual(c,2)
    def test_workstream_dependencies_not_assumed_complete(self):
        self.plan();c,r=self.invoke('prepare','workstream','--workstream-id','RP3');self.assertEqual(c,2)
    def test_workstream_uses_same_plan_completed_dependencies(self):
        plan=self.plan();h=hashlib.sha256((self.root/plan).read_bytes()).hexdigest()
        self.state('logic-1','run-1',workstream={'workstream_id':'RP1','plan_sha256':h})
        self.state('logic-2','run-2',workstream={'workstream_id':'RP2','plan_sha256':h})
        c,r=self.invoke('prepare','workstream','--workstream-id','RP3');self.assertEqual(c,0);self.assertEqual(len(r['context']['dependency_runs']),2)
    def test_wrong_plan_dependency_refused(self):
        self.plan();self.state('logic-1','run-1',workstream={'workstream_id':'RP1','plan_sha256':'0'*64})
        c,r=self.invoke('prepare','workstream','--workstream-id','RP3');self.assertEqual(c,2)
    def test_ambiguous_dependency_requires_selection(self):
        plan=self.plan();h=hashlib.sha256((self.root/plan).read_bytes()).hexdigest()
        self.state('logic-1','run-1',workstream={'workstream_id':'RP1','plan_sha256':h});self.state('logic-1','run-2',workstream={'workstream_id':'RP1','plan_sha256':h})
        c,r=self.invoke('prepare','workstream','--workstream-id','RP3');self.assertEqual(c,2);self.assertEqual(r['status'],'needs_selection')
    def test_run_requires_unchanged_prepare_lease(self):
        c,r=self.invoke('run','research','--brief','比較');self.assertEqual(c,2);self.assertIn('expect-dispatch',r['reason'])
    def test_changed_requirements_invalidates_lease(self):
        p=self.req();c,r=self.invoke('prepare','research','--brief','比較');p.write_text('changed');c,r=self.invoke('run','research','--brief','比較','--expect-dispatch',r['dispatch_sha256']);self.assertEqual(c,2)
    def test_real_subprocess_dispatch_propagates_exit_status(self):
        # Only the installed harness boundary is substituted. A real local Bash process is executed.
        scripts=self.root/'fake installed scripts';scripts.mkdir();(scripts/'gan-harness.sh').write_text('#!/usr/bin/env bash\nexit 7\n')
        with patch.object(ci,'HERE',scripts):
            c,r=self.invoke('prepare','research','--brief','比較')
            c,r=self.invoke('run','research','--brief','比較','--expect-dispatch',r['dispatch_sha256'])
        self.assertEqual(c,7)
    def test_one_user_facing_skill_and_internal_modes(self):
        self.assertEqual(COMMANDS,{})
        self.assertEqual(assets(),{})
        from pathlib import Path
        guide=(ROOT/'overlay/tools/design-research/skill/references/workflow-guide.md').read_text()
        for mode in ('research','reassess','resume','workstream','runs','plan'):
            self.assertIn(mode,guide)
        self.assertIn('$design-research',guide)
        self.assertIn('plan-only',guide)


if __name__=='__main__':unittest.main()
