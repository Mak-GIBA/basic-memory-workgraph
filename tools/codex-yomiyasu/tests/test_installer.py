"""Offline tests. The upstream fixtures are NOT nanaism's real implementation."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

if 'I' not in globals():
    spec = importlib.util.spec_from_file_location('yomi_installer', Path(__file__).resolve().parents[1]/'installer.py')
    I = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = I
    spec.loader.exec_module(I)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)/"日本語 home ' $()"; self.home.mkdir()
        self.env = mock.patch.dict(os.environ, {'HOME': str(self.home), 'CODEX_HOME': str(self.home/'custom-codex')})
        self.env.start(); self.addCleanup(self.env.stop)
        self.target = self.home/'.agents/skills/yomiyasu'
        self.source = self.home/'source'; self.source.mkdir()
        self.fake = {name: ('fixture ' + name + '\n').encode() for name in I.PINS}
        self.fake['SKILL.md'] = b'---\nname: yomiyasu\n---\nfixture only\n'
        self.fake['LICENSE'] = b'MIT License\nTest fixture only\n'
        self.fake['scripts/yomiyasu_lint.py'] = b'import json, sys\nprint(json.dumps({"score":80,"findings":[]}))\nsys.exit(1 if "--strict" in sys.argv else 0)\n'
        self.fake['scripts/yomiyasu_diff.py'] = b'import json, sys\nprint(json.dumps({"markers":[], "received":sys.argv[1:]}))\n'
        for name, data in self.fake.items():
            p = self.source/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        self.pin_patch = mock.patch.object(I, 'PINS', {k: (I.blob_sha(v), len(v)) for k,v in self.fake.items()})
        self.pin_patch.start(); self.addCleanup(self.pin_patch.stop)

    def put(self, **kw):
        return I.install(self.target, apply=True, source=self.source, **kw)

    def files(self):
        return I.inventory(self.target)

    def check_module(self):
        s = importlib.util.spec_from_file_location('yomi_check_test', self.target/'scripts/check.py')
        m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

    def test_dry_run_no_directories_or_download(self):
        with mock.patch.object(I, 'download', side_effect=AssertionError('network')):
            r = I.install(self.target)
        self.assertFalse(r['applied']); self.assertFalse(self.target.parent.exists())

    def test_install_offline_source(self):
        r = self.put(); self.assertTrue(r['applied']); self.assertEqual(r['mode'], 'auto')
        self.assertEqual((self.target/'upstream/SKILL.upstream.md').read_bytes(), self.fake['SKILL.md'])
        self.assertFalse((self.target/'upstream/SKILL.md').exists())

    def test_just_one_discoverable_skill(self):
        self.put(); self.assertEqual(len(list(self.target.rglob('SKILL.md'))), 1)

    def test_no_pip_npm_or_other_settings(self):
        protected = [self.home/'custom-codex/config.toml', self.home/'custom-codex/hooks.json',
                     self.home/'custom-codex/AGENTS.md', self.home/'knowledge/note.md', self.home/'.bashrc',
                     self.home/'.agents/skills/github-project-director/SKILL.md',
                     self.home/'.agents/skills/office-workbench/SKILL.md']
        for p in protected:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text('keep\n')
        before = {p:(p.read_bytes(), p.stat().st_mtime_ns) for p in protected}
        self.put()
        self.assertEqual(before, {p:(p.read_bytes(), p.stat().st_mtime_ns) for p in protected})

    def test_idempotent_skips_without_source_or_network(self):
        self.put(); before = self.files(); mtimes = {p: p.stat().st_mtime_ns for p in self.target.rglob('*') if p.is_file()}
        with mock.patch.object(I, 'download', side_effect=AssertionError('network')):
            r = I.install(self.target, apply=True)
        self.assertEqual(r['action'], 'skip'); self.assertEqual(before, self.files())
        self.assertEqual(mtimes, {p:p.stat().st_mtime_ns for p in mtimes})

    def test_mode_explicit(self):
        self.put(mode='explicit'); self.assertIn('allow_implicit_invocation: false', (self.target/'agents/openai.yaml').read_text())

    def test_auto_mode_enables_natural_invocation_and_scoped_description(self):
        self.put()
        skill=(self.target/'SKILL.md').read_text()
        agent=(self.target/'agents/openai.yaml').read_text()
        self.assertIn('日本語の文章そのものが成果物', skill)
        self.assertIn('Issue/PR', skill)
        self.assertIn('事実回答だけ', skill)
        self.assertIn('allow_implicit_invocation: true', agent)
        self.assertIn('CODEX', agent)

    def test_check_update_is_read_only(self):
        self.put(); before=self.files()
        latest={"tag":"v1.0.4","commit":I.COMMIT,"published_at":"2026-10-02T15:10:34Z","release_url":"x","files":{}}
        with mock.patch.object(I,'latest_release_meta',return_value=latest):
            r=I.check_update(self.target)
        self.assertFalse(r['update_available'])
        self.assertEqual(before,self.files())

    def test_explicit_update_refreshes_upstream_and_backs_up(self):
        self.put(); before=self.files()
        future={"tag":"v1.1.0","commit":"f"*40,"published_at":"2026-11-01T00:00:00Z","release_url":"x","files":{}}
        changed=dict(self.fake); changed['SKILL.md']=b'---\nname: yomiyasu\n---\nnew upstream\n'
        dynamic={I.map_upstream(k):v for k,v in changed.items()}
        with mock.patch.object(I,'latest_release_meta',return_value=future), mock.patch.object(I,'fetch_release_upstream',return_value=dynamic):
            r=I.install(self.target,apply=True,update=True)
        self.assertTrue(r['applied']); self.assertEqual(r['upstream_tag'],'v1.1.0')
        self.assertEqual((self.target/'upstream/SKILL.upstream.md').read_bytes(), changed['SKILL.md'])
        self.assertTrue(Path(r['backup']).exists())
        self.assertNotEqual(before,self.files())

    def test_mode_preserved(self):
        self.put(mode='explicit'); r = I.install(self.target, apply=True); self.assertEqual(r['mode'], 'explicit')

    def test_mode_change_needs_force(self):
        self.put()
        with self.assertRaises(I.InstallError): self.put(mode='explicit')

    def test_mode_change_force_uses_cached_upstream(self):
        self.put()
        with mock.patch.object(I, 'download', side_effect=AssertionError('network')):
            r = I.install(self.target, mode='explicit', force=True, apply=True)
        self.assertFalse(r['network']); self.assertTrue(Path(r['backup']).exists())
        self.assertIn('false', (self.target/'agents/openai.yaml').read_text())

    def test_update_backup_and_preserve_extras(self):
        self.put(); (self.target/'notes.txt').write_text('my note')
        before = self.files(); r = self.put(force=True)
        self.assertEqual((self.target/'notes.txt').read_text(), 'my note')
        with zipfile.ZipFile(r['backup']) as z: self.assertEqual(z.read('notes.txt'), before['notes.txt'])

    def test_edited_managed_protected_even_force(self):
        self.put(); (self.target/'SKILL.md').write_text('edited'); before = self.files()
        with self.assertRaises(I.InstallError): self.put(force=True)
        self.assertEqual(before, self.files())

    def test_missing_managed_protected(self):
        self.put(); (self.target/'upstream/LICENSE').unlink()
        with self.assertRaises(I.InstallError): self.put(force=True)

    def test_unknown_same_name_not_adopted(self):
        self.target.mkdir(parents=True); (self.target/'SKILL.md').write_text('other')
        with self.assertRaises(I.InstallError): self.put(force=True)
        self.assertEqual((self.target/'SKILL.md').read_text(), 'other')

    def test_corrupt_manifest(self):
        self.put(); (self.target/I.MANIFEST).write_text('{')
        with self.assertRaises(I.InstallError): self.put(force=True)

    def test_traversal_manifest_refused(self):
        self.put(); p=self.target/I.MANIFEST; m=json.loads(p.read_text()); m['files']['../x']='a'*64; p.write_text(json.dumps(m))
        with self.assertRaises(I.InstallError): self.put(force=True)

    def test_symlink_destination(self):
        other=self.home/'elsewhere'; other.mkdir(); self.target.parent.mkdir(parents=True); self.target.symlink_to(other)
        with self.assertRaises(I.InstallError): self.put()
        self.assertEqual(list(other.iterdir()), [])

    def test_symlink_parent(self):
        other=self.home/'elsewhere'; other.mkdir(); self.target.parent.parent.mkdir(parents=True); self.target.parent.symlink_to(other)
        with self.assertRaises(I.InstallError): self.put()

    def test_symlink_inside_installation(self):
        self.put(); (self.target/'outside').symlink_to(self.home/'secret')
        with self.assertRaises(I.InstallError): self.put(force=True)

    def test_symlink_source(self):
        p=self.source/'LICENSE'; p.unlink(); alt=self.home/'license'; alt.write_bytes(self.fake['LICENSE']); p.symlink_to(alt)
        with self.assertRaises(I.InstallError): self.put()
        self.assertFalse(self.target.exists())

    def test_source_checksum_mismatch_before_writes(self):
        self.put(); before=self.files(); (self.source/'LICENSE').write_bytes(b'bad')
        with self.assertRaises(I.InstallError): self.put(force=True)
        self.assertEqual(before, self.files())

    def test_download_failure_preserves_existing(self):
        self.put(); before=self.files()
        future = {"tag":"v9.9.9","commit":"f"*40,"published_at":"2099-01-01T00:00:00Z","release_url":"https://github.com/nanaism/yomiyasu/releases/tag/v9.9.9","files":{}}
        with mock.patch.object(I, 'latest_release_meta', return_value=future), mock.patch.object(I, 'fetch_release_upstream', side_effect=I.InstallError('offline')):
            with self.assertRaises(I.InstallError): I.install(self.target, apply=True, update=True)
        self.assertEqual(before, self.files())

    def test_raw_download_exact_pins(self):
        def downloader(url): return self.fake[url.split(I.COMMIT+'/')[1]]
        with mock.patch.object(I, 'download', side_effect=downloader) as d:
            r = I.fetch_upstream()
        self.assertEqual(d.call_count, len(self.fake)); self.assertEqual(r['upstream/LICENSE'], self.fake['LICENSE'])

    def test_api_fallback_exact_pins(self):
        def downloader(url):
            if 'raw.githubusercontent' in url: raise urllib.error.URLError('raw unavailable')
            name=url.split('/contents/')[1].split('?')[0]
            return json.dumps({'encoding':'base64','sha':I.PINS[name][0], 'content':I.base64.b64encode(self.fake[name]).decode()}).encode()
        with mock.patch.object(I, 'download', side_effect=downloader):
            self.assertEqual(I.fetch_upstream()['upstream/LICENSE'], self.fake['LICENSE'])

    def test_api_bad_sha_refused(self):
        def downloader(url):
            if 'raw.githubusercontent' in url: raise urllib.error.URLError('no')
            return b'{"encoding":"base64","sha":"wrong","content":"YQ=="}'
        with mock.patch.object(I, 'download', side_effect=downloader):
            with self.assertRaises(I.InstallError): I.fetch_upstream()

    def test_download_mismatching_content_refused(self):
        with mock.patch.object(I, 'download', return_value=b'evil'):
            with self.assertRaises(I.InstallError): I.fetch_upstream()

    def test_source_python_syntax(self):
        name='scripts/yomiyasu_lint.py'; bad=b'def :\n'; (self.source/name).write_bytes(bad)
        I.PINS[name] = (I.blob_sha(bad), len(bad))
        with self.assertRaises(I.InstallError): I.fetch_upstream(self.source)

    def test_lock_prevents_parallel_update(self):
        self.put(); lock=self.target.parent/'.yomiyasu-installer.lock'; lock.write_text('another')
        with self.assertRaises(I.InstallError): self.put(force=True)
        self.assertEqual(lock.read_text(), 'another')

    def test_stage_rename_failure_rolls_back(self):
        self.put(); before=self.files(); orig=I.os.replace
        def fail(src,dst):
            if Path(src).name.startswith('.yomiyasu-stage-'): raise OSError('simulated rename failure')
            return orig(src,dst)
        with mock.patch.object(I.os, 'replace', side_effect=fail):
            with self.assertRaises(OSError): self.put(force=True)
        self.assertEqual(before, self.files())
        self.assertFalse((self.target.parent/'.yomiyasu-installer.lock').exists())

    def test_concurrent_edit_detected(self):
        self.put(); original=I.bundle
        def side(*args):
            data=original(*args); (self.target/'SKILL.md').write_text('concurrent'); return data
        with mock.patch.object(I, 'bundle', side_effect=side):
            with self.assertRaises(I.InstallError): self.put(force=True)
        self.assertEqual((self.target/'SKILL.md').read_text(), 'concurrent')

    def test_duplicate_codex_home_blocks_install(self):
        other=Path(os.environ['CODEX_HOME'])/'skills/yomiyasu'; other.mkdir(parents=True); (other/'SKILL.md').write_text('other')
        with self.assertRaises(I.InstallError): self.put()
        self.assertFalse(self.target.exists())

    def test_duplicate_project_blocks_install(self):
        project=self.home/'proj'; p=project/'.agents/skills/yomiyasu'; p.mkdir(parents=True); (p/'SKILL.md').write_text('other')
        with self.assertRaises(I.InstallError): self.put(project=project)

    def test_other_styler_warning_not_removed(self):
        p=self.target.parent/'natural-japanese'; p.mkdir(parents=True); (p/'SKILL.md').write_text('other')
        r=self.put(); self.assertIn(str(p),r['conflicts']['other_style_skills']); self.assertEqual((p/'SKILL.md').read_text(),'other')

    def test_doctor_reads_no_write(self):
        self.put(); before=self.files(); r,c=I.doctor(self.target,None)
        self.assertEqual(c,0); self.assertEqual(before,self.files()); self.assertEqual(r['status'],'READY_FILES')

    def test_doctor_detects_upstream_modification(self):
        self.put(); (self.target/'upstream/LICENSE').write_text('bad'); r,c=I.doctor(self.target,None)
        self.assertEqual(c,2); self.assertEqual(r['status'],'DAMAGED_OR_EDITED'); self.assertTrue(r['edited'])

    def test_doctor_missing(self):
        r,c=I.doctor(self.target,None); self.assertEqual(c,2); self.assertEqual(r['status'],'NOT_READY')

    def test_uninstall_dry_then_apply(self):
        self.put(); r=I.uninstall(self.target,False); self.assertFalse(r['applied']); self.assertTrue(self.target.exists())
        r=I.uninstall(self.target,True); self.assertFalse(self.target.exists()); self.assertTrue(Path(r['backup']).exists())
        self.assertEqual(I.uninstall(self.target,True)['action'],'absent')

    def test_uninstall_protects_edits(self):
        self.put(); (self.target/'SKILL.md').write_text('edited')
        with self.assertRaises(I.InstallError): I.uninstall(self.target,True)

    def test_uninstall_protects_extras(self):
        self.put(); (self.target/'notes.txt').write_text('keep')
        with self.assertRaises(I.InstallError): I.uninstall(self.target,True)

    def test_invalid_arguments_are_read_only(self):
        with contextlib.redirect_stdout(io.StringIO()): code=I.main(['--doctor','--apply'])
        self.assertEqual(code,2); self.assertFalse(self.target.exists())

    def test_extract_empty_only(self):
        dest=self.home/'extracted'; I.extract(dest); self.assertTrue((dest/'SKILL.md').exists())
        self.assertTrue((dest/'upstream-pin.json').exists())
        with self.assertRaises(I.InstallError): I.extract(dest)

    def test_custom_skills_dir_not_codex_settings(self):
        target=self.home/'custom skills/yomiyasu'; I.install(target,apply=True,source=self.source)
        self.assertTrue((target/'SKILL.md').exists()); self.assertFalse((self.home/'custom-codex').exists())

    def test_check_lint_uses_upstream_fixture(self):
        self.put(); p=self.home/'記事.md'; p.write_text('日本語のテストです。')
        m=self.check_module()
        with contextlib.redirect_stdout(io.StringIO()) as o: code=m.main(['lint',str(p)])
        data=json.loads(o.getvalue()); self.assertEqual(code,0); self.assertFalse(data['meaning_preservation_verified'])

    def test_check_strict_returncode(self):
        self.put(); p=self.home/'記事.md'; p.write_text('test')
        m=self.check_module()
        with contextlib.redirect_stdout(io.StringIO()): code=m.main(['lint',str(p),'--strict'])
        self.assertEqual(code,1)

    def test_check_upstream_modification_refused(self):
        self.put(); (self.target/'upstream/scripts/yomiyasu_lint.py').write_text('raise Exception()')
        m=self.check_module()
        with self.assertRaises(ValueError): m.verified_script('yomiyasu_lint.py')

    def test_check_no_source_rewrite_and_path_safety(self):
        self.put(); p=self.home/"--本文 ' $().md"; q=self.home/'after.md'
        p.write_text('APP-FR-001 は10秒で確認する。'); q.write_text('APP-FR-001 は20秒で確認する。')
        b={p:p.read_bytes(),q:q.read_bytes()}; m=self.check_module()
        with contextlib.redirect_stdout(io.StringIO()) as o: code=m.main(['compare',str(p),str(q),'--stance','決まり'])
        data=json.loads(o.getvalue()); self.assertEqual(code,1); self.assertTrue(data['protected_changes'])
        self.assertEqual(b,{p:p.read_bytes(),q:q.read_bytes()})
        self.assertIn('--stance=決まり',data['upstream']['report']['received'])

    def test_check_same_input_refused(self):
        self.put(); p=self.home/'x.md'; p.write_text('text'); m=self.check_module()
        with contextlib.redirect_stderr(io.StringIO()): code=m.main(['compare',str(p),str(p)])
        self.assertEqual(code,2)

    def test_check_binary_docx_refused(self):
        self.put(); p=self.home/'x.docx'; p.write_bytes(b'PK00'); m=self.check_module()
        with contextlib.redirect_stderr(io.StringIO()): code=m.main(['lint',str(p)])
        self.assertEqual(code,2)

    def test_check_protected_terms(self):
        self.put(); m=self.check_module()
        changes=m.compare_anchors('双曲空間を使う。','特殊な空間を使う。',['双曲空間'])
        self.assertIn('specified_terms',[x['kind'] for x in changes])

    def test_check_code_links_quotes_math_frontmatter(self):
        self.put(); m=self.check_module()
        b='---\ntype: a\n---\n```python\nx=1\n```\n`code` [ref](target)\n> 引用\n$$x=1$$\n- [ ] 未実施\n'
        a='---\ntype: b\n---\n```python\nx=2\n```\n`kode` [ref](other)\n> 改変\n$$x=2$$\n- [x] 未実施\n'
        kinds={x['kind'] for x in m.compare_anchors(b,a,[])}
        self.assertTrue({'frontmatter','code_blocks','inline_code','link_targets','literal_quotes','math','checkbox_state'} <= kinds)

    def test_japanese_adjacent_numbers_and_units(self):
        self.put(); m=self.check_module()
        for before, after in [('待つのは10秒。','待つのは20秒。'),('締切2026-10-10','締切2026-10-11'),('価格は3万円','価格は4万円')]:
            with self.subTest(before=before):
                self.assertIn('numbers_and_units',[x['kind'] for x in m.compare_anchors(before,after,[])])

    def test_check_prose_only_changes_no_semantic_claim(self):
        self.put(); m=self.check_module()
        self.assertEqual(m.compare_anchors('処理が可能です。','処理できます。',[]),[])

    def test_check_ids_mentions(self):
        self.put(); m=self.check_module(); changes=m.compare_anchors('APP-FR-001 #12 @alice','APP-FR-002 #13 @bob',[])
        self.assertIn('ids_mentions',[c['kind'] for c in changes])

    def test_helper_timeout_not_pass(self):
        self.put(); m=self.check_module(); p=self.home/'x.md'; p.write_text('text')
        with mock.patch.object(m.subprocess,'run',side_effect=subprocess.TimeoutExpired('python',30)), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(m.main(['lint',str(p)]),2)

    def test_skill_contract(self):
        self.put(); s=(self.target/'SKILL.md').read_text(); policy=(self.target/'references/usage-policy.md').read_text()
        for text in ['upstream/SKILL.upstream.md','GitHub Project Director','SpecKit Upstream','Office Workbench',
                     '数値','Issue','未実施','承認','二重','本文だけ','scripts/check.py']:
            self.assertIn(text,s)
        self.assertIn('一律に強制しない',policy); self.assertIn('最大一回',s)

    def test_safe_paths_reject(self):
        for path in ['../x','/tmp/x','a\\b','x:bad','a//b']:
            with self.subTest(path=path), self.assertRaises(I.InstallError): I.safe_rel(path)

    def test_redirect_external_refused(self):
        handler=I.LockedRedirect()
        with self.assertRaises(I.InstallError): handler.redirect_request(None,None,302,'',{},'http://example.com/a')

    def test_extras_collide_new_assets_refused(self):
        self.put(); extra=self.target/'references/new.md'; extra.write_text('user')
        original=I.bundle
        def more(*args): return {**original(*args),'references/new.md':b'new managed'}
        with mock.patch.object(I,'bundle',side_effect=more):
            with self.assertRaises(I.InstallError): self.put(force=True)
        self.assertEqual(extra.read_text(),'user')

class BundleTests(unittest.TestCase):
    setUp = InstallerTests.setUp
    put = InstallerTests.put
    files = InstallerTests.files

    def both(self, **kwargs):
        return I.install_selected(self.target.parent, apply=True, source=self.source, **kwargs)

    def paragraph(self):
        return self.target.parent/'paragraph-writing'

    def snapshots(self):
        return {name:I.inventory(self.target.parent/name) for name in I.COMPONENTS}

    def test_default_cli_installs_both_and_only_two_entrypoints(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            code = I.main(['--apply','--source-dir',str(self.source)])
        self.assertEqual(code,0)
        result=json.loads(stream.getvalue())
        self.assertEqual(set(result['components']),set(I.COMPONENTS))
        self.assertEqual({p.parent.name for p in self.target.parent.rglob('SKILL.md')},set(I.COMPONENTS))
        for name in I.COMPONENTS:
            marker=json.loads((self.target.parent/name/I.MANIFEST).read_text())
            self.assertEqual(marker['owner'],I.OWNERS[name])

    def test_bundle_preview_no_directory_or_network(self):
        with mock.patch.object(I,'download',side_effect=AssertionError('network')):
            result=I.install_selected(self.target.parent)
        self.assertFalse(result['applied'])
        self.assertFalse(self.target.parent.exists())

    def test_bundle_idempotent_no_files_or_mtimes_changed(self):
        self.both(); before=self.snapshots()
        mtimes={p:p.stat().st_mtime_ns for p in self.target.parent.rglob('*') if p.is_file()}
        with mock.patch.object(I,'download',side_effect=AssertionError('network')):
            result=I.install_selected(self.target.parent,apply=True)
        self.assertFalse(result['applied'])
        self.assertEqual(before,self.snapshots())
        self.assertEqual(mtimes,{p:p.stat().st_mtime_ns for p in mtimes})

    def test_new_paragraph_inherits_existing_explicit_yomiyasu(self):
        self.put(mode='explicit')
        result=self.both()
        self.assertEqual(result['components']['paragraph-writing']['mode'],'explicit')
        self.assertIn('allow_implicit_invocation: false',(self.paragraph()/'agents/openai.yaml').read_text())

    def test_individual_existing_modes_preserved(self):
        self.put(mode='explicit')
        I.install_selected(self.target.parent,('paragraph-writing',),mode='auto',apply=True)
        result=self.both()
        self.assertEqual(result['components']['yomiyasu']['mode'],'explicit')
        self.assertEqual(result['components']['paragraph-writing']['mode'],'auto')

    def test_explicit_mode_changes_both_with_force_offline(self):
        self.both()
        with mock.patch.object(I,'download',side_effect=AssertionError('network')):
            result=I.install_selected(self.target.parent,mode='explicit',force=True,apply=True)
        for entry in result['components'].values():
            self.assertEqual(entry['mode'],'explicit')
            self.assertTrue(Path(entry['backup']).exists())

    def test_paragraph_only_no_yomiyasu_or_network(self):
        with mock.patch.object(I,'download',side_effect=AssertionError('network')):
            I.install_selected(self.target.parent,('paragraph-writing',),apply=True)
        self.assertFalse(self.target.exists())
        meta=json.loads((self.paragraph()/'UPSTREAM.json').read_text())
        for name,digest in meta['files'].items():
            self.assertEqual(I.sha((self.paragraph()/name).read_bytes()),digest)

    def test_paragraph_source_option_rejected_without_writes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code=I.main(['--only','paragraph-writing','--source-dir',str(self.source),'--apply'])
        self.assertEqual(code,2)
        self.assertFalse(self.target.parent.exists())

    def test_legacy_yomiyasu_manifest_requires_force_and_keeps_upstream(self):
        self.put(mode='explicit'); marker=self.target/I.MANIFEST
        legacy=json.loads(marker.read_text());legacy['version']='1.1.0';legacy.pop('component')
        marker.write_text(json.dumps(legacy)); before=self.files()
        with self.assertRaises(I.InstallError):self.both()
        self.assertFalse(self.paragraph().exists())
        with mock.patch.object(I,'download',side_effect=AssertionError('network')):
            result=I.install_selected(self.target.parent,force=True,apply=True)
        self.assertEqual((self.target/'upstream/SKILL.upstream.md').read_bytes(),before['upstream/SKILL.upstream.md'])
        self.assertEqual(result['components']['paragraph-writing']['mode'],'explicit')

    def test_paragraph_edit_blocks_whole_update_even_force(self):
        self.both();(self.paragraph()/'SKILL.md').write_text('user edit');before=self.snapshots()
        with self.assertRaises(I.InstallError):self.both(force=True)
        self.assertEqual(before,self.snapshots())

    def test_unowned_paragraph_blocks_before_yomiyasu_install(self):
        self.paragraph().mkdir(parents=True);(self.paragraph()/'SKILL.md').write_text('other install')
        with self.assertRaises(I.InstallError):self.both(force=True)
        self.assertFalse(self.target.exists())
        self.assertEqual((self.paragraph()/'SKILL.md').read_text(),'other install')

    def test_owner_cannot_be_swapped_between_components(self):
        self.both();p=self.paragraph()/I.MANIFEST;marker=json.loads(p.read_text());marker['owner']=I.OWNER;p.write_text(json.dumps(marker))
        with self.assertRaises(I.InstallError):self.both(force=True)

    def test_duplicate_paragraph_blocks_entire_install(self):
        duplicate=Path(os.environ['CODEX_HOME'])/'skills/paragraph-writing'
        duplicate.mkdir(parents=True);(duplicate/'SKILL.md').write_text('other')
        with self.assertRaises(I.InstallError):self.both()
        self.assertFalse(self.target.exists())
        self.assertFalse(self.paragraph().exists())

    def test_companions_not_classified_as_conflicting_stylers(self):
        self.both()
        for name in I.COMPONENTS:
            result,code=I.doctor(self.target.parent/name,None,name)
            self.assertEqual(code,0)
            self.assertEqual(result['conflicts']['other_style_skills'],[])

    def test_second_install_switch_failure_restores_both_existing(self):
        self.both();before=self.snapshots();original=I.os.replace
        def fail(src,dst):
            if Path(src).name.startswith('.paragraph-writing-stage-'):raise OSError('second switch fails')
            return original(src,dst)
        with mock.patch.object(I.os,'replace',side_effect=fail):
            with self.assertRaises(OSError):self.both(force=True)
        self.assertEqual(before,self.snapshots())
        self.assertFalse((self.target.parent/'.yomiyasu-installer.lock').exists())

    def test_second_install_failure_removes_first_new_component(self):
        original=I.os.replace
        def fail(src,dst):
            if Path(src).name.startswith('.paragraph-writing-stage-'):raise OSError('second switch fails')
            return original(src,dst)
        with mock.patch.object(I.os,'replace',side_effect=fail):
            with self.assertRaises(OSError):self.both()
        self.assertFalse(self.target.exists());self.assertFalse(self.paragraph().exists())

    def test_second_preparation_failure_leaves_existing_files_unchanged(self):
        self.both();before=self.snapshots()
        with mock.patch.object(I,'paragraph_bundle',side_effect=I.InstallError('invalid payload')):
            with self.assertRaises(I.InstallError):self.both(force=True)
        self.assertEqual(before,self.snapshots())

    def test_concurrent_paragraph_edit_is_preserved_before_switch(self):
        self.both();before=self.files();original=I.paragraph_bundle
        def changed(mode):
            data=original(mode);(self.paragraph()/'SKILL.md').write_text('concurrent edit');return data
        with mock.patch.object(I,'paragraph_bundle',side_effect=changed):
            with self.assertRaises(I.InstallError):self.both(force=True)
        self.assertEqual(before,self.files())
        self.assertEqual((self.paragraph()/'SKILL.md').read_text(),'concurrent edit')

    def test_user_paragraph_extra_preserved_update_but_blocks_uninstall(self):
        self.both();(self.paragraph()/'notes.txt').write_text('keep')
        self.both(force=True);before=self.snapshots()
        self.assertEqual((self.paragraph()/'notes.txt').read_text(),'keep')
        with self.assertRaises(I.InstallError):I.uninstall_selected(self.target.parent,I.COMPONENTS,True)
        self.assertEqual(before,self.snapshots())

    def test_second_uninstall_rename_failure_restores_both(self):
        self.both();before=self.snapshots();original=I.os.replace
        def fail(src,dst):
            if Path(src)==self.paragraph():raise OSError('second removal fails')
            return original(src,dst)
        with mock.patch.object(I.os,'replace',side_effect=fail):
            with self.assertRaises(OSError):I.uninstall_selected(self.target.parent,I.COMPONENTS,True)
        self.assertEqual(before,self.snapshots())

    def test_uninstall_only_paragraph_keeps_yomiyasu(self):
        self.both();before=self.files()
        with contextlib.redirect_stdout(io.StringIO()):
            code=I.main(['--uninstall','--only','paragraph-writing','--apply'])
        self.assertEqual(code,0);self.assertFalse(self.paragraph().exists());self.assertEqual(before,self.files())

    def test_bundle_uninstall_preview_does_not_mutate(self):
        self.both();before=self.snapshots()
        I.uninstall_selected(self.target.parent,I.COMPONENTS,False)
        self.assertEqual(before,self.snapshots())

    def test_bundle_uninstall_removes_both_with_distinct_backups(self):
        self.both();result=I.uninstall_selected(self.target.parent,I.COMPONENTS,True)
        paths={entry['backup'] for entry in result['components'].values()}
        self.assertEqual(len(paths),2)
        self.assertTrue(all(Path(p).exists() for p in paths))
        self.assertFalse(self.target.exists());self.assertFalse(self.paragraph().exists())

    def test_paragraph_check_update_is_offline_read_only(self):
        self.both();before=self.snapshots()
        with mock.patch.object(I,'download',side_effect=AssertionError('network')):
            result=I.check_updates(self.target.parent,('paragraph-writing',))
        self.assertFalse(result['update_available']);self.assertEqual(before,self.snapshots())

    def test_paragraph_update_is_offline_and_leaves_yomiyasu_unchanged(self):
        self.both();before=self.files()
        with mock.patch.object(I,'download',side_effect=AssertionError('network')):
            I.install_selected(self.target.parent,('paragraph-writing',),update=True,apply=True)
        self.assertEqual(before,self.files())

    def test_bundle_doctor_no_mtime_changes(self):
        self.both();before=self.snapshots()
        mtimes={p:p.stat().st_mtime_ns for p in self.target.parent.rglob('*') if p.is_file()}
        with contextlib.redirect_stdout(io.StringIO()) as stream:code=I.main(['--doctor'])
        self.assertEqual(code,0)
        self.assertTrue(all(entry['status']=='READY_FILES' for entry in json.loads(stream.getvalue())['components'].values()))
        self.assertEqual(before,self.snapshots());self.assertEqual(mtimes,{p:p.stat().st_mtime_ns for p in mtimes})

    def test_extracted_python_can_install_paragraph_alone(self):
        destination=self.home/'extract';I.extract(destination)
        result=subprocess.run([sys.executable,str(destination/'installer.py'),'--only','paragraph-writing','--apply'],
                              cwd=self.home,text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue((self.paragraph()/'SKILL.md').exists());self.assertFalse(self.target.exists())

    def test_corrupt_bundled_original_rejected_before_skill_placement(self):
        data=I.assets();data['paragraph-writing/upstream/SKILL.upstream.md']=b'corrupt'
        with mock.patch.object(I,'assets',return_value=data):
            with self.assertRaises(I.InstallError):
                I.install_selected(self.target.parent,('paragraph-writing',),apply=True)
        self.assertFalse(self.paragraph().exists())

    def test_edit_during_backup_is_preserved_on_install(self):
        self.both();before=self.files();original=I.backup
        def modified(target,files):
            path=original(target,files)
            if target==self.paragraph():(target/'SKILL.md').write_text('edit during backup')
            return path
        with mock.patch.object(I,'backup',side_effect=modified):
            with self.assertRaises(I.InstallError):self.both(force=True)
        self.assertEqual(before,self.files())
        self.assertEqual((self.paragraph()/'SKILL.md').read_text(),'edit during backup')

    def test_edit_during_backup_is_preserved_on_uninstall(self):
        self.both();before=self.files();original=I.backup
        def modified(target,files):
            path=original(target,files)
            if target==self.paragraph():(target/'SKILL.md').write_text('edit during backup')
            return path
        with mock.patch.object(I,'backup',side_effect=modified):
            with self.assertRaises(I.InstallError):I.uninstall_selected(self.target.parent,I.COMPONENTS,True)
        self.assertEqual(before,self.files())
        self.assertEqual((self.paragraph()/'SKILL.md').read_text(),'edit during backup')


if __name__=='__main__': unittest.main()
