"""Behavioral tests: fixtures are fictional and never enter real Basic Memory."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "tools/basic-memory-workgraph"
sys.path.insert(0, str(SOURCE))
import workgraph_tools as wg


def piece(text):
    return {"summary": text, "excerpt": None}


def case_data():
    return {
        "version": 1, "request": piece("Compare equivalent quantities"),
        "initial": piece("Different denominators were compared"),
        "corrections": [
            {"feedback": piece("Align denominators"), "change": piece("Recomputed values"), "result": None},
            {"feedback": piece("Label the units"), "change": piece("Added unit labels"), "result": piece("Consistent comparison")},
        ],
        "final": {"summary": "Comparable values", "excerpt": "A: 20 per 100; B: 30 per 100"},
        "outcome": "verified", "acceptance": "unknown",
        "checks": ["Recomputed both denominators"], "lessons": ["Preserve denominator definitions"],
        "transfer_use": "Comparisons in other reporting projects",
    }


class TransferTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.memory = self.base / "memory"
        self.memory.mkdir()
        self.output = self.base / "export"

    def args(self, **kwargs):
        return argparse.Namespace(memory_dir=self.memory, output=self.output, dry_run=False, **kwargs)

    def note(self, path="rules/units.md", body="\n## Observations\n- [action] Preserve unit definitions\n", **metadata):
        meta = {"title": Path(path).stem, "type": "rule", **metadata}
        note = wg.Note(path, meta, body)
        target = self.memory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(note.render())
        return path

    def case(self, data=None, **metadata):
        return self.note("cases/comparison.md", "\n## Interaction\n```json\n" + json.dumps(data or case_data(), ensure_ascii=False, indent=2) + "\n```\n",
                         type="case", capture_kind="interaction_case", case_format_version=1, **metadata)

    def review(self, note, sharing="private", training="excluded"):
        return wg.review(self.args(note=note, sharing=sharing, training=training))

    def test_legacy_private_and_unreviewed_never_export(self):
        self.note()
        self.note("rules/team.md", sharing_scope="team")
        self.note("rules/public.md", sharing_scope="public")
        result = wg.export_share(self.args(scope="team", include_cases=False))
        self.assertEqual(result["exported"], 0)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(json.loads((self.output / "manifest.json").read_text())["notes"], [])

    def test_contextual_corrections_are_private_and_not_training_cases(self):
        rel = self.note("corrections/briefing.md", type="correction", schema="Correction",
                        body="\n- [context] Decision briefing\n- [instruction] Compare first\n"
                             "- [desired_output] Table then recommendation\n- [scope] Current briefing\n"
                             "- [verification] unverified\n- [acceptance] unknown\n")
        self.assertEqual(wg.export_share(self.args(scope="team", include_cases=True))["exported"], 0)
        with self.assertRaises(wg.Invalid):
            self.review(rel, training="approved")
        self.output = self.base / "training.jsonl"
        self.assertEqual(wg.export_cases(self.args())["exported"], 0)
        self.assertEqual(self.output.read_text(), "")
        self.review(rel, sharing="team")
        self.output = self.base / "reviewed-correction"
        self.assertEqual(wg.export_share(self.args(scope="team", include_cases=False))["exported"], 1)
        self.assertIn("[verification] unverified", (self.output / rel).read_text())

    def test_review_invalidates_on_content_or_permission_change(self):
        rel = self.note()
        self.review(rel, "team")
        note = wg.load_note(self.memory, rel)
        self.assertTrue(note.reviewed())
        for change in ("body", "sharing_scope", "training_use", "title"):
            changed = copy.deepcopy(note)
            if change == "body":
                changed.body += "New content\n"
            else:
                changed.metadata[change] = "changed"
            self.assertFalse(changed.reviewed())
        (self.memory / rel).write_text(note.render() + "Additional content\n")
        self.assertEqual(wg.export_share(self.args(scope="team", include_cases=False))["exported"], 0)

    def test_secret_and_personal_data_rejected_before_review(self):
        for text in ("password: not-a-real-password", "person@example.test", "/home/person/private/file", "-----BEGIN PRIVATE KEY-----"):
            rel = self.note(body=text)
            before = (self.memory / rel).read_bytes()
            with self.assertRaises(wg.Invalid):
                self.review(rel, "public")
            self.assertEqual(before, (self.memory / rel).read_bytes())

    def test_markdown_roundtrip_private_links_removed_original_unchanged(self):
        private = self.note("rules/private.md", title="Private customer")
        shared = self.note("rules/units.md", title="Units", body="""
## Relations
- learned_from [[Private customer]]
- implements [[Other]]
Inline [[Private customer|confidential label]] and [internal](file:///internal/doc).
""")
        other = self.note("workflows/other.md", title="Other", type="workflow")
        for rel in (shared, other):
            self.review(rel, "team")
        before = {p: p.read_bytes() for p in self.memory.rglob("*.md")}
        result = wg.export_share(self.args(scope="team", include_cases=False))
        self.assertEqual(result["exported"], 2)
        exported = (self.output / shared).read_text()
        self.assertNotIn("Private customer", exported)
        self.assertNotIn("confidential label", exported)
        self.assertNotIn("file:///", exported)
        self.assertIn("[[workflows/other]]", exported)
        self.assertEqual(before, {p: p.read_bytes() for p in self.memory.rglob("*.md")})
        imported = self.base / "imported"
        args = argparse.Namespace(memory_dir=imported, bundle=self.output, dry_run=False)
        self.assertEqual(wg.import_share(args)["imported"], 2)
        meta = wg.load_note(imported, shared).metadata
        self.assertEqual((meta["sharing_scope"], meta["training_use"], meta["privacy_review"]), ("private", "excluded", "pending"))
        self.assertEqual(wg.import_share(args)["unchanged"], 2)
        (imported / shared).write_text("user edit")
        self.assertEqual(wg.import_share(args)["conflicts"], [shared])
        self.assertEqual((imported / shared).read_text(), "user edit")
        self.assertFalse((imported / private).exists())

    def test_case_sharing_requires_flag_and_training_is_independent(self):
        rel = self.case()
        self.review(rel, "team", "excluded")
        self.assertEqual(wg.export_share(self.args(scope="team", include_cases=False))["exported"], 0)
        self.output = self.base / "with-cases"
        self.assertEqual(wg.export_share(self.args(scope="team", include_cases=True))["exported"], 1)
        self.output = self.base / "training.jsonl"
        self.assertEqual(wg.export_cases(self.args())["exported"], 0)
        self.assertEqual(self.output.read_text(), "")
        self.review(rel, "private", "approved")
        self.output = self.base / "private-share"
        self.assertEqual(wg.export_share(self.args(scope="team", include_cases=True))["exported"], 0)
        self.output = self.base / "approved.jsonl"
        self.assertEqual(wg.export_cases(self.args())["exported"], 1)
        row = json.loads(self.output.read_text())
        self.assertEqual(row["interaction"], case_data())
        self.assertEqual(row["interaction"]["acceptance"], "unknown")
        self.assertNotIn(str(self.memory), self.output.read_text())

    def test_freeform_cases_and_incomplete_or_unknown_formats_are_not_training(self):
        for mutator in (
            lambda d: d.update(version=2), lambda d: d.pop("initial"),
            lambda d: d.update(outcome="verified", checks=[]),
            lambda d: d.update(corrections="not ordered"),
            lambda d: d.update(request={"summary": "a", "raw_transcript": "no"}),
        ):
            data = case_data()
            mutator(data)
            rel = self.case(data)
            with self.assertRaises(wg.Invalid):
                self.review(rel, training="approved")
        rel = self.note("cases/legacy.md", "Old freeform case", type="case")
        with self.assertRaises(wg.Invalid):
            self.review(rel, training="approved")

    def test_partial_and_unknown_evidence_remain_unmodified(self):
        data = case_data()
        data.update(initial=None, outcome="partial", checks=[])
        rel = self.case(data)
        self.review(rel, training="approved")
        self.output = self.base / "partial.jsonl"
        wg.export_cases(self.args())
        self.assertEqual(json.loads(self.output.read_text())["interaction"], data)

    def test_shared_case_links_are_redacted_without_corrupting_json(self):
        data = case_data()
        data["final"]["excerpt"] = "See [[Quoted]] and [[Private reference]]"
        rel = self.case(data)
        linked = self.note('rules/unit"quote.md', title="Quoted")
        self.note("rules/private.md", title="Private reference")
        self.review(rel, "team")
        self.review(linked, "team")
        wg.export_share(self.args(scope="team", include_cases=True))
        result = wg.interaction(wg.load_note(self.output, rel))
        self.assertEqual(result["final"]["excerpt"], 'See [[rules/unit"quote]] and [omitted]')
        self.assertNotIn("Private reference", (self.output / rel).read_text())

    def test_decoded_case_excerpts_are_privacy_screened(self):
        rel = self.case()
        path = self.memory / rel
        encoded = "".join("\\u%04x" % ord(c) for c in "person@example.test")
        path.write_text(path.read_text().replace("A: 20 per 100; B: 30 per 100", encoded))
        with self.assertRaises(wg.Invalid):
            self.review(rel, training="approved")
        # Even a manually forged review stamp does not bypass export screening.
        note = wg.load_note(self.memory, rel)
        note.metadata.update(training_use="approved", privacy_review="passed")
        note.metadata["review_sha256"] = note.fingerprint()
        path.write_text(note.render())
        result = wg.export_cases(self.args())
        self.assertEqual(result["exported"], 0)
        self.assertEqual(self.output.read_text(), "")

    def test_sensitive_filename_not_echoed_in_skip_report(self):
        rel = self.note("rules/person@example.test.md", title="Safe title", sharing_scope="team")
        result = wg.export_share(self.args(scope="team", include_cases=False))
        self.assertNotIn("person@example.test", json.dumps(result))
        self.assertTrue(result["skipped"][0]["note"].startswith("sha256:"))

    def test_duplicate_yaml_json_and_unsafe_yaml_rejected(self):
        for content in ("title: a\ntitle: b\ntype: rule", "title: a\ntype: !!python/object:danger {}",
                        "title: &a test\ntype: *a"):
            with self.assertRaises(wg.Invalid):
                wg.parse_note("---\n" + content + "\n---\nbody", "rules/a.md")
        with self.assertRaises(wg.Invalid):
            wg.strict_json('{"a":1,"a":2}')
        with self.assertRaises(wg.Invalid):
            wg.strict_json('{"a":NaN}')

    def make_bundle(self):
        rel = self.note()
        self.review(rel, "team")
        wg.export_share(self.args(scope="team", include_cases=False))
        return argparse.Namespace(memory_dir=self.base / "imported", bundle=self.output, dry_run=False)

    def test_import_rejects_traversal_extra_files_symlinks_and_tampering(self):
        args = self.make_bundle()
        manifest_path = self.output / "manifest.json"
        original = manifest_path.read_text()
        for path in ("../outside.md", "/etc/passwd", "rules/../../outside.md", "rules\\other.md", "schemas/Case.md"):
            manifest = json.loads(original)
            manifest["notes"][0]["path"] = path
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(wg.Invalid):
                wg.import_share(args)
            self.assertFalse(args.memory_dir.exists())
        manifest_path.write_text(original)
        extra = self.output / "unlisted.py"
        extra.write_text("print('no execution')")
        with self.assertRaises(wg.Invalid):
            wg.import_share(args)
        extra.unlink()
        target = self.output / "rules/units.md"
        content = target.read_text()
        target.write_text(content + "tampered")
        with self.assertRaises(wg.Invalid):
            wg.import_share(args)
        target.unlink()
        target.symlink_to(self.memory / "rules/units.md")
        with self.assertRaises(wg.Invalid):
            wg.import_share(args)
        self.assertFalse(args.memory_dir.exists())

    def test_import_preflights_entire_bundle_before_writing(self):
        first = self.note("rules/a.md")
        last = self.note("rules/z.md")
        for rel in (first, last):
            self.review(rel, "team")
        wg.export_share(self.args(scope="team", include_cases=False))
        (self.output / last).write_text("tampered")
        dest = self.base / "imported"
        with self.assertRaises(wg.Invalid):
            wg.import_share(argparse.Namespace(memory_dir=dest, bundle=self.output, dry_run=False))
        self.assertFalse(dest.exists())

    def test_dry_runs_do_not_write_and_existing_outputs_are_never_overwritten(self):
        rel = self.note()
        before = (self.memory / rel).read_bytes()
        args = self.args(note=rel, sharing="team", training="excluded")
        args.dry_run = True
        wg.review(args)
        self.assertEqual(before, (self.memory / rel).read_bytes())
        self.review(rel, "team")
        args = self.args(scope="team", include_cases=False)
        args.dry_run = True
        wg.export_share(args)
        self.assertFalse(self.output.exists())
        args.dry_run = False
        wg.export_share(args)
        with self.assertRaises(wg.Invalid):
            wg.export_share(args)
        imported = self.base / "imported"
        wg.import_share(argparse.Namespace(memory_dir=imported, bundle=self.output, dry_run=True))
        self.assertFalse(imported.exists())

    def test_export_destination_inside_memory_or_symlink_is_rejected(self):
        self.note()
        for output in (self.memory / "out", self.memory):
            self.output = output
            with self.assertRaises(wg.Invalid):
                wg.export_cases(self.args())
        link = self.base / "linked"
        link.symlink_to(self.memory, target_is_directory=True)
        self.output = link / "out"
        with self.assertRaises(wg.Invalid):
            wg.export_cases(self.args())

    def test_cli_skipped_items_have_nonzero_exit_and_no_secret_content(self):
        self.note(sharing_scope="team")
        result = subprocess.run([sys.executable, str(SOURCE / "workgraph_tools.py"), "export-share",
                                 "--memory-dir", str(self.memory), "--scope", "team", "--output", str(self.output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["exported"], 0)


class SkillTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.codex = self.base / "codex"
        config = self.codex / "basic-memory-workgraph/config.json"
        config.parent.mkdir(parents=True)
        config.write_text('{"mode":"smart","skillMode":"auto"}')
        self.source = self.base / "staged"
        self.source.mkdir()
        self.skill = self.source / "SKILL.md"
        self.skill.write_text("---\nname: compare-units\ndescription: Compare measured values with compatible denominators\n---\nVerify denominators before computing a comparison.\n")
        self.validation = self.base / "review.json"
        self.args = argparse.Namespace(source=self.source, name="compare-units", workflow="workflows/compare-units",
                                       validation=self.validation, codex_dir=self.codex, dry_run=False)
        self.attest()

    def attest(self, decision="create_skill"):
        self.validation.write_text(json.dumps({"reviewer": "fixture-creator", "decision": decision,
            "passed": True, "checks": ["Compared fixture outputs with consistent denominators"],
            "source_sha256": wg.skill_digest(self.args)["source_sha256"]}))

    def test_registration_idempotence_and_managed_update(self):
        self.assertEqual(wg.register_skill(self.args)["registered"], 1)
        target = self.codex / "skills/compare-units"
        self.assertEqual((target / "SKILL.md").read_text(), self.skill.read_text())
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in target.rglob("*") if p.is_file()}
        self.assertEqual(wg.register_skill(self.args)["unchanged"], 1)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in target.rglob("*") if p.is_file()})
        self.skill.write_text(self.skill.read_text() + "Handle missing denominators as unknown.\n")
        self.attest("update_existing")
        self.assertEqual(wg.register_skill(self.args)["registered"], 1)
        self.assertIn("unknown", (target / "SKILL.md").read_text())
        manifest = json.loads((target / wg.SKILL_MANIFEST).read_text())
        self.assertEqual(manifest["workflow"], self.args.workflow)

    def test_absent_failed_or_stale_validation_cannot_register(self):
        valid = self.validation.read_text()
        for change in ({"passed": False}, {"checks": []}, {"reviewer": ""}, {"source_sha256": "old"}):
            data = json.loads(valid)
            data.update(change)
            self.validation.write_text(json.dumps(data))
            with self.assertRaises(wg.Invalid):
                wg.register_skill(self.args)
            self.assertFalse((self.codex / "skills").exists())
        self.validation.write_text(valid)
        self.skill.write_text(self.skill.read_text() + "changed after review\n")
        with self.assertRaises(wg.Invalid):
            wg.register_skill(self.args)

    def test_unmanaged_and_user_modified_skills_are_preserved(self):
        target = self.codex / "skills/compare-units"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("user-owned")
        with self.assertRaises((wg.Invalid, OSError)):
            wg.register_skill(self.args)
        self.assertEqual((target / "SKILL.md").read_text(), "user-owned")
        (target / "SKILL.md").unlink()
        target.rmdir()
        wg.register_skill(self.args)
        (target / "SKILL.md").write_text("user edit")
        with self.assertRaises(wg.Invalid):
            wg.register_skill(self.args)
        self.assertEqual((target / "SKILL.md").read_text(), "user edit")

    def test_modes_and_wrong_origin_prohibit_registration(self):
        config = self.codex / "basic-memory-workgraph/config.json"
        for mode, skill in (("off", "auto"), ("smart", "review"), ("smart", "off"), ("invalid", "auto")):
            config.write_text(json.dumps({"mode": mode, "skillMode": skill}))
            with self.assertRaises(wg.Invalid):
                wg.register_skill(self.args)
        config.write_text('{"mode":"smart","skillMode":"auto"}')
        wg.register_skill(self.args)
        self.args.workflow = "workflows/unrelated"
        with self.assertRaises(wg.Invalid):
            wg.register_skill(self.args)

    def test_symlinks_rejected_and_dry_run_does_not_register(self):
        self.args.dry_run = True
        wg.register_skill(self.args)
        self.assertFalse((self.codex / "skills").exists())
        (self.source / "outside").symlink_to(self.validation)
        with self.assertRaises(wg.Invalid):
            wg.register_skill(self.args)

    def test_failed_swap_restores_previous_skill(self):
        wg.register_skill(self.args)
        target = self.codex / "skills/compare-units"
        original = (target / "SKILL.md").read_bytes()
        self.skill.write_text(self.skill.read_text() + "More precise checks.\n")
        self.attest("update_existing")
        rename = Path.rename
        def fail_publish(path, destination):
            if path.name.startswith(".workgraph-skill-"):
                raise OSError("simulated publication failure")
            return rename(path, destination)
        with patch.object(Path, "rename", fail_publish), self.assertRaises(OSError):
            wg.register_skill(self.args)
        self.assertEqual((target / "SKILL.md").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
