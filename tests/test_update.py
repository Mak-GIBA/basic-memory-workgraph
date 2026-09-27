"""Upgrade real shipped templates in isolated existing installations."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import install_schemas as schemas
import update_workgraph as updater
import workgraph_tools as wg

REPO = Path(__file__).resolve().parent.parent


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.codex = self.root / "codex ' with spaces"
        self.memory = self.root / 'registered-not-default-memory'
        self.registry = self.root / 'bm-config/config.json'
        self.registry.parent.mkdir()
        self.registry.write_text(json.dumps({'projects': {'chosen': {'path': str(self.memory), 'mode': 'local'}}}))
        self.codex.mkdir()
        (self.codex/'basic-memory.json').write_text(json.dumps({'unrelated': 4, 'basicMemory': {
            'primaryProject': 'chosen', 'captureEvents': False, 'rememberFolder': 'manual'}}))
        (self.codex/'basic-memory-workgraph').mkdir()
        (self.codex/'basic-memory-workgraph/config.json').write_text(json.dumps({
            'mode': 'off', 'caseMode': 'reusable', 'skillMode': 'auto', 'custom': 9}))
        self.sibling = {'type': 'command', 'command': 'other-hook'}
        (self.codex/'hooks.json').write_text(json.dumps({'hooks': {'Stop': [{'hooks': [self.sibling]}]}}))
        shutil.copytree(REPO/'schema-history/v1', self.memory)
        for path in self.memory.rglob('*.md'):
            meta, body, _ = schemas.split_note(path.read_text())
            meta.update(permalink='chosen/'+path.stem.lower(), extra_metadata={'owner': 'retained'})
            path.write_text('---\n'+wg.yaml.safe_dump(meta,sort_keys=False)+'---\n'+body)
        (self.memory/'rules').mkdir()
        (self.memory/'rules/ordinary.md').write_text('An existing user note.\n')
        self.args = argparse.Namespace(codex_dir=self.codex, basic_memory_config=self.registry,
            project=None, memory_dir=None, mode=None, case_mode=None, skill_mode=None, dry_run=False)

    def test_update_discovers_project_preserves_modes_metadata_and_user_notes(self):
        ordinary = (self.memory/'rules/ordinary.md').read_bytes()
        result = updater.update(self.args)
        self.assertEqual(result['project'], 'chosen')
        self.assertEqual(result['memory_dir'], str(self.memory))
        self.assertEqual(result['preserved'], [])
        self.assertTrue(result['changed'])
        config=json.loads((self.codex/'basic-memory-workgraph/config.json').read_text())
        self.assertEqual(config, {'mode': 'off', 'caseMode': 'reusable', 'skillMode': 'auto', 'custom': 9, 'correctionMode': 'off'})
        for path in (self.memory/'schemas').glob('*.md'):
            meta, _, _ = schemas.split_note(path.read_text())
            self.assertEqual(meta['version'], 3 if path.stem == 'Correction' else 2)
            self.assertEqual(meta['permalink'], 'chosen/'+path.stem.lower())
            self.assertEqual(meta['extra_metadata'], {'owner':'retained'})
        self.assertEqual((self.memory/'rules/ordinary.md').read_bytes(), ordinary)
        self.assertEqual(len(list((self.memory/'schemas').glob('*.bak.*'))), 7)
        bm=json.loads((self.codex/'basic-memory.json').read_text())
        self.assertEqual(bm['unrelated'],4)
        self.assertFalse(bm['basicMemory']['captureEvents'])
        self.assertEqual(bm['basicMemory']['rememberFolder'],'manual')
        hooks=json.loads((self.codex/'hooks.json').read_text())
        self.assertEqual(hooks['hooks']['Stop'][0]['hooks'],[self.sibling])
        first=snapshot(self.root)
        again=updater.update(self.args)
        self.assertEqual(again['changed'],[])
        self.assertEqual(again['preserved'],[])
        self.assertEqual(snapshot(self.root),first)

    def test_dry_run_prepares_real_migration_without_any_files_changed(self):
        before=snapshot(self.root)
        self.args.dry_run=True
        result=updater.update(self.args)
        self.assertTrue(result['changed'])
        self.assertEqual(result['preserved'],[])
        self.assertEqual(snapshot(self.root),before)

    def test_custom_schema_body_and_yaml_comments_are_preserved(self):
        for edit in ('schema','body','comment'):
            with self.subTest(edit=edit):
                target=self.memory/'schemas/Case.md'
                original=target.read_text()
                if edit=='schema':
                    modified=original.replace('task_type: string','task_type: CustomType')
                elif edit=='body':
                    modified=original+'\nUser-specific instructions.\n'
                else:
                    modified=original.replace('entity: Case','entity: Case # user rationale')
                target.write_text(modified)
                result=updater.update(self.args)
                self.assertEqual(target.read_text(),modified)
                self.assertEqual([p['path'] for p in result['preserved']],[str(target)])
                target.write_text(original)

    def test_metadata_formatting_does_not_force_rewrite_of_latest_schema(self):
        latest=(REPO/'templates/schemas/Case.md').read_text()
        meta,body,_=schemas.split_note(latest)
        meta['permalink']='custom/stable-link'
        actual='---\n# preserve this comment\n'+wg.yaml.safe_dump(meta,sort_keys=True)+'---\n'+body
        self.assertEqual(schemas.migrate(actual,latest,[]),actual)

    def test_invalid_config_and_registry_mismatch_fail_before_mutation(self):
        cases=[('config',None),('mode',None),('unknown',None),('mismatch',None),('cloud',None)]
        for case,_ in cases:
            with self.subTest(case=case):
                args=copy.copy(self.args)
                config=self.codex/'hooks.json'
                original=config.read_text()
                registry_original=self.registry.read_text()
                if case=='config':config.write_text('{')
                if case=='mode':args.skill_mode='wrong'
                if case=='unknown':args.project='missing'
                if case=='mismatch':args.memory_dir=self.root/'wrong'
                if case=='cloud':self.registry.write_text(json.dumps({'projects': {'chosen': {'path':str(self.memory),'mode':'cloud'}}}))
                before=snapshot(self.root)
                with self.assertRaises((ValueError,TypeError)):
                    updater.update(args)
                self.assertEqual(snapshot(self.root),before)
                config.write_text(original)
                self.registry.write_text(registry_original)

    def test_explicit_modes_and_old_string_registry_supported(self):
        self.registry.write_text(json.dumps({'projects':{'chosen':str(self.memory)}}))
        self.args.mode='always'
        self.args.case_mode='off'
        self.args.skill_mode='review'
        updater.update(self.args)
        config=json.loads((self.codex/'basic-memory-workgraph/config.json').read_text())
        self.assertEqual((config['mode'],config['caseMode'],config['skillMode']),('always','off','review'))

    def test_missing_installation_missing_directory_and_symlink_fail_closed(self):
        config=self.codex/'basic-memory.json'
        original=config.read_text()
        config.unlink()
        with self.assertRaises(ValueError):updater.update(self.args)
        config.write_text(original)
        moved=self.root/'moved'
        self.memory.rename(moved)
        with self.assertRaises(ValueError):updater.update(self.args)
        self.memory.symlink_to(moved,target_is_directory=True)
        with self.assertRaises(ValueError):updater.update(self.args)

    def test_runtime_failure_restores_changed_files_and_retains_backups(self):
        first=self.root/'first.txt';second=self.root/'second.txt'
        first.write_text('first old');second.write_text('second old')
        real=updater.write_file
        def failing(path,content,stamp):
            if path==second:raise OSError('simulated disk error')
            real(path,content,stamp)
        with patch.object(updater,'write_file',failing),self.assertRaises(OSError):
            updater.apply_update([(first,'first new'),(second,'second new')])
        self.assertEqual(first.read_text(),'first old')
        self.assertEqual(second.read_text(),'second old')
        self.assertEqual(len(list(self.root.glob('first.txt.bak.*'))),1)

    def test_shell_update_never_runs_package_plugin_or_git_commands(self):
        binaries=self.root/'bin';binaries.mkdir()
        for name in ('codex','uv','uvx','curl','bm','git'):
            path=binaries/name
            path.write_text('#!/bin/sh\ntouch "$HOME/unexpected-command"\nexit 99\n')
            path.chmod(0o755)
        env={k:v for k,v in os.environ.items() if k not in ('MEMORY_PROJECT','MEMORY_DIR','BM_AUTO_MODE','BM_CASE_MODE','BM_SKILL_MODE','BM_CORRECTION_MODE')}
        env.update(HOME=str(self.root),CODEX_HOME=str(self.codex),BASIC_MEMORY_CONFIG_DIR=str(self.registry.parent),
                   PATH=str(binaries)+os.pathsep+os.environ['PATH'])
        result=subprocess.run(['bash',str(REPO/'install_basic_memory_workgraph.sh'),'--update','--dry-run'],
                              env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['dry_run'])
        self.assertFalse((self.root/'unexpected-command').exists())
        result=subprocess.run(['bash',str(REPO/'install_basic_memory_workgraph.sh'),'--update'],
                              env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['changed'])
        self.assertFalse((self.root/'unexpected-command').exists())
        target=self.memory/'schemas/Rule.md';target.write_text(target.read_text()+'\nCustom note.\n')
        result=subprocess.run(['bash',str(REPO/'install_basic_memory_workgraph.sh'),'--update'],
                              env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertEqual(json.loads(result.stdout)['preserved'][0]['path'],str(target))

    def test_earliest_graph_revision_migrates_and_unknown_edits_do_not(self):
        old=(REPO/'schema-history/v0/Work-Knowledge-Graph.md').read_text()
        latest=(REPO/'templates/Work-Knowledge-Graph.md').read_text()
        migrated=schemas.migrate(old,latest,[old])
        self.assertIn('packaged_as',migrated)
        self.assertIsNone(schemas.migrate(old+'\nCustom instructions.\n',latest,[old]))

    def test_missing_yaml_fails_update_without_mutation(self):
        before=snapshot(self.root)
        with patch.object(updater,'yaml',None),self.assertRaisesRegex(ValueError,'PyYAML'):
            updater.update(self.args)
        self.assertEqual(snapshot(self.root),before)

    def test_registry_environment_locations(self):
        with patch.dict(os.environ,{'BASIC_MEMORY_CONFIG_DIR':str(self.root/'override'),'XDG_CONFIG_HOME':str(self.root/'xdg')}):
            self.assertEqual(updater.basic_memory_config(),self.root/'override/config.json')
        with patch.dict(os.environ,{'BASIC_MEMORY_CONFIG_DIR':'','XDG_CONFIG_HOME':str(self.root/'xdg')}):
            self.assertEqual(updater.basic_memory_config(),self.root/'xdg/basic-memory/config.json')

    def test_v2_correction_upgrade_keeps_metadata_and_legacy_notes(self):
        target = self.memory / 'schemas/Correction.md'
        metadata, body, _ = schemas.split_note((REPO / 'schema-history/v2/schemas/Correction.md').read_text())
        metadata['permalink'] = 'chosen/schemas/correction'
        metadata['custom_metadata'] = 'keep'
        target.write_text('---\n' + wg.yaml.safe_dump(metadata) + '---\n' + body)
        old_note = self.memory / 'corrections/legacy.md'
        old_note.parent.mkdir()
        old_note.write_text('---\ntitle: Legacy\ntype: correction\n---\n- [instruction] Keep the original order.\n')
        before = old_note.read_bytes()
        self.args.correction_mode = 'scoped'
        self.args.dry_run = True
        snapshot_before = snapshot(self.root)
        preview = updater.update(self.args)
        self.assertIn(str(target), preview['changed'])
        self.assertEqual(snapshot(self.root), snapshot_before)
        self.args.dry_run = False
        self.assertEqual(updater.update(self.args)['preserved'], [])
        current, _, _ = schemas.split_note(target.read_text())
        self.assertEqual(current['version'], 3)
        self.assertEqual(current['permalink'], 'chosen/schemas/correction')
        self.assertEqual(current['custom_metadata'], 'keep')
        self.assertIn('desired_output?', current['schema'])
        self.assertEqual(old_note.read_bytes(), before)
        self.assertEqual(json.loads((self.codex/'basic-memory-workgraph/config.json').read_text())['correctionMode'], 'scoped')
        self.args.correction_mode = None
        self.assertEqual(updater.update(self.args)['changed'], [])

    def test_custom_v2_correction_is_not_replaced(self):
        target = self.memory / 'schemas/Correction.md'
        target.write_text((REPO / 'schema-history/v2/schemas/Correction.md').read_text() + '\nUser custom scope.\n')
        original = target.read_bytes()
        result = updater.update(self.args)
        self.assertEqual([item['path'] for item in result['preserved']], [str(target)])
        self.assertEqual(target.read_bytes(), original)


if __name__=='__main__':
    unittest.main()
