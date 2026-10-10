"""Offline conformance and regression tests. Upstream execution uses marked stubs."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock
import zipfile

if 'I' not in globals():
    spec = importlib.util.spec_from_file_location('proposal_installer', Path(__file__).resolve().parents[1]/'installer.py')
    I = importlib.util.module_from_spec(spec); sys.modules[spec.name] = I; spec.loader.exec_module(I)
    A = I.assets()
L = types.ModuleType('proposal_check')
L.__file__ = str(Path(tempfile.gettempdir())/'proposal-local/scripts/check.py')
sys.modules[L.__name__] = L
exec(compile(A['scripts/check.py'].decode('utf-8'), 'check.py', 'exec'), L.__dict__)


def fixture(version=1):
    """Synthetic upstream, deliberately not the actual yomiyasu implementation."""
    values = {
        'SKILL.md': f'---\nname: yomiyasu\ndescription: synthetic fixture\n---\n# Stub {version}\n'.encode(),
        'LICENSE': b'TEST LICENSE - synthetic only\n',
        'UNICODE-LICENSE.txt': b'TEST Unicode license placeholder - synthetic only\n',
        'references/domains/tech.md': b'Synthetic reference\n',
        'scripts/markdown_visibility.py': b'READY = True\n',
        'scripts/yomiyasu_lint.py': b'# Unicode License; --json\nimport json\nimport markdown_visibility\nprint(json.dumps({"fixture": True, "findings": []}))\n',
        'scripts/yomiyasu_diff.py': b'# --json\nimport json\nprint(json.dumps({"fixture": True, "changes": []}))\n',
    }
    rows = [{'path': 'skills/yomiyasu/'+k, 'type': 'blob', 'mode': '100644',
             'sha': I.blob_sha(v), 'size': len(v)} for k, v in values.items()]
    rows += [{'path': 'LICENSE', 'type': 'blob', 'mode': '100644',
              'sha': I.blob_sha(values['LICENSE']), 'size': len(values['LICENSE'])}]
    meta = {'repository': I.REPO, 'tag': f'v0.0.{version}', 'commit': str(version)*40,
            'files': I.release_file_manifest({'tree': rows, 'truncated': False})}
    mapped = {I.map_upstream(k): v for k, v in values.items()}
    return meta, mapped, rows


class Isolated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='yomiyasu-unit-')
        self.home = Path(self.tmp.name)
        self.root = self.home/'skills'
        self.project = self.home/'project'; self.project.mkdir()
        self.env = mock.patch.dict(os.environ, {'HOME': str(self.home), 'CODEX_HOME': str(self.home/'.codex')})
        self.env.start()
        self.old_cwd = Path.cwd(); os.chdir(self.project)
        self.meta, self.up, self.rows = fixture()
        self.resolve = mock.patch.object(I, 'resolve_release', return_value=self.meta)
        self.fetch = mock.patch.object(I, 'fetch_release', return_value=self.up)
        self.resolve_mock = self.resolve.start(); self.fetch_mock = self.fetch.start()
    def tearDown(self):
        self.fetch.stop(); self.resolve.stop(); self.env.stop(); os.chdir(self.old_cwd); self.tmp.cleanup()
    def install(self, names=I.COMPONENTS, **kwargs):
        return I.install_selected(self.root, names, apply=True, project=self.project, **kwargs)
    def snapshot(self, name='yomiyasu'):
        return I.inventory(self.root/name)
    def legacy(self, names=I.COMPONENTS):
        self.install(names)
        for name in names:
            target = self.root/name
            marker = json.loads((target/I.MANIFEST).read_text())
            marker['version'] = '1.3.0'
            (target/I.MANIFEST).write_text(json.dumps(marker))


class InstallerTests(Isolated):
    def test_install_all(self):
        result = self.install()
        self.assertTrue(result['applied'])
        self.assertEqual(set(result['components']), set(I.COMPONENTS))
        for name in I.COMPONENTS:
            self.assertTrue((self.root/name/'SKILL.md').is_file())
    def test_no_args_dry_run(self):
        I.install_selected(self.root, I.COMPONENTS, project=self.project)
        self.assertFalse(self.root.exists()); self.resolve_mock.assert_not_called()
    def test_update_preview_no_network(self):
        I.install_selected(self.root, I.COMPONENTS, update=True, project=self.project)
        self.assertFalse(self.root.exists()); self.resolve_mock.assert_not_called()
    def test_idempotent_skip(self):
        self.install(); before = self.snapshot(); self.resolve_mock.reset_mock()
        self.assertFalse(self.install()['applied']); self.assertEqual(before, self.snapshot()); self.resolve_mock.assert_not_called()
    def test_explicit_mode_all(self):
        self.install(mode='explicit')
        for n in I.COMPONENTS:
            self.assertIn(b'allow_implicit_invocation: false', self.snapshot(n)['agents/openai.yaml'])
    def test_mode_is_preserved(self):
        self.install(mode='explicit'); self.install(force=True)
        self.assertEqual(json.loads(self.snapshot()[I.MANIFEST])['mode'], 'explicit')
    def test_mode_change_requires_force(self):
        self.install()
        with self.assertRaises(I.InstallError): self.install(mode='explicit')
    def test_force_does_not_fetch_new_upstream(self):
        self.install(); before = self.snapshot(); self.resolve_mock.reset_mock()
        self.install(force=True); self.resolve_mock.assert_not_called()
        self.assertEqual(before['upstream/SKILL.upstream.md'], self.snapshot()['upstream/SKILL.upstream.md'])
    def test_old_version_requires_update(self):
        self.legacy()
        with self.assertRaises(I.InstallError): self.install()
    def test_v1_3_owner_schema_migration(self):
        self.legacy(); result = self.install(update=True)
        for n in I.COMPONENTS:
            self.assertEqual(json.loads(self.snapshot(n)[I.MANIFEST])['version'], I.VERSION)
            self.assertTrue(Path(result['components'][n]['backup']).is_file())
    def test_upstream_only_preserves_wrapper_bytes(self):
        self.legacy(); before = self.snapshot(); meta, up, _ = fixture(2)
        self.resolve_mock.return_value = meta; self.fetch_mock.return_value = up
        self.install(('yomiyasu',), update=True, upstream_only=True)
        after = self.snapshot()
        for k, v in before.items():
            if k != I.MANIFEST and k != 'UPSTREAM.json' and not k.startswith('upstream/'):
                self.assertEqual(v, after[k], k)
        self.assertEqual(json.loads(after[I.MANIFEST])['version'], '1.3.0')
        self.assertEqual(json.loads(after[I.MANIFEST])['upstream_commit'], '2'*40)
    def test_upstream_only_does_not_touch_companions(self):
        self.install(); before = self.snapshot('paragraph-writing')
        self.install(('yomiyasu',), update=True, upstream_only=True)
        self.assertEqual(before, self.snapshot('paragraph-writing'))
    def test_upstream_only_requires_existing(self):
        with self.assertRaises(I.InstallError): self.install(('yomiyasu',), update=True, upstream_only=True)
    def test_upstream_only_rejects_mode(self):
        self.install()
        with self.assertRaises(I.InstallError): self.install(('yomiyasu',), update=True, upstream_only=True, mode='auto')
    def test_update_ref_is_forwarded(self):
        self.install(('yomiyasu',), update=True, upstream_ref='v1.1.1')
        self.resolve_mock.assert_called_with('v1.1.1')
    def test_edited_file_never_overwritten(self):
        self.install(); p = self.root/'yomiyasu/SKILL.md'; p.write_text('my edits')
        with self.assertRaises(I.InstallError): self.install(update=True, force=True)
        self.assertEqual(p.read_text(), 'my edits')
    def test_missing_managed_file_blocks(self):
        self.install(); (self.root/'yomiyasu/SKILL.md').unlink()
        with self.assertRaises(I.InstallError): self.install(update=True)
    def test_user_extra_is_preserved(self):
        self.install(); p = self.root/'yomiyasu/my-style.md'; p.write_text('custom')
        self.install(update=True); self.assertEqual(p.read_text(), 'custom')
    def test_extra_collision_blocks_all(self):
        self.install(); name = 'references/future.md'; (self.root/'yomiyasu'/name).write_text('mine')
        original = I.assets
        def expanded(): return {**original(), name: b'new managed'}
        before = self.snapshot('paragraph-writing')
        with mock.patch.object(I, 'assets', side_effect=expanded):
            with self.assertRaises(I.InstallError): self.install(update=True)
        self.assertEqual(before, self.snapshot('paragraph-writing'))
    def test_path_prefix_extra_collision_blocks(self):
        self.install(); (self.root/'yomiyasu/newdir').write_text('user file')
        original = I.assets
        with mock.patch.object(I, 'assets', side_effect=lambda: {**original(), 'references/new.md': b'x', 'scripts/newdir/x.py': b'pass'}):
            # An existing user file at scripts/newdir collides with a new directory.
            (self.root/'yomiyasu/scripts/newdir').write_text('user')
            with self.assertRaises(I.InstallError): self.install(update=True)
    def test_untracked_upstream_file_blocks(self):
        self.install(); (self.root/'yomiyasu/upstream/scripts/evil.py').write_text('pass')
        with self.assertRaises(I.InstallError): self.install(update=True)
    def test_other_owner_not_overwritten(self):
        self.root.mkdir(); target = self.root/'yomiyasu'; target.mkdir(); (target/'SKILL.md').write_text('third party')
        with self.assertRaises(I.InstallError): self.install(force=True)
        self.assertEqual((target/'SKILL.md').read_text(), 'third party')
    def test_symlink_target_rejected(self):
        self.root.mkdir(); (self.root/'yomiyasu').symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(I.InstallError): self.install()
    def test_broken_symlink_target_rejected(self):
        self.root.mkdir(); (self.root/'yomiyasu').symlink_to(self.home/'absent')
        with self.assertRaises(I.InstallError): self.install()
    def test_symlink_parent_rejected(self):
        self.root.symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(I.InstallError): self.install()
    def test_duplicate_skill_blocks(self):
        other = self.home/'.agents/skills/yomiyasu'; other.mkdir(parents=True); (other/'SKILL.md').write_text('other')
        with self.assertRaises(I.InstallError): self.install()
    def test_other_style_is_not_disabled(self):
        other = self.home/'.agents/skills/natural-japanese'; other.mkdir(parents=True); (other/'SKILL.md').write_text('other')
        r = self.install(('yomiyasu',))
        self.assertIn(str(other), r['conflicts']['other_style_skills']); self.assertEqual((other/'SKILL.md').read_text(), 'other')
    def test_lock_does_not_delete_another_lock(self):
        self.root.mkdir(); lock = self.root/'.yomiyasu-installer.lock'; lock.write_text('other pid')
        with self.assertRaises(I.InstallError): self.install()
        self.assertEqual(lock.read_text(), 'other pid')
    def test_download_failure_changes_nothing(self):
        self.fetch_mock.side_effect = OSError('network failure')
        with self.assertRaises(OSError): self.install()
        self.assertFalse(self.root.exists())
    def test_update_failure_preserves_all(self):
        self.install(); before = {n: self.snapshot(n) for n in I.COMPONENTS}; self.fetch_mock.side_effect = OSError('network')
        with self.assertRaises(OSError): self.install(update=True)
        for n in I.COMPONENTS: self.assertEqual(before[n], self.snapshot(n))
    def test_backup_is_exact(self):
        self.install(); old = self.snapshot(); r = self.install(('yomiyasu',), force=True)
        with zipfile.ZipFile(r['backup']) as z:
            self.assertEqual(old, {n: z.read(n) for n in z.namelist()})
    def test_mid_switch_failure_restores_every_directory(self):
        self.install(); old = {n: self.snapshot(n) for n in I.COMPONENTS}; replace = I.os.replace
        def fail_second(src, dst):
            if '-stage-' in str(src) and Path(dst).name == 'paragraph-writing': raise OSError('simulated rename failure')
            return replace(src, dst)
        with mock.patch.object(I.os, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError): self.install(force=True)
        for n in I.COMPONENTS: self.assertEqual(old[n], self.snapshot(n))
    def test_no_config_or_agents_changes(self):
        config = self.home/'.codex/config.toml'; config.parent.mkdir(); config.write_text('keep=true')
        agents = self.project/'AGENTS.md'; agents.write_text('keep instructions')
        self.install(); self.assertEqual(config.read_text(), 'keep=true'); self.assertEqual(agents.read_text(), 'keep instructions')
    def test_uninstall_preview(self):
        self.install(); before=self.snapshot(); I.uninstall_selected(self.root, I.COMPONENTS, False)
        self.assertEqual(before,self.snapshot())
    def test_uninstall_apply(self):
        self.install(); I.uninstall_selected(self.root, I.COMPONENTS, True)
        self.assertFalse((self.root/'yomiyasu').exists())
    def test_uninstall_refuses_extras(self):
        self.install(); (self.root/'yomiyasu/notes.md').write_text('mine')
        with self.assertRaises(I.InstallError): I.uninstall_selected(self.root, I.COMPONENTS, True)
    def test_uninstall_refuses_edited(self):
        self.install(); (self.root/'yomiyasu/SKILL.md').write_text('mine')
        with self.assertRaises(I.InstallError): I.uninstall_selected(self.root, I.COMPONENTS, True)
    def test_doctor_ready(self):
        self.install(); report,code=I.doctor(self.root/'yomiyasu',self.project)
        self.assertEqual(code,0);self.assertEqual(report['status'],'READY_FILES')
    def test_doctor_missing_not_ready(self):
        self.assertEqual(I.doctor(self.root/'yomiyasu',self.project)[1],2)
    def test_doctor_flags_untracked_upstream(self):
        self.install();(self.root/'yomiyasu/upstream/scripts/evil.py').write_text('pass')
        self.assertEqual(I.doctor(self.root/'yomiyasu',self.project)[1],2)
    def test_only_companion_is_offline(self):
        self.install(('paragraph-writing',));self.resolve_mock.assert_not_called()
        self.assertFalse((self.root/'yomiyasu').exists())
    def test_check_update_is_read_only(self):
        self.install();before=self.snapshot();I.check_updates(self.root,I.COMPONENTS)
        self.assertEqual(before,self.snapshot())
    def test_snapshot_source_offline(self):
        self.install(('yomiyasu',));source=self.root/'yomiyasu';other=self.home/'other'
        result=I.install_selected(other,('yomiyasu',),apply=True,source=source,project=self.project)
        self.assertFalse(result['network'])
    def test_snapshot_source_rejects_extra_module(self):
        self.install(('yomiyasu',));(self.root/'yomiyasu/upstream/scripts/evil.py').write_text('pass')
        with self.assertRaises(I.InstallError): I.source_upstream(self.root/'yomiyasu')
    def test_stub_upstream_runner_and_sibling_module(self):
        self.install(('yomiyasu',)); original=L.ROOT;L.ROOT=self.root/'yomiyasu'
        try:
            report=L.upstream('yomiyasu_lint.py',[])
            self.assertTrue(report['report']['fixture'])
        finally:L.ROOT=original
    def test_stub_runner_rejects_edited_dependency(self):
        self.install(('yomiyasu',));(self.root/'yomiyasu/upstream/scripts/markdown_visibility.py').write_text('READY=False')
        original=L.ROOT;L.ROOT=self.root/'yomiyasu'
        try:
            with self.assertRaises(ValueError):L.upstream('yomiyasu_lint.py',[])
        finally:L.ROOT=original
    def test_extract_empty_only(self):
        dst=self.home/'extract';dst.mkdir();(dst/'keep').write_text('mine')
        with self.assertRaises(I.InstallError):I.extract(dst)
    def test_extracted_source_can_read_assets(self):
        dst=self.home/'extract';I.extract(dst)
        spec=importlib.util.spec_from_file_location('exported_installer',dst/'installer.py')
        mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
        self.assertIn('SKILL.md',mod.assets())
    def test_cli_invalid_modes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code=I.main(['--doctor','--apply'])
        self.assertEqual(code,2)
    def test_cli_upstream_only_narrows_default_all(self):
        self.install()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code=I.main(['--skills-dir',str(self.root),'--update','--upstream-only','--apply'])
        self.assertEqual(code,0);self.assertEqual(json.loads(buf.getvalue())['component'],'yomiyasu')
    def test_assets_python310_syntax(self):
        import ast
        for name,data in I.assets().items():
            if name.endswith('.py'):ast.parse(data.decode(),filename=name,feature_version=(3,10))


class UpstreamAndSecurityTests(unittest.TestCase):
    def test_paths_are_rejected(self):
        for value in ('../x','/x','x/../y','x\\y','C:x','x//y','x\0y','.'):
            with self.subTest(value=value):
                with self.assertRaises(I.InstallError):I.safe_rel(value)
    def test_observed_v1_1_1_tree_selection(self):
        tree=json.loads(A['tests/upstream-v1.1.1-tree.json'])
        files=I.release_file_manifest(tree)
        self.assertEqual(len(files),13)
        self.assertIn('UNICODE-LICENSE.txt',files)
        self.assertIn('scripts/markdown_visibility.py',files)
        self.assertNotIn('.claude-plugin/plugin.json',files)
        self.assertEqual(files['SKILL.md']['git_blob_sha1'],'ad38af2140d4e102cad69737f2ca035cc1e87677')
    def test_unicode_license_is_included(self):
        _,_,rows=fixture(); files=I.release_file_manifest({'tree':rows,'truncated':False})
        self.assertIn('UNICODE-LICENSE.txt',files);self.assertIn('scripts/markdown_visibility.py',files)
    def test_legacy_layout_supported(self):
        _,_,rows=fixture();rows=[{**r,'path':r['path'].removeprefix('skills/yomiyasu/')} for r in rows if r['path'].startswith('skills/')]
        self.assertIn('SKILL.md',I.release_file_manifest({'tree':rows}))
    def test_truncated_tree_blocks(self):
        with self.assertRaises(I.InstallError):I.release_file_manifest({'tree':[],'truncated':True})
    def test_symlink_tree_blocks(self):
        _,_,rows=fixture();rows[0]['mode']='120000'
        with self.assertRaises(I.InstallError):I.release_file_manifest({'tree':rows})
    def test_path_traversal_in_tree_blocks(self):
        _,_,rows=fixture();rows.append({'path':'skills/yomiyasu/scripts/../../evil.py','type':'blob','mode':'100644','sha':'a'*40,'size':1})
        with self.assertRaises(I.InstallError):I.release_file_manifest({'tree':rows})
    def test_nested_skill_blocks(self):
        _,_,rows=fixture();rows.append({'path':'skills/yomiyasu/references/nested/SKILL.md','type':'blob','mode':'100644','sha':'a'*40,'size':1})
        with self.assertRaises(I.InstallError):I.release_file_manifest({'tree':rows})
    def test_conflicting_duplicate_license_blocks(self):
        _,_,rows=fixture();rows[-1]['sha']='a'*40
        with self.assertRaises(I.InstallError):I.release_file_manifest({'tree':rows})
    def test_missing_required_files_blocks(self):
        with self.assertRaises(I.InstallError):I.release_file_manifest({'tree':[]})
    def test_size_limit_blocks(self):
        _,_,rows=fixture();rows[0]['size']=I.MAX_FILE+1
        with self.assertRaises(I.InstallError):I.release_file_manifest({'tree':rows})
    def test_hash_mismatch_blocks(self):
        with self.assertRaises(I.InstallError):I.verify_file('SKILL.md',b'bad',{'size':3,'git_blob_sha1':'a'*40})
    def test_python_syntax_blocks(self):
        raw=b'def x(:'
        with self.assertRaises(SyntaxError):I.verify_file('scripts/a.py',raw,{'size':len(raw),'git_blob_sha1':I.blob_sha(raw)})
    def test_contract_missing_helper(self):
        _,files,_=fixture();del files['upstream/scripts/markdown_visibility.py']
        with self.assertRaises(I.InstallError):I.upstream_contract(files)
    def test_contract_missing_license(self):
        _,files,_=fixture();del files['upstream/UNICODE-LICENSE.txt']
        with self.assertRaises(I.InstallError):I.upstream_contract(files)
    def test_changed_skill_name_blocks(self):
        _,files,_=fixture();files['upstream/SKILL.upstream.md']=b'---\nname: different\n---\n'
        with self.assertRaises(I.InstallError):I.upstream_contract(files)
    def test_allowed_urls(self):
        I.validate_url('https://api.github.com/repos/nanaism/yomiyasu/releases/latest')
        I.validate_url('https://raw.githubusercontent.com/nanaism/yomiyasu/main/README.md')
    def test_other_endpoints_are_rejected(self):
        for url in ('http://api.github.com/repos/nanaism/yomiyasu/x','https://api.github.com/repos/evil/repo/x','https://evil.example/x','https://user:pass@api.github.com/repos/nanaism/yomiyasu/x'):
            with self.subTest(url=url):
                with self.assertRaises(I.InstallError):I.validate_url(url)
    def test_lightweight_tag_resolution(self):
        with mock.patch.object(I,'json_download',return_value={'object':{'type':'commit','sha':'a'*40}}):
            self.assertEqual(I.tag_commit('v1.1.1'),'a'*40)
    def test_annotated_tag_ignores_remote_url(self):
        replies=[{'object':{'type':'tag','sha':'b'*40,'url':'https://evil.example'}},{'object':{'type':'commit','sha':'a'*40}}]
        with mock.patch.object(I,'json_download',side_effect=replies) as getter:
            self.assertEqual(I.tag_commit('v1.1.1'),'a'*40)
            self.assertIn('/git/tags/'+('b'*40),getter.call_args[0][0])
    def test_prerelease_is_rejected(self):
        with mock.patch.object(I,'json_download',return_value={'prerelease':True,'tag_name':'v1.1.1'}):
            with self.assertRaises(I.InstallError):I.resolve_release()
    def test_downloaded_files_verified_and_mapped(self):
        meta,files,_=fixture()
        source={spec['repo_path']:files[I.map_upstream(name)] for name,spec in meta['files'].items()}
        with mock.patch.object(I,'download',side_effect=lambda url:source[url.split(meta['commit']+'/',1)[1]]):
            self.assertEqual(I.fetch_release(meta),files)


class TextRegressionTests(unittest.TestCase):
    def test_soft_wrapped_meta_is_detected(self):
        self.assertTrue(L.local_lint('ご依頼に\n沿って整理しました。'))
    def test_footnote_continuation_detected(self):
        self.assertTrue(L.local_lint('[^a]: 注記\n    ご依頼に沿って整理しました。'))
    def test_nested_inline_quotes_are_protected(self):
        self.assertFalse(L.local_lint('「中に『ご依頼に沿って』を含む」という用例。'))
    def test_comment_continuation_detected(self):
        self.assertTrue(L.local_lint('<!--\nここに図を入れる\n-->'))
    def test_four_backtick_fence_protected(self):
        self.assertFalse(L.local_lint('````\n```\nご依頼に沿って\n````'))
    def test_outline_respects_blank_paragraphs(self):
        rows=L.outline('# 見出し\n\n方式Aは速い。理由を示す。\n\n方式Bは遅い。')
        self.assertEqual([x['first_sentence'] for x in rows if x['kind']=='paragraph'],['方式Aは速い。','方式Bは遅い。'])
    def test_outline_ignores_code(self):
        self.assertFalse([x for x in L.outline('```\ncode\n```') if x['kind']=='paragraph'])
    def test_outline_decimal(self):
        rows=L.outline('正解率は0.82だった。比較を続ける。')
        self.assertEqual(rows[0]['first_sentence'],'正解率は0.82だった。')
    def test_negative_to_positive_is_flagged(self):
        self.assertTrue(L.compare_anchors('効果は確認できない。','効果を確認した。'))
    def test_no_significance_to_no_effect_flagged(self):
        self.assertTrue(L.compare_anchors('有意差はなかった。','効果はない。'))
    def test_protected_number_changed(self):
        self.assertTrue(L.compare_anchors('正解率は82%。','正解率は86%。'))
    def test_url_changed(self):
        self.assertTrue(L.compare_anchors('[出典](https://example.org/a)','[出典](https://example.org/b)'))
    def test_term_removed(self):
        self.assertTrue(L.compare_anchors('Poincareモデルを比較した。','モデルを比較した。',['Poincare']))
    def test_citation_removed(self):
        self.assertTrue(L.compare_anchors('結果を報告した[1]。','結果を報告した。'))
    def test_code_changed(self):
        self.assertTrue(L.compare_anchors('```python\nx=1\n```','```python\nx=2\n```'))
    def test_math_changed(self):
        self.assertTrue(L.compare_anchors('$x=y$','$x=z$'))
    def test_same_anchors_do_not_prove_semantics(self):
        # A counter cannot know that ownership has swapped. This limitation is explicit.
        self.assertEqual(L.compare_anchors('Aは82%、Bは86%。','Aは86%、Bは82%。'),[])
    def test_identical_text_unchanged(self):
        s='本研究では方式Aを評価した。正解率は82%だった。'
        self.assertEqual(L.compare_anchors(s,s),[])
    def test_empty_after_is_flagged(self):
        self.assertTrue(L.compare_anchors('結果を報告した。',''))
    def test_template_todo_is_kept(self):
        self.assertFalse(L.local_lint('TODO: 担当者名を記入。','template'))
    def test_safe_reader_request_in_email(self):
        self.assertFalse(L.local_lint('ご依頼の資料をご確認ください。','email'))
    def test_technical_prompt_is_kept(self):
        self.assertFalse(L.local_lint('プロンプトの長さを測定した。','research'))
    def test_input_rejects_nul(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'a.md';p.write_bytes(b'abc\0')
            with self.assertRaises(ValueError):L.read_text(str(p))
    def test_input_bom_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'a.md';p.write_bytes(b'\xef\xbb\xbfabc')
            self.assertEqual(L.read_text(str(p))[1],'abc')


class DevelopmentCorpusTests(unittest.TestCase):
    pass

for _case in [json.loads(x) for x in A['evals/boundary-cases.jsonl'].decode().splitlines() if x]:
    if _case['split'] != 'development':continue
    def _test(self, case=_case):
        self.assertEqual(bool(L.local_lint(case['text'],case['genre'])),case['expected'],case['id'])
    setattr(DevelopmentCorpusTests,'test_'+_case['id'],_test)

if __name__=='__main__':unittest.main()

class GenerationPreparationTests(Isolated):
    def module(self):
        mod=types.ModuleType('generation_preparation')
        mod.__file__=str(self.home/'evals/prepare_generation_eval.py')
        exec(compile(A['evals/prepare_generation_eval.py'].decode(),mod.__file__,'exec'),mod.__dict__)
        return mod
    def setup_sources(self):
        up=self.home/'upstream';up.mkdir();(up/'SKILL.upstream.md').write_text('Upstream rules')
        old=self.home/'old';new=self.home/'new'
        for folder,names in [(old,['SKILL.md','paragraph-writing/SKILL.md','japanese-direct-writing/SKILL.md']),
                             (new,['SKILL.md','references/paragraphs.md','references/audience.md','references/directness.md','references/review.md'])]:
            for rel in names:
                p=folder/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('Rules '+rel)
        tasks=[{'id':'W01','instruction':'Rewrite','input':'Input','must_keep':['DO_NOT_LEAK_ANSWER']}]
        return up,old,new,tasks
    def test_balanced_preparation(self):
        up,old,new,tasks=self.setup_sources()
        r=self.module().prepare(tasks,up,old,new,self.home/'out',repeats=3)
        self.assertEqual(len(r['jobs']),9)
        self.assertEqual(set(j['arm'] for j in r['jobs']),{'upstream_only','existing_three_skills','proposal'})
        self.assertTrue(all(j['status']=='NOT_RUN' for j in r['jobs']))
    def test_answers_not_in_generation_prompt(self):
        up,old,new,tasks=self.setup_sources();out=self.home/'out'
        self.module().prepare(tasks,up,old,new,out)
        for p in (out/'prompts').glob('*'):
            self.assertNotIn('DO_NOT_LEAK_ANSWER',p.read_text())
    def test_prepare_existing_destination_refused(self):
        up,old,new,tasks=self.setup_sources();out=self.home/'out';out.mkdir()
        with self.assertRaises(ValueError):self.module().prepare(tasks,up,old,new,out)
    def test_preparation_deterministic(self):
        up,old,new,tasks=self.setup_sources();m=self.module()
        a=m.prepare(tasks,up,old,new,self.home/'out1');b=m.prepare(tasks,up,old,new,self.home/'out2')
        self.assertEqual(a,b)
    def test_task_id_path_rejected(self):
        up,old,new,tasks=self.setup_sources();tasks[0]['id']='../bad'
        with self.assertRaises(ValueError):self.module().prepare(tasks,up,old,new,self.home/'out')
