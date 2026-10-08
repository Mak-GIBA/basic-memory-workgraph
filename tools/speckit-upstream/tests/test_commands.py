from __future__ import annotations
import json, os, re, subprocess, sys
from pathlib import Path
from unittest.mock import patch
from workbench import VERSION
from test_workbench import Base, demo_records
from workbench.common import *
from workbench.installer import install,uninstall,global_files
from workbench.command_skills import COMMANDS
from workbench.workflow import flow,run_gate,verify_gate,GATE_PATH
from workbench.cli import main

class CommandTests(Base):
    def test_fresh_offline_install_without_specify(self):
        with patch('workbench.installer.executable', return_value=None):
            install(True,skip_specify=True)
        m=read_json(locations()['config']/'install.json')
        self.assertEqual(m['specify']['status'],'skipped')
        self.assertIsNone(m['specify']['path'])
        self.assertTrue((locations()['skill'].parent/'upstream-new/SKILL.md').is_file())
    def test_idempotent_offline_install_without_specify(self):
        with patch('workbench.installer.executable', return_value=None):
            install(True,skip_specify=True)
            install(True,skip_specify=True)
        m=read_json(locations()['config']/'install.json')
        self.assertEqual(m['workbench_version'],'2.0.0')
    def test_six_explicit_commands_installed(self):
        install(True)
        for name in COMMANDS:
            folder=locations()['skill'].parent/name
            self.assertIn('name: '+name,(folder/'SKILL.md').read_text())
            self.assertIn('allow_implicit_invocation: false',(folder/'agents/openai.yaml').read_text())
    def test_fixed_flow_in_every_skill(self):
        install(True)
        for name,(mode,_) in COMMANDS.items():
            text=(locations()['skill'].parent/name/'SKILL.md').read_text()
            if mode in {'new','existing','change','bug','refactor','check'}:
                self.assertIn('flow --project <root> --mode '+mode,text)
                self.assertIn('gate --project <root> --write',text)
            elif mode=='review':
                self.assertIn('review --project <root> --checkpoint next --write',text)
            elif mode=='approve':
                self.assertIn('approve',text);self.assertIn('STALE_REVIEW',text)
    def test_no_unrendered_placeholders(self):
        for path,data in global_files().items():
            if path.name=='SKILL.md' and path.is_relative_to(locations()['skill'].parent):
                self.assertNotIn(b'@COMMAND@',data);self.assertNotIn(b'@ASSETS@',data)
    def test_command_collision_is_not_overwritten(self):
        p=locations()['skill'].parent/'upstream-existing/SKILL.md'
        p.parent.mkdir(parents=True);p.write_text('foreign skill')
        with self.assertRaises(WorkbenchError):install(True)
        self.assertEqual(p.read_text(),'foreign skill')
        self.assertFalse((locations()['config']/'install.json').exists())
    def test_user_edit_command_survives_update(self):
        install(True);p=locations()['skill'].parent/'upstream-bug/SKILL.md';p.write_text('edited')
        with self.assertRaises(WorkbenchError):install(True,update=True)
        self.assertEqual(p.read_text(),'edited')
    def test_commands_removed_on_uninstall(self):
        install(True);uninstall(True)
        for name in COMMANDS:self.assertFalse((locations()['skill'].parent/name/'SKILL.md').exists())
    def test_edited_command_kept_on_uninstall(self):
        install(True);p=locations()['skill'].parent/'upstream-new/SKILL.md';p.write_text('edited')
        uninstall(True);self.assertEqual(p.read_text(),'edited')
    def test_flow_unattached_is_readonly(self):
        text=flow(self.root,'existing');self.assertIn('未準備',text)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_flow_existing_uses_project(self):
        self.attach(docs_only=True);text=flow(self.root,'existing')
        self.assertIn('system=APP',text);self.assertIn('To-Be',text)
    def test_flow_all_modes(self):
        for mode in ['new','existing','change','bug','refactor','check']:
            text=flow(self.root,mode);self.assertIn('固定成果物',text);self.assertIn('実装',text)
    def test_flow_unknown_mode(self):
        with self.assertRaises(WorkbenchError):flow(self.root,'deploy')
    def test_command_list_cli(self):self.assertEqual(main(['commands']),0)
    def test_flow_cli_before_attach(self):
        self.assertEqual(main(['flow','--project',str(self.root),'--mode','existing']),0)
    def test_launcher_commands_from_space_path(self):
        install(True);r=command([str(locations()['bin']/'speckit-workbench'),'commands'])
        self.assertEqual(r.returncode,0);self.assertIn('$upstream-existing',r.stdout)
    def test_compat_entry_still_present(self):
        install(True);self.assertIn('name: speckit-workbench',(locations()['skill']/'SKILL.md').read_text())
    def test_instruction_only_no_hook_registration(self):
        install(True);self.assertFalse((self.home/'.codex/hooks.json').exists())

    def test_installed_skill_reference_targets_exist(self):
        install(True)
        folders=[locations()['skill']]+[locations()['skill'].parent/n for n in COMMANDS]
        release=locations()['data']/'releases'/VERSION
        for folder in folders:
            text=(folder/'SKILL.md').read_text()
            references=re.findall(r'`([^`\n]+/references/[^`\n]+\.md)`',text)
            if folder.name!='upstream-approve':
                self.assertTrue(references,folder.name)
            for reference in references:
                path=Path(reference)
                self.assertTrue(path.is_file(),reference)
                self.assertTrue(path.is_relative_to(release),reference)

    def test_installed_flow_references_are_available_without_research(self):
        install(True)
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for mode in ['existing','check','change','bug','refactor']:
            result=command([str(locations()['bin']/'speckit-workbench'),'flow',
                            '--project',str(self.root),'--mode',mode])
            self.assertEqual(result.returncode,0,result.stderr)
            references=re.findall(r'^参照資料: (.+)$',result.stdout,re.M)
            self.assertTrue(references,mode)
            for reference in references:
                self.assertTrue(Path(reference).is_file(),reference)
        after={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

class GateTests(Base):
    def setUp(self):super().setUp();self.attach(docs_only=True)
    def test_empty_gate_blocks(self):
        r=run_gate(self.root);self.assertFalse(r['passed']);self.assertEqual(r['verdict'],'BLOCKED')
        self.assertFalse((self.root/GATE_PATH).exists())
    def test_gate_cli_nonzero_on_empty(self):self.assertEqual(main(['gate','--project',str(self.root)]),1)
    def test_complete_gate_and_verify(self):
        self.write_records(demo_records());r=run_gate(self.root,True);self.assertTrue(r['passed'])
        self.assertTrue(verify_gate(self.root)['record_is_current'])
    def test_plan_not_run_not_app_pass(self):
        self.write_records(demo_records());r=run_gate(self.root,True)
        self.assertTrue(r['passed']);self.assertIn('アプリの合否は判定しない',r['scope'])
    def test_modified_doc_is_stale(self):
        self.write_records(demo_records());run_gate(self.root,True)
        p=self.root/'docs/upstream/product/vision.md';p.write_text(p.read_text()+'\nchanged\n')
        with self.assertRaisesRegex(WorkbenchError,'STALE'):verify_gate(self.root)
    def test_new_document_is_stale(self):
        self.write_records(demo_records());run_gate(self.root,True)
        (self.root/'docs/upstream/new.md').write_text('new')
        with self.assertRaisesRegex(WorkbenchError,'STALE'):verify_gate(self.root)
    def test_deleted_document_is_stale(self):
        self.write_records(demo_records());run_gate(self.root,True)
        (self.root/'docs/upstream/product/vision.md').unlink()
        with self.assertRaisesRegex(WorkbenchError,'STALE'):verify_gate(self.root)
    def test_config_change_is_stale(self):
        self.write_records(demo_records());run_gate(self.root,True)
        p=self.root/'.specify/workbench.json';c=read_json(p);c['note']='changed';p.write_text(json_text(c))
        with self.assertRaisesRegex(WorkbenchError,'STALE'):verify_gate(self.root)
    def test_report_generation_does_not_stale_gate(self):
        from workbench.trace import inspect,save_report
        self.write_records(demo_records());run_gate(self.root,True);save_report(self.root,inspect(self.root))
        self.assertTrue(verify_gate(self.root)['passed'])
    def test_forged_pass_flag_does_not_bypass_checks(self):
        run_gate(self.root,True);p=self.root/GATE_PATH;c=read_json(p);c['passed']=True;p.write_text(json_text(c))
        with self.assertRaisesRegex(WorkbenchError,'BLOCKED'):verify_gate(self.root)
    def test_failed_run_replaces_own_pass_receipt(self):
        self.write_records(demo_records());run_gate(self.root,True)
        (self.root/'docs/upstream/product/vision.md').write_text('TBD')
        r=run_gate(self.root,True);self.assertFalse(r['passed'])
        with self.assertRaises(WorkbenchError):verify_gate(self.root)
    def test_foreign_gate_file_preserved(self):
        p=self.root/GATE_PATH;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{"mine": true}')
        with self.assertRaises(WorkbenchError):run_gate(self.root,True)
        self.assertEqual(read_json(p),{'mine':True})
    def test_symlink_gate_preserved(self):
        p=self.root/GATE_PATH;p.parent.mkdir(parents=True,exist_ok=True);p.symlink_to(self.home/'elsewhere.json')
        with self.assertRaises(WorkbenchError):run_gate(self.root,True)
    def test_missing_receipt(self):
        with self.assertRaises(WorkbenchError):verify_gate(self.root)
    def test_cli_verify_success(self):
        self.write_records(demo_records());self.assertEqual(main(['gate','--project',str(self.root),'--write']),0)
        self.assertEqual(main(['gate','--project',str(self.root),'--verify']),0)
    def test_no_app_changes(self):
        p=self.root/'app.py';p.write_text('unchanged')
        run_gate(self.root,True);self.assertEqual(p.read_text(),'unchanged')
