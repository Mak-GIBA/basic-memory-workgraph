from __future__ import annotations
import contextlib, copy, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench.common import *
from workbench import VERSION
from workbench.project_ops import attach,add_item,prompt,register_doc,official_plan,CORE_SKILLS
from workbench.trace import inspect,parse_file,save_report
from workbench.installer import install,uninstall,dependency_plan
from workbench.cli import main
from workbench.approval import create_review, approve


def fake_specify(path:Path):
    code='''#!/usr/bin/env python3
import json,sys,pathlib
args=sys.argv[1:];r=pathlib.Path.cwd()
if args==['version']:print('Specify CLI 1.0.8');sys.exit(0)
if args==['init','--help']:print('--integration --non-interactive --script --ignore-agent-tools --extension');sys.exit(0)
if args and args[0]=='init':
    files={'.specify/templates/spec-template.md':'# mock upstream spec','.specify/memory/constitution.md':'# Mock constitution'}
    names=['constitution','specify','plan','tasks','analyze']
    if '--extension' in args:names+=['bug-assess','bug-fix','bug-test']
    for n in names:files['.agents/skills/speckit-'+n+'/SKILL.md']='---\\nname: speckit-'+n+'\\n---\\nMock official Skill'
    for rel,t in files.items():
        p=r/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
    print('mock init done');sys.exit(0)
if args[:3]==['preset','add','--dev']:
    p=r/'.specify/presets/upstream-trace/preset.yml';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('mock preset');sys.exit(0)
print('unknown mock command',args,file=sys.stderr);sys.exit(2)
'''
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(code);path.chmod(0o755)


def record(key,typ,links=None):
    r={'id':key,'type':typ,'system':'APP','title':'架空の説明 '+key,'status':'approved','basis':'agreed',
       'owner':'架空のレビュー担当','sources':['架空の合意メモ。実際の承認ではない。'],'links':links or {},
       'approval':{'by':'DEMO-REVIEWER','reference':'DEMO fixture','date':'2026-09-21'}}
    if typ in {'goal','story','requirement','quality','interface','data','operation','constraint'}:r['acceptance']='架空の合格条件: 同一操作で予約は一件だけ保存される'
    if typ=='verification':r.update(method='test',expected='予約が1件であること',result='not_run',result_evidence=[])
    return r


def demo_records():
    return [record('APP-GOL-001','goal'),record('APP-NEED-001','need',{'derives_from':['APP-GOL-001']}),
            record('APP-US-001','story',{'derives_from':['APP-NEED-001']}),
            record('APP-FR-001','requirement',{'derives_from':['APP-US-001']}),
            record('APP-DES-001','design',{'satisfies':['APP-FR-001']}),
            record('APP-TEST-001','verification',{'verifies':['APP-FR-001']})]

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='swb-tests-');self.home=Path(self.tmp.name)/'日本語 home';self.home.mkdir()
        self.root=Path(self.tmp.name)/'app project';self.root.mkdir()
        self.bin=self.home/'bin';self.bin.mkdir();fake_specify(self.bin/'specify')
        env={'HOME':str(self.home),'XDG_DATA_HOME':str(self.home/'data'),'XDG_CONFIG_HOME':str(self.home/'config'),
             'SWB_BIN_DIR':str(self.home/'bin'),'SWB_SKILL_DIR':str(self.home/'skills/speckit-workbench'),
             'PATH':str(self.bin)+os.pathsep+os.environ.get('PATH','')}
        self.env=patch.dict(os.environ,env);self.env.start();self.sudo=os.environ.pop('SUDO_USER',None)
        self.out=contextlib.redirect_stdout(io.StringIO());self.out.__enter__()
    def tearDown(self):
        self.out.__exit__(None,None,None);self.env.stop();self.tmp.cleanup()
    legacy_layout=True
    def attach(self,**kw):
        existed=(self.root/'.specify/workbench.json').exists()
        attach(self.root,'APP','existing','docs/upstream',True,**kw)
        if self.legacy_layout and not existed:
            # Explicit old-format fixture: upgrades must continue supporting these projects.
            c=load_project(self.root);c.pop('document_layout')
            for rel in c['required_docs']:(self.root/rel).unlink()
            assets=Path(__file__).resolve().parents[1]/'assets/templates'
            manifest=json.loads((assets/'legacy-manifest.json').read_text())
            c['required_docs']=[]
            for target,template in manifest.items():
                if not target.startswith('@DOCS@/'):continue
                rel=target.replace('@DOCS@','docs/upstream');c['required_docs'].append(rel)
                p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text((assets/template).read_text().replace('@SYSTEM@','APP').replace('@MODE@','existing').replace('@DOCS@','docs/upstream'))
            (self.root/'.specify/workbench.json').write_text(json_text(c))
    def write_records(self,records):
        # Complete the illustrative narrative documents so ready tests target item coverage.
        for rel in load_project(self.root).get('required_docs',[]):
            p=self.root/rel
            p.write_text(p.read_text().replace('TBD','架空例: 項目説明済み'))
        p=self.root/'docs/upstream/requirements/demo.md';p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('\n'.join('## '+str(r.get('id'))+'\n\n```upstream\n'+json_text(r)+'```\n\n架空例。\n' for r in records))
        # Bind legacy-looking demo approvals to an actual review snapshot so ready tests
        # exercise the hash-bound approval implementation. Invalid-approval tests opt out
        # automatically by removing approval metadata or changing status from approved.
        if records and all(r.get('status')=='approved' and isinstance(r.get('approval'),dict) for r in records):
            current=inspect(self.root,'draft')
            allowed={'LEGACY_APPROVAL_UNBOUND','STALE_APPROVAL','STALE_DEPENDENCY_APPROVAL','APPROVAL_METADATA_MISMATCH','APPROVAL_INVALID'}
            blocking=[f for f in current['findings'] if f['severity']=='error' and f['code'] not in allowed]
            if not blocking:
                packet=create_review(self.root,'all',True)
                approve(self.root,packet['review_id'],[], 'DEMO-REVIEWER','DEMO fixture',True,all_reviewed=True)
    def codes(self,phase='ready'):return {x['code'] for x in inspect(self.root,phase)['findings']}

class InstallTests(Base):
    def test_dry_run_no_writes(self):
        install(False);self.assertFalse(locations()['config'].exists());self.assertFalse(locations()['data'].exists())
    def test_install_global(self):
        install(True);self.assertTrue((locations()['skill']/'SKILL.md').exists());self.assertTrue((locations()['bin']/'speckit-workbench').exists())
    def test_idempotent_install(self):
        install(True);a=(locations()['skill']/'SKILL.md').stat().st_mtime_ns;install(True);self.assertEqual(a,(locations()['skill']/'SKILL.md').stat().st_mtime_ns)
    def test_edited_skill_preserved(self):
        install(True);p=locations()['skill']/'SKILL.md';p.write_text('my edits')
        with self.assertRaises(WorkbenchError):install(True,update=True)
        self.assertEqual(p.read_text(),'my edits')
    def test_existing_foreign_skill_blocks(self):
        p=locations()['skill']/'SKILL.md';p.parent.mkdir(parents=True);p.write_text('someone else')
        with self.assertRaises(WorkbenchError):install(True)
    def test_global_launcher_runs(self):
        install(True);r=command([str(locations()['bin']/'speckit-workbench'),'--version']);self.assertEqual(r.returncode,0);self.assertEqual(r.stdout.strip(),VERSION)
    def test_dependency_reused(self):self.assertEqual(dependency_plan(False)['status'],'reuse')
    def test_skip_dependency(self):self.assertEqual(dependency_plan(True)['status'],'skipped')
    def test_dependency_failure(self):
        p=self.bin/'specify';p.write_text('#!/bin/sh\nexit 1\n')
        with self.assertRaises(WorkbenchError):dependency_plan(False)
    def test_no_ecc_hooks_agents_config_changes(self):
        protected=[]
        for rel in ['.codex/hooks.json','.codex/config.toml','.codex/AGENTS.md','knowledge/memory.md']:
            p=self.home/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('keep me');protected.append(p)
        install(True)
        self.assertTrue(all(p.read_text()=='keep me' for p in protected))
    def test_uninstall_keeps_specify(self):
        install(True);uninstall(True);self.assertTrue((self.bin/'specify').exists());self.assertFalse((locations()['skill']/'SKILL.md').exists())
    def test_uninstall_keeps_modified(self):
        install(True);p=locations()['skill']/'SKILL.md';p.write_text('changed');uninstall(True);self.assertEqual(p.read_text(),'changed')
    def test_uninstall_dry(self):
        install(True);uninstall(False);self.assertTrue((locations()['skill']/'SKILL.md').exists())
    def test_relative_xdg_refused(self):
        with patch.dict(os.environ,{'XDG_DATA_HOME':'relative'}):
            with self.assertRaises(WorkbenchError):locations()
    def test_symlink_refused(self):
        target=self.home/'elsewhere';target.mkdir();locations()['skill'].parent.mkdir(parents=True)
        locations()['skill'].symlink_to(target,target_is_directory=True)
        with self.assertRaises(WorkbenchError):install(True)
    def test_tampered_manifest_path_refused(self):
        install(True);p=locations()['config']/'install.json';m=read_json(p);m['managed'][str(locations()['data']/'releases/../../../victim')]='fake';p.write_text(json_text(m))
        with self.assertRaises(WorkbenchError):uninstall(True)

class ProjectTests(Base):
    def test_attach_dry_no_changes(self):
        attach(self.root,'APP','existing','docs/upstream',False);self.assertEqual(list(self.root.iterdir()),[])
    def test_official_attach_mock(self):
        self.attach();self.assertTrue((self.root/'.agents/skills/speckit-bug-test/SKILL.md').exists());self.assertTrue((self.root/'.specify/presets/upstream-trace/preset.yml').exists())
    def test_docs_only(self):
        self.attach(docs_only=True);self.assertFalse((self.root/'.agents').exists());self.assertTrue((self.root/'docs/upstream/README.md').exists())
    def test_repeat_keeps_authored_docs(self):
        self.attach();p=self.root/'docs/upstream/product/vision.md';p.write_text('authored');self.attach();self.assertEqual(p.read_text(),'authored')
    def test_conflict_no_partial_apply(self):
        p=self.root/'docs/upstream/requirements.md';p.parent.mkdir(parents=True);p.write_text('old')
        with self.assertRaises(WorkbenchError):self.attach()
        self.assertEqual(p.read_text(),'old');self.assertFalse((self.root/'.agents').exists())
    def test_no_application_changes(self):
        p=self.root/'app.py';p.write_text('keep');h=self.root/'.codex/hooks.json';h.parent.mkdir();h.write_text('{"keep":1}')
        self.attach();self.assertEqual(p.read_text(),'keep');self.assertEqual(h.read_text(),'{"keep":1}')
    def test_existing_spec_reused(self):
        self.attach();p=self.root/'.specify/memory/constitution.md';p.write_text('human')
        (self.root/'.specify/workbench.json').unlink()
        # Docs-only retained: official_plan itself must not modify existing framework.
        files,_=official_plan(self.root,True,True);self.assertEqual(files,{});self.assertEqual(p.read_text(),'human')
    def test_partial_spec_fail_closed(self):
        p=self.root/'.specify/templates';p.mkdir(parents=True)
        with self.assertRaises(WorkbenchError):self.attach()
    def test_invalid_system(self):
        with self.assertRaises(WorkbenchError):attach(self.root,'../bad','existing','docs/upstream',True)
    def test_system_switch_refused(self):
        self.attach()
        with self.assertRaises(WorkbenchError):attach(self.root,'OTHER','new','docs/upstream',True)
    def test_traversal_refused(self):
        with self.assertRaises(WorkbenchError):attach(self.root,'APP','existing','../outside',True)
    def test_parent_file_refused(self):
        (self.root/'docs').write_text('file')
        with self.assertRaises(WorkbenchError):self.attach()
    def test_symlink_docs_refused(self):
        target=self.home/'documents';target.mkdir();(self.root/'docs').symlink_to(target)
        with self.assertRaises(WorkbenchError):self.attach()
    def test_all_modes_prompt(self):
        self.attach()
        for mode in ['new','existing','change','bug','refactor']:
            text=prompt(self.root,mode);self.assertIn('$speckit-workbench',text);self.assertIn('承認',text)
    def test_create_item(self):
        self.attach();add_item(self.root,'goal','APP-GOL-001','目的',[],None,True);self.assertEqual(len(inspect(self.root)['items']),1)
    def test_item_duplicate(self):
        self.attach();add_item(self.root,'goal','APP-GOL-001','目的',[],None,True)
        with self.assertRaises(WorkbenchError):add_item(self.root,'goal','APP-GOL-001','目的',[],None,True)
    def test_item_dry_run(self):
        self.attach();add_item(self.root,'goal','APP-GOL-001','目的',[],None,False);self.assertEqual(inspect(self.root)['items'],[])
    def test_item_parent_must_exist(self):
        self.attach()
        with self.assertRaises(WorkbenchError):add_item(self.root,'need','APP-NEED-001','需要',['APP-GOL-404'],None,True)
    def test_item_target_restricted(self):
        self.attach()
        with self.assertRaises(WorkbenchError):add_item(self.root,'goal','APP-GOL-001','目的',[],'AGENTS.md',True)
    def test_item_append_preserves(self):
        self.attach();p=self.root/'specs/a/spec.md';p.parent.mkdir(parents=True);p.write_text('original\n')
        add_item(self.root,'goal','APP-GOL-001','目的',[],'specs/a/spec.md',True);self.assertTrue(p.read_text().startswith('original\n'))
        self.assertTrue(list((self.root/'docs/upstream/.backups').glob('*.bak')))
    def test_register_document(self):
        self.attach();p=self.root/'old.md';p.write_text('old');register_doc(self.root,'old.md',True);self.assertIn('old.md',inspect(self.root)['documents'])

class TraceTests(Base):
    def setUp(self):super().setUp();self.attach(docs_only=True)
    def test_empty_not_pass(self):self.assertIn('NO_ITEMS',self.codes())
    def test_complete_fixture_ready(self):
        self.write_records(demo_records());self.assertEqual(inspect(self.root,'ready')['verdict'],'STRUCTURE_OK')
    def test_unfilled_documents_block_ready(self):
        self.write_records(demo_records());p=self.root/'docs/upstream/product/vision.md';p.write_text('TBD')
        self.assertIn('DOCUMENT_TBD',self.codes())
    def test_required_document_missing(self):
        self.write_records(demo_records());(self.root/'docs/upstream/product/vision.md').unlink()
        self.assertIn('MISSING_DOCUMENT',self.codes())
    def test_reverse_links(self):
        self.write_records(demo_records());r=inspect(self.root);self.assertIn({'id':'APP-DES-001','relation':'satisfies'},r['incoming']['APP-FR-001'])
    def test_broken_reference(self):
        rows=demo_records();rows[-1]['links']['verifies']=['APP-FR-999'];self.write_records(rows);self.assertIn('BROKEN_REFERENCE',self.codes())
    def test_duplicate_id(self):
        rows=demo_records();self.write_records(rows+[rows[0]]);self.assertIn('DUPLICATE_ID',self.codes())
    def test_wrong_system(self):
        rows=demo_records();rows[0]['system']='OTHER';self.write_records(rows);self.assertIn('WRONG_SYSTEM',self.codes())
    def test_no_approval(self):
        rows=demo_records();rows[0].pop('approval');self.write_records(rows);self.assertIn('LEGACY_APPROVAL_UNBOUND',self.codes())
    def test_no_source(self):
        rows=demo_records();rows[0]['sources']=[];self.write_records(rows);self.assertIn('NO_SOURCE',self.codes())
    def test_no_design(self):
        self.write_records(demo_records()[:4]+demo_records()[5:]);self.assertIn('NO_DESIGN',self.codes())
    def test_no_verification(self):
        self.write_records(demo_records()[:-1]);self.assertIn('NO_VERIFICATION',self.codes())
    def test_unapproved(self):
        rows=demo_records();rows[0]['status']='draft';self.write_records(rows);self.assertIn('NOT_APPROVED',self.codes())
    def test_placeholder_acceptance(self):
        rows=demo_records();rows[3]['acceptance']='TBD';self.write_records(rows);self.assertIn('NO_ACCEPTANCE',self.codes())
    def test_observation_not_requirement(self):
        rows=demo_records();rows[3]['basis']='observed';self.write_records(rows);self.assertIn('ASIS_NOT_REQUIREMENT',self.codes())
    def test_claimed_pass_without_log(self):
        rows=demo_records();rows[-1]['result']='pass';self.write_records(rows);self.assertIn('NO_RESULT_EVIDENCE',self.codes())
    def test_not_run_allowed_for_plan(self):
        self.write_records(demo_records());self.assertEqual(inspect(self.root,'ready')['errors'],0)
    def test_draft_missing_coverage_warning(self):
        self.write_records(demo_records()[:4]);r=inspect(self.root,'draft');self.assertEqual(r['errors'],0);self.assertGreater(r['warnings'],0)
    def test_cycle(self):
        rows=demo_records();rows[0]['links']={'derives_from':['APP-NEED-001']};self.write_records(rows);self.assertIn('DERIVATION_CYCLE',self.codes())
    def test_json_error(self):
        p=self.root/'docs/upstream/bad.md';p.write_text('```upstream\n{bad}\n```');self.assertIn('INVALID_JSON',self.codes())
    def test_unclosed_block(self):
        p=self.root/'docs/upstream/bad.md';p.write_text('```upstream\n{}');self.assertIn('UNCLOSED_BLOCK',self.codes())
    def test_bad_links(self):
        rows=demo_records();rows[0]['links']='bad';self.write_records(rows);self.assertIn('BAD_LINKS',self.codes())
    def test_bad_scalar(self):
        rows=demo_records();rows[0]['type']=[];self.write_records(rows);self.assertIn('BAD_FIELD',self.codes())
    def test_symlink_scan(self):
        p=self.root/'docs/upstream/link.md';p.symlink_to(self.home/'private.md')
        with self.assertRaises(WorkbenchError):inspect(self.root)
    def test_trace_write(self):
        self.write_records(demo_records());r=inspect(self.root);save_report(self.root,r);save_report(self.root,r)
        self.assertTrue((self.root/'docs/upstream/traceability/matrix.md').exists())
    def test_trace_preserves_handwritten(self):
        self.write_records(demo_records());p=self.root/'docs/upstream/traceability/matrix.md';p.parent.mkdir();p.write_text('human')
        with self.assertRaises(WorkbenchError):save_report(self.root,inspect(self.root))
        self.assertEqual(p.read_text(),'human')
    def test_cli_error_exit(self):self.assertEqual(main(['check','--project',str(self.root)]),1)
    def test_cli_ready_exit(self):
        self.write_records(demo_records());self.assertEqual(main(['check','--project',str(self.root),'--phase','ready']),0)

if __name__=='__main__':unittest.main(verbosity=2)
