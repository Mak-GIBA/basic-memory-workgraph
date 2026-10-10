import base64
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bootstrap as b
import integrate


class PackagingTests(unittest.TestCase):
    def test_unknown_flag_rejected_before_download(self):
        with patch.object(b,'COMPONENT','design-research'), self.assertRaises(SystemExit):
            b.parse(['--updtae'])
    def test_design_installer_flags_preserved(self):
        with patch.object(b,'COMPONENT','design-research'):
            a,rest=b.parse(['--update','--skills-dir','path with spaces','--json'])
        self.assertEqual(rest,['--update','--skills-dir','path with spaces','--json'])
    def test_upstream_apply_update_skip_preserved(self):
        with patch.object(b,'COMPONENT','upstream'):
            a,rest=b.parse(['--apply','--update','--skip-specify'])
        self.assertEqual(rest,['--apply','--update','--skip-specify'])
    def test_bundle_and_install_flags_do_not_mix(self):
        with patch.object(b,'COMPONENT','design-research'), self.assertRaises(SystemExit):
            b.parse(['--bundle-self-test','--update'])
    def test_missing_option_value_rejected(self):
        with patch.object(b,'COMPONENT','design-research'), self.assertRaises(SystemExit):
            b.parse(['--project'])
    def test_embedded_bundle_digest_is_checked(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'installer.sh';data=b'example';p.write_bytes(b'header'+b.MARKER+base64.b64encode(data))
            with patch.object(b,'BUNDLE_SHA256',hashlib.sha256(data).hexdigest()):self.assertEqual(b.bundle(p),data)
            with patch.object(b,'BUNDLE_SHA256','0'*64),self.assertRaises(ValueError):b.bundle(p)
    def test_archive_traversal_rejected_without_output(self):
        bio=io.BytesIO()
        with zipfile.ZipFile(bio,'w') as z:z.writestr('codex_interface_upgrade/../../escape','bad')
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'out'
            with self.assertRaises(ValueError):b.extract(bio.getvalue(),out)
            self.assertFalse(out.exists())
    def test_symlink_archive_rejected(self):
        bio=io.BytesIO()
        with zipfile.ZipFile(bio,'w') as z:
            i=zipfile.ZipInfo('codex_interface_upgrade/link');i.external_attr=0o120777<<16;z.writestr(i,'outside')
        with tempfile.TemporaryDirectory() as t,self.assertRaises(ValueError):b.extract(bio.getvalue(),Path(t)/'out')
    def test_duplicate_archive_rejected(self):
        import warnings
        bio=io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(bio,'w') as z:z.writestr('codex_interface_upgrade/x','1');z.writestr('codex_interface_upgrade/x','2')
        with tempfile.TemporaryDirectory() as t,self.assertRaises(ValueError):b.extract(bio.getvalue(),Path(t)/'out')
    def test_incomplete_archive_rejected(self):
        bio=io.BytesIO()
        with zipfile.ZipFile(bio,'w') as z:z.writestr('codex_interface_upgrade/x','1')
        with tempfile.TemporaryDirectory() as t,self.assertRaises(ValueError):b.extract(bio.getvalue(),Path(t)/'out')
    def test_exact_anchor_patch_refuses_unrecognized_installer(self):
        with self.assertRaises(ValueError):integrate.patch_installer('def main(): pass\n')
    def test_output_symlink_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'real').mkdir();(root/'link').symlink_to(root/'real',target_is_directory=True)
            with self.assertRaises(ValueError):b.safe_path(root/'link'/'file')

if __name__=='__main__':unittest.main()
