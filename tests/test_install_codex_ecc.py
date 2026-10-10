"""Run the public Bash installer against a native Codex fixture, without downloads."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / "install_codex_ecc.sh"
CONFIG = '''# user setting
model = "keep-model"
[plugins."codex@basic-memory"]
enabled = true
[mcp_servers.chrome-devtools]
command = "keep-browser"
'''
FAKE_CODEX = r'''#!/usr/bin/env python3
import json,os,pathlib,sys,tomllib
home=pathlib.Path(os.environ['CODEX_HOME'])
fixture=home/'fixture.json'
state=json.loads(fixture.read_text())
args=sys.argv[1:]
with (home/'calls.jsonl').open('a') as stream:
 stream.write(json.dumps({'args':args})+'\n')
def save(): fixture.write_text(json.dumps(state))
def cache(version):
 root=home/'plugins/cache/ecc/ecc'/version
 manifest=root/'.codex-plugin/plugin.json'
 manifest.parent.mkdir(parents=True,exist_ok=True)
 manifest.write_text(json.dumps({'name':'ecc','version':version}))
 for name in ['python-patterns','error-handling','security-review','api-design','database-migrations']:
  folder=root/'skills'/name
  (folder/'references').mkdir(parents=True,exist_ok=True)
  (folder/'SKILL.md').write_text('---\nname: '+name+'\ndescription: '+name+'\n---\nFixture body\n')
  (folder/'references/example.md').write_text('Relative reference')
def enable():
 path=home/'config.toml'
 text=path.read_text()
 header='[plugins."ecc@ecc"]'
 prefix,tail=text.split(header,1)
 section,sep,rest=tail.partition('\n[')
 section=section.replace('enabled = false','enabled = true')
 path.write_text(prefix+header+section+sep+rest)
def fail(stage):
 if state.get('fail_stage')==stage:
  print('fixture '+stage+' failed after native mutation',file=sys.stderr)
  sys.exit(7)
def plugin(installed):
 return {'pluginId':'ecc@ecc','name':'ecc','marketplaceName':'ecc',
         'installed':installed,'version':state.get('version','1.0.0'),
         'marketplaceSource':{'sourceType':'git','source':state.get('market_source','https://github.com/affaan-m/ECC.git')},
         'installPolicy':state.get('install_policy','AVAILABLE')}
if args[-2:]==['app-server','--stdio']:
 override='plugins.ecc@ecc.enabled=true' in args
 config=tomllib.loads((home/'config.toml').read_text())
 enabled=config.get('plugins',{}).get('ecc@ecc',{}).get('enabled',False)
 for line in sys.stdin:
  request=json.loads(line)
  with (home/'calls.jsonl').open('a') as stream: stream.write(json.dumps({'rpc':request['method']})+'\n')
  if 'id' not in request: continue
  if state.get('fail_rpc'):
   print(json.dumps({'id':request['id'],'error':{'code':-1,'message':'fixture RPC failed'}}),flush=True)
   continue
  if request['method']=='initialize': result={}
  elif request['method']=='skills/list':
   skills=[]
   if state.get('installed') and (override or enabled):
    root=home/'plugins/cache/ecc/ecc'/state.get('version','1.0.0')
    for name in ['python-patterns','error-handling','security-review','api-design','database-migrations']:
     skills.append({'name':'ecc:'+name,'description':name,'path':str(root/'skills'/name/'SKILL.md'),
                    'enabled':True,'pluginId':'ecc@ecc'})
   for name in ['ecc-python','ecc-errors','ecc-security','ecc-library']:
    path=pathlib.Path(state['skills_root'])/name/'SKILL.md'
    if path.is_file(): skills.append({'name':name,'path':str(path),'enabled':True})
   result={'data':[{'cwd':request['params']['cwds'][0],'skills':skills,'errors':[]}]}
  else: raise RuntimeError('No model/thread calls are allowed')
  print(json.dumps({'id':request['id'],'result':result}),flush=True)
elif args==['plugin','marketplace','list','--json']:
 entries=[]
 if state.get('market_present'):
  entries=[{'name':'ecc','marketplaceSource':{'sourceType':'git','source':state.get('market_source','https://github.com/affaan-m/ECC.git')}}]
 print(json.dumps({'marketplaces':entries}))
elif args==['plugin','marketplace','add','affaan-m/ECC','--json']:
 state['market_present']=True;save();fail('marketplace_add');print('{}')
elif args==['plugin','marketplace','upgrade','ecc','--json']:
 state['version']='2.0.0';save();cache('2.0.0');enable();fail('upgrade');print('{}')
elif args in (['plugin','list','--json'],['plugin','list','--available','--json']):
 installed=[plugin(True)] if state.get('installed') else []
 available=[]
 if '--available' in args and not installed and state.get('market_present') and not state.get('hide_available'):
  available=[plugin(False)]
 print(json.dumps({'installed':installed,'available':available}))
elif args==['plugin','add','ecc@ecc','--json']:
 state['installed']=True;save();cache(state.get('version','1.0.0'));enable()
 if state.get('late_collision'):
  path=pathlib.Path(state['skills_root'])/'ecc-errors'
  path.mkdir(parents=True,exist_ok=True);(path/'SKILL.md').write_text('user-owned collision')
 fail('plugin_add');print('{}')
else:
 print('Unexpected command: '+str(args),file=sys.stderr);sys.exit(9)
'''


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ecc-installer-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "space and 'quote $dollar"
        self.home = self.root / "codex home"
        self.home.mkdir(parents=True)
        self.skills = self.root / "skills root"
        self.config = self.home / "config.toml"
        self.config.write_text(CONFIG)
        self.binary = self.root / "native codex"
        self.binary.write_text(FAKE_CODEX)
        self.binary.chmod(0o755)
        self.fixture = self.home / "fixture.json"
        self.fixture.write_text(json.dumps({'skills_root': str(self.skills)}))
        self.env = {**os.environ, 'HOME': str(self.root), 'CODEX_HOME': str(self.home)}
        self.state_path = self.home / "ecc-on-demand/state.json"

    def run_installer(self, *args, success=True):
        result = subprocess.run(['bash', str(INSTALLER), '--codex', str(self.binary),
                                 '--codex-home', str(self.home), '--skills-root', str(self.skills),
                                 '--cwd', str(self.root), '--json', *args], cwd=self.root,
                                env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return json.loads(result.stdout or result.stderr)

    def fixture_update(self, **values):
        state = json.loads(self.fixture.read_text())
        state.update(values)
        self.fixture.write_text(json.dumps(state))

    def calls(self):
        path = self.home / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def enabled(self):
        return tomllib.loads(self.config.read_text()).get('plugins', {}).get('ecc@ecc', {}).get('enabled')

    def preinstall(self):
        self.run_installer('--apply')
        self.run_installer('--restore', '--apply')
        self.config.write_text(CONFIG + '\n[plugins."ecc@ecc"]\nenabled = true\n')
        (self.home / 'calls.jsonl').unlink()

    def test_default_and_dry_run_are_offline_and_do_not_write(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(self.run_installer()['status'], 'planned')
        self.assertEqual(self.run_installer('--dry-run')['status'], 'planned')
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertFalse(self.calls())
        self.assertFalse((self.home / 'ecc-on-demand').exists())

    def test_fresh_install_preserves_other_settings_and_restore_keeps_cache_disabled(self):
        report = self.run_installer('--apply')
        self.assertEqual(report['status'], 'ready')
        self.assertFalse(self.enabled())
        state = json.loads(self.state_path.read_text())
        self.assertEqual(Path(state['backup']).read_text(), CONFIG)
        self.assertEqual(Path(state['backup']).stat().st_mode & 0o777, 0o600)
        self.assertFalse(state['previous_enabled'])
        parsed = tomllib.loads(self.config.read_text())
        self.assertTrue(parsed['plugins']['codex@basic-memory']['enabled'])
        self.assertEqual(parsed['mcp_servers']['chrome-devtools']['command'], 'keep-browser')
        self.config.write_text(self.config.read_text()+'\n[added_after_install]\nkeep = true\n')
        self.run_installer('--restore', '--apply')
        self.assertFalse(self.enabled())
        self.assertTrue((self.home/'plugins/cache/ecc/ecc/1.0.0').is_dir())
        self.assertTrue(tomllib.loads(self.config.read_text())['added_after_install']['keep'])
        self.assertFalse(any(c.get('rpc','').startswith(('thread/','turn/')) for c in self.calls()))

    def test_mcp_preview_selection_and_invalid_name_are_offline(self):
        before = self.config.read_bytes()
        report = self.run_installer('--mcps', 'recommended,cloudflare')
        self.assertEqual(report['selected_mcps'], ['context7', 'playwright', 'cloudflare-docs'])
        self.assertEqual(report['recommended_mcps'], ['context7', 'playwright'])
        error = self.run_installer('--apply', '--mcps', 'unknown', success=False)
        self.assertIn('Unknown MCP selection', error['error'])
        self.assertFalse(self.calls())
        self.assertEqual(self.config.read_bytes(), before)

    def test_mcp_selection_survives_update_and_none_preserves_old_connections(self):
        self.run_installer('--apply', '--mcps', 'research,cloudflare')
        initial = tomllib.loads(self.config.read_text())['mcp_servers']
        self.assertEqual(set(initial), {'context7', 'parallel-search', 'cloudflare-docs', 'chrome-devtools'})
        self.run_installer('--update', '--apply')
        self.assertEqual(tomllib.loads(self.config.read_text())['mcp_servers'], initial)
        self.run_installer('--update', '--apply', '--mcps', 'none')
        self.assertEqual(tomllib.loads(self.config.read_text())['mcp_servers'], initial)
        self.assertEqual(self.run_installer('--update')['selected_mcps'], [])
        self.run_installer('--restore', '--apply')
        self.assertEqual(tomllib.loads(self.config.read_text())['mcp_servers'], {'chrome-devtools': {'command': 'keep-browser'}})

    def test_existing_native_install_has_no_download_and_restores_initial_enabled(self):
        self.preinstall()
        original = self.config.read_bytes()
        self.run_installer('--apply')
        state = json.loads(self.state_path.read_text())
        self.assertTrue(state['previous_enabled'])
        self.assertEqual(Path(state['backup']).read_bytes(), original)
        commands = [c['args'] for c in self.calls() if 'args' in c]
        self.assertFalse(any('add' in command or 'upgrade' in command for command in commands))
        self.run_installer('--restore', '--apply')
        self.assertTrue(self.enabled())

    def test_reapply_is_idempotent_and_keeps_initial_backup(self):
        self.run_installer('--apply')
        state = json.loads(self.state_path.read_text())
        before = self.config.read_bytes()
        report = self.run_installer('--apply')
        self.assertEqual(report['apply']['changed_files'], 0)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(json.loads(self.state_path.read_text())['backup'], state['backup'])
        adds = [c for c in self.calls() if c.get('args')==['plugin','add','ecc@ecc','--json']]
        self.assertEqual(len(adds), 1)

    def test_update_follows_new_native_catalog_and_keeps_old_cache(self):
        self.run_installer('--apply')
        report = self.run_installer('--update', '--apply')
        self.assertEqual(report['status'], 'ready')
        self.assertEqual(report['original_versions'], ['2.0.0'])
        self.assertFalse(self.enabled())
        self.assertTrue((self.home/'plugins/cache/ecc/ecc/1.0.0').is_dir())
        self.assertTrue((self.home/'plugins/cache/ecc/ecc/2.0.0').is_dir())
        commands = [c['args'] for c in self.calls() if 'args' in c]
        self.assertIn(['plugin','marketplace','upgrade','ecc','--json'], commands)

    def test_native_add_failure_stays_disabled_and_retry_keeps_first_baseline(self):
        self.fixture_update(fail_stage='plugin_add')
        result = self.run_installer('--apply', success=False)
        self.assertIn('fixture plugin_add failed', result['error'])
        self.assertFalse(self.enabled())
        backup = Path(result['backup'])
        self.assertEqual(backup.read_text(), CONFIG)
        self.assertFalse(self.state_path.exists())
        self.fixture_update(fail_stage='')
        self.run_installer('--apply')
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state['backup'], str(backup))
        self.assertFalse(state['previous_enabled'])
        self.assertFalse((self.home/'ecc-on-demand/bootstrap.json').exists())

    def test_existing_enabled_baseline_survives_apply_failure_and_retry(self):
        self.preinstall()
        self.fixture_update(fail_rpc=True)
        result = self.run_installer('--apply', success=False)
        self.assertFalse(self.enabled())
        self.assertIn('fixture RPC failed', result['error'])
        self.fixture_update(fail_rpc=False)
        self.run_installer('--apply')
        state = json.loads(self.state_path.read_text())
        self.assertTrue(state['previous_enabled'])
        self.assertEqual(state['backup'], result['backup'])
        self.run_installer('--restore','--apply')
        self.assertTrue(self.enabled())

    def test_late_collision_is_preserved_and_retry_reuses_fresh_install_baseline(self):
        self.fixture_update(late_collision=True)
        result = self.run_installer('--apply',success=False)
        path = self.skills/'ecc-errors/SKILL.md'
        self.assertEqual(path.read_text(), 'user-owned collision')
        self.assertFalse(self.enabled())
        path.unlink();path.parent.rmdir()
        self.fixture_update(late_collision=False)
        self.run_installer('--apply')
        state = json.loads(self.state_path.read_text())
        self.assertFalse(state['previous_enabled'])
        self.assertEqual(state['backup'], result['backup'])

    def test_install_without_an_existing_config_creates_private_config(self):
        self.config.unlink()
        self.run_installer('--apply')
        self.assertFalse(self.enabled())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        state = json.loads(self.state_path.read_text())
        self.assertEqual(Path(state['backup']).read_bytes(), b'')

    def test_marketplace_failure_can_retry_without_losing_original_backup(self):
        self.fixture_update(fail_stage='marketplace_add')
        result = self.run_installer('--apply', success=False)
        self.assertFalse(self.enabled())
        self.fixture_update(fail_stage='')
        self.run_installer('--apply')
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state['backup'], result['backup'])

    def test_upgrade_failure_restores_disabled_setting(self):
        self.run_installer('--apply')
        self.fixture_update(fail_stage='upgrade')
        result = self.run_installer('--update','--apply',success=False)
        self.assertFalse(self.enabled())
        self.assertTrue(result['ecc_disabled'])
        self.fixture_update(fail_stage='')
        self.assertEqual(self.run_installer('--update','--apply')['status'], 'ready')

    def test_foreign_marketplace_is_preserved_before_any_config_change(self):
        self.fixture_update(market_present=True,market_source='https://example.invalid/other.git')
        before = self.config.read_bytes()
        self.run_installer('--apply',success=False)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse(any('add' in c.get('args',[]) for c in self.calls()))
        self.assertFalse(self.state_path.exists())

    def test_unmanaged_skill_and_invalid_toml_stop_before_codex_calls(self):
        path = self.skills/'ecc-python'
        path.mkdir(parents=True)
        (path/'SKILL.md').write_text('user-owned')
        self.run_installer('--apply',success=False)
        self.assertFalse(self.calls())
        (path/'SKILL.md').unlink();path.rmdir()
        self.config.write_text('this is not valid TOML')
        self.run_installer('--apply',success=False)
        self.assertFalse(self.calls())

    def test_edited_managed_file_blocks_update_before_native_mutation(self):
        self.run_installer('--apply')
        edited = self.skills/'ecc-python/SKILL.md'
        edited.write_text('user edited this')
        before = len(self.calls())
        self.run_installer('--update','--apply',success=False)
        self.assertEqual(len(self.calls()), before)
        self.assertEqual(edited.read_text(), 'user edited this')

    def test_missing_original_reports_error_and_preserves_disabled(self):
        self.run_installer('--apply')
        path = self.home/'plugins/cache/ecc/ecc/1.0.0/skills/python-patterns/SKILL.md'
        path.unlink()
        report = self.run_installer('--doctor',success=False)
        self.assertTrue(any('missing' in issue for issue in report['issues']))
        self.assertFalse(self.enabled())

    def test_hidden_catalog_and_denied_install_policy_do_not_guess_another_plugin(self):
        for overrides in ({'hide_available':True},{'hide_available':False,'install_policy':'NOT_AVAILABLE'}):
            self.fixture_update(**overrides)
            self.run_installer('--apply',success=False)
            self.assertFalse(self.enabled())
            self.assertFalse(any(c.get('args')==['plugin','add','ecc@ecc','--json'] for c in self.calls()))

    def test_update_requires_managed_install_and_restore_requires_completed_bootstrap(self):
        self.run_installer('--update','--apply',success=False)
        self.assertFalse(self.calls())
        self.fixture_update(fail_stage='plugin_add')
        self.run_installer('--apply',success=False)
        path = self.home/'ecc-on-demand/bootstrap.json'
        before = path.read_bytes()
        self.run_installer('--restore','--apply',success=False)
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
