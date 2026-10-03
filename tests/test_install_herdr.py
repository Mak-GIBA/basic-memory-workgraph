"""Installer checks in isolated homes; no real downloads or live Herdr sessions."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'install_herdr.sh'
FAKE_BINARY = '''#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if args == ['--version']:
    print('herdr 0.9.3')
elif '--help' in args:
    print('Usage: --json --cwd --focus workspace_id')
else:
    print(json.dumps(args))
'''


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='test-herdr-installer-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.home = root / "home with space ' quote"
        self.home.mkdir()
        self.bin = root / 'commands'
        self.bin.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('HERDR_')}
        self.env.update(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                        PATH=f'{self.bin}:/usr/local/bin:/usr/bin:/bin')
        self.rc = self.home / '.bashrc'
        self.rc.write_text('# existing configuration\nexport KEEP_ME=yes\n')
        self.payload = root / 'payload'
        self.payload.write_text(FAKE_BINARY)
        self.payload.chmod(0o755)
        self.env['FAKE_PAYLOAD'] = str(self.payload)
        self.env['CURL_LOG'] = str(root / 'curl.log')
        curl = self.bin / 'curl'
        curl.write_text('''#!/usr/bin/env python3
import os, pathlib, sys
pathlib.Path(os.environ['CURL_LOG']).write_text('called')
if os.environ.get('FAIL_DOWNLOAD'):
    sys.exit(22)
target = sys.argv[sys.argv.index('-o') + 1]
pathlib.Path(target).write_text('mkdir -p "$HERDR_INSTALL_DIR"\\ncp "$FAKE_PAYLOAD" "$HERDR_INSTALL_DIR/herdr"\\nchmod +x "$HERDR_INSTALL_DIR/herdr"\\n')
''')
        curl.chmod(0o755)

    def install(self, *args, success=True):
        result = subprocess.run(['bash', str(INSTALLER), *args], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def existing(self):
        binary = self.bin / 'herdr'
        binary.write_text(FAKE_BINARY)
        binary.chmod(0o755)
        return binary

    def test_dry_run_does_not_write_or_download(self):
        before = self.rc.read_bytes()
        self.install('--dry-run')
        self.assertEqual(self.rc.read_bytes(), before)
        self.assertFalse((self.home / '.local').exists())
        self.assertFalse(Path(self.env['CURL_LOG']).exists())

    def test_existing_binary_preserved_and_repeat_is_idempotent(self):
        binary = self.existing()
        digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        before = self.rc.read_bytes()
        self.install()
        wrapper = self.home / '.local/bin/herdr-open'
        first = (self.rc.read_bytes(), wrapper.read_bytes(), self.rc.stat().st_mtime_ns)
        backups = list(self.home.glob('.bashrc.before-herdr-open-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)
        self.install()
        self.assertEqual(first, (self.rc.read_bytes(), wrapper.read_bytes(), self.rc.stat().st_mtime_ns))
        self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), digest)
        self.assertFalse(Path(self.env['CURL_LOG']).exists())
        args = ['workspace', 'list', 'space and 日本語', '$(false)', "it's", '']
        result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                                 'source ' + shlex.quote(str(self.rc)) + '\nherdr ' + shlex.join(args)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), args)

    def test_initial_install_uses_official_installer_then_skips_on_repeat(self):
        self.install()
        binary = self.home / '.local/bin/herdr'
        self.assertEqual(binary.read_bytes(), self.payload.read_bytes())
        self.assertTrue(os.access(binary, os.X_OK))
        log = Path(self.env['CURL_LOG'])
        self.assertTrue(log.exists())
        log.unlink()
        self.install()
        self.assertFalse(log.exists())

    def test_failed_download_keeps_shell_config(self):
        self.env['FAIL_DOWNLOAD'] = '1'
        before = self.rc.read_bytes()
        self.install(success=False)
        self.assertEqual(self.rc.read_bytes(), before)
        self.assertFalse((self.home / '.local/bin/herdr').exists())
        self.assertFalse((self.home / '.local/bin/herdr-open').exists())

    def test_unmanaged_function_is_not_overwritten(self):
        self.rc.write_text('herdr() { echo custom; }\n')
        self.install(success=False)
        self.assertEqual(self.rc.read_text(), 'herdr() { echo custom; }\n')
        self.assertFalse(Path(self.env['CURL_LOG']).exists())

    def test_existing_managed_block_replaced_once(self):
        self.existing()
        self.rc.write_text('# before\n# >>> herdr-open: cwd workspace >>>\n'
                           'herdr() { echo old; }\n# <<< herdr-open: cwd workspace <<<\n# after\n')
        self.install()
        text = self.rc.read_text()
        self.assertEqual(text.count('# >>> herdr-open: cwd workspace >>>'), 1)
        self.assertNotIn('echo old', text)
        self.assertTrue(text.startswith('# before\n'))
        self.assertTrue(text.endswith('# after\n'))

    def test_symlinked_bashrc_and_explicit_binary(self):
        binary = self.existing()
        target = self.home / 'dotfile'
        self.rc.rename(target)
        self.rc.symlink_to(target)
        self.install('--binary', str(binary))
        self.assertTrue(self.rc.is_symlink())
        self.assertIn('herdr()', target.read_text())
        self.assertEqual(len(list(self.home.glob('dotfile.before-herdr-open-*'))), 1)


if __name__ == '__main__':
    unittest.main()
