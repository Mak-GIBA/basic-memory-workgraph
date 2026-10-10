from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from command_assets import assets, COMMANDS, LEGACY_COMMAND_NAMES
import build_installers as bi


class SingleEntryInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'skills'
        self.g={'__name__':'legacy_installer_fixture'}
        exec(compile((ROOT/'tests/fixtures/legacy_installer_fixture.py').read_text(),'<legacy-core-fixture>','exec'),self.g)
        self.g['VERSION']='2.3.1'
        exec(compile((ROOT/'installer_commands.py').read_text(),'<single-entry-migration>','exec'),self.g)
        self.decoded={'SKILL.md':b'---\nname: design-research\ndescription: Research workflow\n---\nCore fixture\n',**assets()}
        self.payload={'schema_version':1,'name':'design-research','version':'2.3.1','files':{
            rel:{'sha256':hashlib.sha256(raw).hexdigest(),'mode':0o644} for rel,raw in self.decoded.items()}}

    def perform(self,**kw):return self.g['perform'](self.root,self.payload,self.decoded,**kw)
    def live(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def make_legacy(self,name=LEGACY_COMMAND_NAMES[0],edited=False,unmanaged=False):
        p=self.root/name;p.mkdir(parents=True,exist_ok=True)
        (p/'SKILL.md').write_text('legacy',encoding='utf-8')
        if not unmanaged:
            meta={'owner':self.g['OWNER']+'/commands','name':name,'version':'2.3.0',
                  'schema_version':1,'files':{'SKILL.md':hashlib.sha256(b'legacy').hexdigest()}}
            (p/'.design-research-command.json').write_text(json.dumps(meta),encoding='utf-8')
        if edited:
            (p/'SKILL.md').write_text('edited by user',encoding='utf-8')
        return p

    def test_install_publishes_only_the_main_skill(self):
        self.assertEqual(COMMANDS,{})
        self.assertEqual(assets(),{})
        r=self.perform();self.assertEqual(r['action'],'install')
        self.assertTrue((self.root/'design-research/SKILL.md').is_file())
        self.assertEqual(r['codex_entries'],['$design-research'])
        self.assertFalse(any((self.root/n).exists() for n in LEGACY_COMMAND_NAMES))

    def test_dry_run_has_no_destination(self):
        r=self.perform(dry_run=True)
        self.assertTrue(r['dry_run']);self.assertFalse(self.root.exists())

    def test_reinstall_is_idempotent(self):
        self.perform();before=self.live();r=self.perform()
        self.assertEqual(r['action'],'skip');self.assertEqual(before,self.live())

    def test_unmodified_owned_alias_retired_with_backup(self):
        self.perform();name=LEGACY_COMMAND_NAMES[0];self.make_legacy(name)
        r=self.perform(update=True)
        self.assertEqual(r['action'],'update')
        self.assertEqual(r['legacy_shortcuts_to_retire'],[name])
        self.assertFalse((self.root/name).exists())
        self.assertEqual((Path(r['legacy_backup'])/name/'SKILL.md').read_text(),'legacy')

    def test_modified_alias_preserved_without_force(self):
        self.perform();p=self.make_legacy(edited=True)
        r=self.perform(update=True)
        self.assertEqual(p.joinpath('SKILL.md').read_text(),'edited by user')
        self.assertIn(p.name,r['legacy_shortcuts_preserved'])

    def test_unmanaged_alias_preserved(self):
        self.perform();p=self.make_legacy(unmanaged=True)
        r=self.perform(update=True)
        self.assertEqual(p.joinpath('SKILL.md').read_text(),'legacy')
        self.assertIn(p.name,r['legacy_shortcuts_preserved'])

    def test_failed_core_update_rolls_back_shortcut(self):
        self.perform();p=self.make_legacy();before=self.live()
        def fail_core(*a,**kw):
            if not kw.get('dry_run'):raise self.g['InstallError']('simulated core failure')
            return self.g['_original_core_before_test'](*a,**kw)
        self.g['_original_core_before_test']=self.g['_perform_core']
        self.g['_perform_core']=fail_core
        with self.assertRaises(self.g['InstallError']):self.perform(update=True)
        self.assertEqual(before,self.live());self.assertTrue(p.exists())
        self.assertFalse((self.root/'.design-research-command-install.lock').exists())

    def test_edited_core_refuses_update_preserving_shortcut(self):
        self.perform();p=self.make_legacy()
        (self.root/'design-research/SKILL.md').write_text('edited main skill')
        before=self.live()
        with self.assertRaises(self.g['InstallError']):self.perform(update=True)
        self.assertEqual(before,self.live())

    def test_legacy_not_removed_if_no_core_version_upgrade(self):
        self.perform();p=self.make_legacy()
        self.g['VERSION']='2.3.2'
        r=self.perform()
        self.assertEqual(r['action'],'skip')
        self.assertTrue(p.exists())
        self.assertFalse(r['legacy_shortcuts_to_retire'])

    def test_legacy_symlink_refused(self):
        self.root.mkdir();out=Path(self.tmp.name)/'out';out.mkdir()
        (self.root/LEGACY_COMMAND_NAMES[0]).symlink_to(out,target_is_directory=True)
        with self.assertRaises(self.g['InstallError']):self.perform()

    def test_uninstall_removes_only_owned_core_and_shortcuts(self):
        self.perform();p=self.make_legacy()
        other=self.root/'unrelated-skill';other.mkdir();(other/'SKILL.md').write_text('keep')
        r=self.perform(uninstall=True)
        self.assertEqual(r['action'],'uninstall')
        self.assertFalse((self.root/'design-research').exists())
        self.assertFalse(p.exists())
        self.assertEqual((other/'SKILL.md').read_text(),'keep')

    def test_no_global_config_mutation(self):
        self.perform()
        self.assertFalse((Path(self.tmp.name)/'.codex/config.toml').exists())
        self.assertFalse((self.root/'AGENTS.md').exists())


class PinnedSourceTests(unittest.TestCase):
    def test_offline_requires_original_bases(self):
        with self.assertRaises(ValueError):bi.obtain_upstream(None,True)
    def test_wrong_upstream_blob_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'base.sh';p.write_text('not a base')
            with self.assertRaises(ValueError):bi.obtain_upstream(p,True)
    def test_wrong_design_research_blob_refused(self):
        with self.assertRaises(ValueError):bi.unpack_base(b'not a base',Path('/does-not-exist'))
    def test_unsafe_archive_paths_rejected(self):
        for name in ('../file','/absolute','x/../a','a\\b','C:/x','a//b'):
            with self.subTest(name=name),self.assertRaises(ValueError):bi.safe_relative(name)

if __name__=='__main__':unittest.main()
