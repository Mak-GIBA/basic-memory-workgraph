"""V2 orchestration regression fixtures, not measurements of model effectiveness.

Model replies are explicit fixtures. Parent execution, receipts, grading, evidence
validation, persistence and replay protection use the real implementation. Tiny
stdlib commands run in disposable directories with the sandbox launcher bypassed;
these tests do not establish the operating system's isolation properties.
"""
from __future__ import annotations

import copy
import json
from unittest.mock import patch
import unittest

import test_stages as stages
from test_effectiveness import contract
import harness as h
import runtime as rt


class BoundedPipelineTests(unittest.TestCase):
    def setUp(self):
        stages.StageTests.setUp(self)
        self.state.update(execution_contract_version=2, role_contract_version=1)
        self.state["config"].update(
            allow_network=False, test_commands=[], target_methods=5,
            url="", start_command="",
        )
        self.plan = self.state.pop("plan")
        self.plan.update(
            status="ready", reason="Explicit orchestration fixture",
            constraints=[], complexity_baseline="No change", queries=[],
        )
        self.state.pop("evaluation_contract")
        self.state.pop("evaluation_contract_sha256")
        self.calls = []

    def project_files(self, files):
        for name, text in files.items():
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.state["expected_source"] = rt.fingerprint(self.project, self.workspace)

    def backend_mode(self, mode, criteria, commands=()):
        self.state["config"]["mode"] = mode
        self.state.pop("evaluation_contract_version", None)
        self.plan.pop("evaluation_json", None)
        self.plan.update(domain="backend", criteria=criteria, test_commands=list(commands))

    def default_reply(self, role, state):
        if role == "planner":
            return copy.deepcopy(self.plan)
        if role in ("producer-design", "producer-results"):
            return copy.deepcopy(self.design)
        if role == "producer-assets":
            return copy.deepcopy(self.assets)
        if role == "producer-evidence":
            draft = json.loads(state["proposal_design"]["dossier_json"])
            cid = state["unit_task"]["candidate_id"]
            return {
                "status": "proposed", "reason": "Explicit candidate fixture",
                "patch_json": json.dumps({
                    "sources": [], "claims": [],
                    "candidate": next(c for c in draft["candidates"] if c["id"] == cid),
                    "comparison": [c for c in draft["comparison"] if c["candidate_id"] == cid],
                }),
                "sources": [],
            }
        value = copy.deepcopy(self.review)
        value.update(checks=[], issues=[], code_evidence=[], sources=[])
        if role == "reviewer-check":
            value["dossier_json"] = ""
            value["checks"] = [
                {"check_id": cid, "result": "unknown",
                 "reason": "Fixture makes no runtime assertion", "evidence_ids": []}
                for cid in state["unit_task"]["criterion_ids"]
            ]
        elif role == "reviewer-dossier":
            value["dossier_json"] = state["proposal_design"]["dossier_json"]
        else:
            raise AssertionError("Unexpected fixture role: " + role)
        return value

    def drive(self, replies=None):
        def invoke(role, schema, state, workspace, run_dir, validator=None):
            task = copy.deepcopy(state.get("unit_task") or {})
            self.calls.append((state["iteration"], role, task))
            value = (replies or self.default_reply)(role, state)
            h.validate_shape(value, schema)
            h.normalize_unit_paths(value, state, workspace, run_dir)
            if validator:
                validator(value, state)
            return value

        with patch.object(h, "checked_role", side_effect=invoke), patch.object(
            h, "sandbox_command", side_effect=lambda _sandbox, _network, argv: argv
        ):
            h.loop(self.state, self.workspace, self.run)

    def role_count(self, role, candidate=None):
        return sum(
            r == role and (candidate is None or task.get("candidate_id") == candidate)
            for _iteration, r, task in self.calls
        )

    def current_executions(self, state):
        return [
            r for r in state["evidence"].values()
            if r["kind"] in ("test", "experiment") and r["iteration"] == state["iteration"]
        ]

    def test_design_only_completes_without_artificial_execution(self):
        with patch.object(h, "capture", side_effect=AssertionError("No experiment was requested")):
            self.drive()
        self.assertEqual(self.state["status"], "research_complete")
        self.assertEqual(self.state["evaluation_summary"]["status"], "unmeasured")
        self.assertEqual(self.current_executions(self.state), [])
        self.assertEqual(self.role_count("producer-evidence"), 2)
        self.assertTrue(all(row["status"] == "complete" for row in self.state["units"].values()))
        # Preliminary grading diagnostics must not turn an unmeasured design
        # into a measured/proposed result or mutate saved decisions.
        invalid = copy.deepcopy(self.state)
        draft = json.loads(invalid['proposal_design']['dossier_json'])
        draft['decision']['status'] = 'proposed'
        invalid['proposal_design']['dossier_json'] = json.dumps(draft)
        before = copy.deepcopy(invalid)
        task = h.dossier_review_task(invalid, self.workspace)
        self.assertIn('Unmeasured effects need a provisional/deferred decision',
                      task['known_ledger_errors'])
        self.assertEqual(invalid, before)
        self.assertEqual(task['current_exported_artifacts'], [])
        # A failed access receipt remains failed even if a later independent
        # qualitative review passes. Final review gets the unresolved source ID.
        unavailable = copy.deepcopy(self.state)
        draft = json.loads(unavailable['proposal_design']['dossier_json'])
        draft['claims'] = [{'id': 'C1', 'status': 'reported',
                            'evidence': [{'source_id': 'MISSING', 'relation': 'supports'}]}]
        unavailable['proposal_design']['dossier_json'] = json.dumps(draft)
        before = copy.deepcopy(unavailable)
        task = h.dossier_review_task(unavailable, self.workspace)
        self.assertIn('Decisive source unavailable: MISSING', task['known_ledger_errors'])
        self.assertEqual(unavailable, before)

    def test_scoped_source_locators_do_not_overwrite_existing_identity(self):
        self.state['plan']=copy.deepcopy(self.plan)
        source=self.workspace/'original.txt';source.write_text('Actual primary passage\n')
        original={'id':'S1','title':'Primary passage','url':'','path':'original.txt',
                  'locator':'Original locator','read_level':'relevant_sections'}
        h.collect_sources([original],self.state,self.workspace,self.run)
        self.state['unit_task']={'criterion_ids':['R1']}
        value=self.default_reply('reviewer-check',self.state)
        value['checks'][0].update(result='pass',evidence_ids=[next(iter(self.state['evidence']))])
        value['sources']=[{**original,'locator':'Independent decisive locator'}]
        h.scoped_review_format(value,self.state)
        self.assertEqual(self.state['sources']['S1']['source'],original)
        self.assertEqual(value['sources'][0]['id'],'R1_1_S1')
        self.assertEqual(self.state['sources']['R1_1_S1']['source']['locator'],'Independent decisive locator')

    def test_compact_dossier_review_reconstructs_and_rejects_wrong_base_or_identity(self):
        from execution_units import digest
        self.state['proposal_design'] = copy.deepcopy(self.design)
        base = json.loads(self.design['dossier_json'])
        value = {'dossier_json': json.dumps({'base_sha256': digest(base), 'replace': {}})}
        h.expand_dossier_review(value, self.state)
        self.assertEqual(json.loads(value['dossier_json']), base)
        for payload in ({'base_sha256': 'wrong', 'replace': {}},
                        {'base_sha256': digest(base), 'replace': {'question': 'changed'}}):
            with self.assertRaisesRegex(rt.Blocked, 'Scoped dossier patch'):
                h.expand_dossier_review({'dossier_json': json.dumps(payload)}, self.state)
        def replies(role, state):
            result = self.default_reply(role, state)
            if role == 'reviewer-dossier':
                saved = json.loads(state['proposal_design']['dossier_json'])
                result['dossier_json'] = json.dumps({'base_sha256': state['unit_task']['base_sha256'],
                                                    'replace': {}})
                self.assertEqual(state['unit_task']['base_sha256'], digest(saved))
            return result
        def tampered(role, state):
            value = replies(role, state)
            if role == 'reviewer-dossier':
                candidates = copy.deepcopy(base['candidates'])
                candidates[0]['name'] = 'A different unreviewed method'
                value['dossier_json'] = json.dumps({'base_sha256': state['unit_task']['base_sha256'],
                                                   'replace': {'candidates': candidates}})
            return value
        with self.assertRaisesRegex(rt.Blocked, 'candidate identity'):
            self.drive(tampered)
        self.drive(replies)
        self.assertEqual(self.state['status'], 'research_complete')
        self.assertEqual(self.state['dossier'], base)
        self.assertEqual(self.role_count('producer-design'), 1)

    def test_local_source_can_omit_an_empty_url(self):
        (self.workspace / 'original.txt').write_text('Actual local source text\n')
        descriptor = {'id': 'S1', 'title': 'Actual local source', 'url': '', 'path': 'original.txt',
                      'locator': 'Line 1', 'read_level': 'full_text'}
        source = {'id': 'S1', 'title': descriptor['title'], 'source_type': 'repository',
                  'local_path': descriptor['path'], 'read_level': descriptor['read_level'],
                  'peer_review_status': 'not_applicable', 'retrieved_at': '2026-10-10',
                  'study_id': 'local-source', 'correction_status': 'not_applicable'}
        draft = json.loads(self.design['dossier_json'])
        draft['sources'] = [source]
        self.design.update(dossier_json=json.dumps(draft), sources=[descriptor])
        self.drive()
        self.assertEqual(self.state['status'], 'research_complete')
        self.assertEqual(self.state['sources']['S1']['source'], descriptor)

    def test_producer_source_collision_is_rejected_before_checkpointing(self):
        (self.workspace / 'original.txt').write_text('Actual local primary text\n')
        descriptor = {'id': 'S1', 'title': 'Actual primary', 'url': '', 'path': 'original.txt',
                      'locator': 'Original line 1', 'read_level': 'full_text'}
        h.collect_sources([descriptor], self.state, self.workspace, self.run)
        def invalid(role, state):
            value = self.default_reply(role, state)
            if role == 'producer-design':
                value['sources'] = [{**descriptor, 'locator': 'An unregistered passage'}]
            return value
        with self.assertRaisesRegex(rt.Blocked, 'silently change identity'):
            self.drive(invalid)
        self.assertEqual(self.state['units']['001-producer-design']['status'], 'incomplete')
        self.assertEqual(self.role_count('producer-assets'), 0)
        self.assertEqual(self.state['sources']['S1']['source'], descriptor)
        self.drive()
        self.assertEqual(self.state['status'], 'research_complete')

    def test_new_source_format_errors_never_poison_a_completed_checkpoint(self):
        descriptor = {'id': 'NEW', 'title': 'Original text', 'url': 'https://example.invalid/',
                      'path': '', 'locator': 'Decisive passage', 'read_level': 'relevant_sections'}
        for rows, error in (([descriptor, descriptor], 'IDs must be unique'),
                            ([{**descriptor, 'locator': ''}], 'exact locators'),
                            ([{**descriptor, 'title': ' '}], 'titles'),
                            ([{**descriptor, 'url': ''}], 'URL or real local artifact')):
            with self.subTest(error=error):
                def invalid(role, state):
                    value = self.default_reply(role, state)
                    if role == 'producer-design':
                        value['sources'] = copy.deepcopy(rows)
                    return value
                with self.assertRaisesRegex(rt.Blocked, error):
                    self.drive(invalid)
                self.assertEqual(self.state['units']['001-producer-design']['status'], 'incomplete')
                self.assertEqual(self.role_count('producer-assets'), 0)
                self.assertNotIn('NEW', self.state['sources'])
        self.drive()
        self.assertEqual(self.state['status'], 'research_complete')

    def test_final_dossier_cannot_reidentify_a_saved_source_and_can_resume(self):
        # This tests access-ledger identity and checkpoint behavior, not whether
        # a model understands or correctly interprets the cited passage.
        (self.workspace / "original.txt").write_text("Actual primary passage\n")
        descriptor = {
            "id": "S1", "title": "Actual primary passage",
            "url": "https://docs.python.org/3/", "path": "original.txt",
            "locator": "Line 1", "read_level": "relevant_sections",
        }
        source = {
            "id": "S1", "title": descriptor["title"], "source_type": "official_doc",
            "url": descriptor["url"], "local_path": descriptor["path"],
            "read_level": descriptor["read_level"],
            "peer_review_status": "not_applicable", "retrieved_at": "2026-10-10",
            "study_id": "S1", "correction_status": "not_applicable",
        }
        draft = json.loads(self.design["dossier_json"])
        draft["sources"] = [source]
        self.design.update(dossier_json=json.dumps(draft), sources=[descriptor])
        for field, replacement in (
            ("title", "Unread unrelated source"),
            ("url", "https://example.invalid/unvisited"),
            ("local_path", ""),
            ("read_level", "full_text"),
        ):
            with self.subTest(field=field):
                def replies(role, state):
                    value = self.default_reply(role, state)
                    if role == "reviewer-dossier":
                        dossier = json.loads(value["dossier_json"])
                        dossier["sources"][0][field] = replacement
                        # No new descriptor was captured for this alleged source.
                        value["dossier_json"] = json.dumps(dossier)
                    return value

                with self.assertRaises(rt.Blocked):
                    self.drive(replies)
                self.assertEqual(
                    self.state["units"]["001-reviewer-dossier"]["status"], "incomplete"
                )
                self.assertEqual(self.state["sources"]["S1"]["source"], descriptor)
                self.assertNotEqual(self.state["status"], "research_complete")
        self.drive()
        self.assertEqual(self.state["status"], "research_complete")
        self.assertEqual(self.state["dossier"]["sources"][0], source)
        self.assertEqual(self.role_count("producer-design"), 1)
        self.assertEqual(self.role_count("producer-results"), 1)
        self.assertEqual(self.role_count("reviewer-check"), 1)
        self.assertEqual(self.role_count("reviewer-dossier"), 5)

    def test_workspace_source_path_does_not_select_a_same_named_project_file(self):
        # Distinct real bytes make an incorrect root selection observable.
        # Absolute project sources still use immutable revision snapshots.
        self.project_files({"shared.txt": "PROJECT source text\n"})
        artifact = self.workspace / "shared.txt"
        artifact.write_text("WORKSPACE artifact text\n")
        for path in (str(artifact), "shared.txt"):
            with self.subTest(path=path):
                value = {"sources": [{
                    "id": "S1", "title": "Actual workspace artifact", "url": "",
                    "path": path, "locator": "Line 1", "read_level": "full_text",
                }]}
                h.normalize_unit_paths(value, self.state, self.workspace, self.run)
                target = self.workspace / value["sources"][0]["path"]
                self.assertEqual(target.read_text(), "WORKSPACE artifact text\n")
        project_source = {"sources": [{
            "id": "S2", "title": "Actual project source", "url": "",
            "path": str(self.project / "shared.txt"), "locator": "Line 1",
            "read_level": "full_text",
        }]}
        h.normalize_unit_paths(project_source, self.state, self.workspace, self.run)
        snapshot = self.workspace / project_source["sources"][0]["path"]
        self.assertEqual(snapshot.read_text(), "PROJECT source text\n")
        self.assertTrue(snapshot.is_relative_to(self.run / "source-inputs"))

    def test_effectiveness_runs_real_algorithms_and_parent_grades_outputs(self):
        c = contract()
        c["tasks"] = [
            {"id": "T1", "input": "金額:1,700円", "expected": 1700},
            {"id": "T2", "input": "金額:1701円", "expected": 1701},
        ]
        c["dataset"] = "Two comma-format extraction cases; not a general accuracy benchmark"
        self.state["config"]["evaluation_purpose"] = "effectiveness"
        self.plan["evaluation_json"] = json.dumps(c)
        self.plan["criteria"] = [{
            "id": "R1", "title": "amount extraction", "kind": "runtime",
            "required": True, "acceptance": "Compare actual final outputs on frozen inputs",
        }]

        def replies(role, state):
            if role == "producer-assets":
                # Neither algorithm reads the expected value. The fixture labels
                # are exported only so the parent can verify frozen task identity.
                code = (
                    "import json,re\n"
                    "tasks=" + repr(c["tasks"]) + "\n"
                    "trials=[]\n"
                    "for task in tasks:\n"
                    " for cid in ('A','B'):\n"
                    "  text=task['input'] if cid=='A' else task['input'].replace(',','')\n"
                    "  output=int(re.search(r'[0-9]+',text).group())\n"
                    "  trials.append({'task_id':task['id'],'trial_id':'1',"
                    "'candidate_id':cid,'output':output})\n"
                    "json.dump({'contract_sha256':"
                    + repr(state["evaluation_contract_sha256"])
                    + ",'tasks':tasks,'trials':trials},open('results.json','w'))\n"
                    "open('notes.txt','w').write('Auxiliary export, not task outcomes')\n"
                )
                return {
                    "status": "proposed", "reason": "Real local regex comparison",
                    "files": [{"path": "compare.py", "content": code}],
                    "experiments": [{
                        "id": "E1", "command": "python3 compare.py", "check_ids": ["R1"],
                        "input_files": [], "artifact_paths": ["results.json", "notes.txt"], "timeout_seconds": 5,
                    }],
                }
            if role == "producer-results":
                value = self.default_reply(role, state)
                draft = json.loads(value["dossier_json"])
                draft["decision"].update(candidate_id="B", rationale="Two observed fixture cases only")
                draft["evaluation_result"] = {
                    "contract_sha256": state["evaluation_contract_sha256"],
                    "artifact_paths": [
                        r["path"] for r in state["evidence"].values()
                        if r["kind"] == "artifact" and r["path"].endswith('/results.json')
                    ],
                }
                value["dossier_json"] = json.dumps(draft)
                return value
            if role == "reviewer-check":
                value = self.default_reply(role, state)
                value["checks"][0].update(
                    result="pass", reason="Current actual experiment receipt and parent grades",
                    evidence_ids=[r["id"] for r in self.current_executions(state)],
                )
                return value
            return self.default_reply(role, state)

        self.drive(replies)
        self.assertEqual(self.state["status"], "research_complete")
        comparison = self.state["evaluation_summary"]["metrics"][0]["comparisons"][0]
        self.assertEqual(
            (comparison["baseline"], comparison["candidate"], comparison["delta"]),
            (0.5, 1.0, 0.5),
        )
        actual = json.loads(
            (self.run / "001-experiments/E1/artifacts/results.json").read_text(encoding="utf-8")
        )
        self.assertEqual([r["output"] for r in actual["trials"]], [1, 1700, 1701, 1701])
        self.assertTrue(self.state["evaluation_review_bound"])
        # Reproduce a real final-review error: receipts prove execution but are
        # not paired-result JSON. Diagnose before review and keep strict grades.
        invalid = copy.deepcopy(self.state)
        draft = json.loads(invalid['proposal_design']['dossier_json'])
        receipt = self.current_executions(invalid)[0]['path']
        draft['evaluation_result']['artifact_paths'].append(receipt)
        invalid['proposal_design']['dossier_json'] = json.dumps(draft)
        before = copy.deepcopy(invalid)
        task = h.dossier_review_task(invalid, self.workspace)
        self.assertIn('Evaluation artifact needs a current matching parent record: ' + receipt,
                      task['known_ledger_errors'])
        self.assertEqual(invalid, before)
        self.assertEqual([r['path'] for r in task['successful_experiment_receipts']], [receipt])
        self.assertEqual([r['path'] for r in task['current_exported_artifacts']],
                         [self.state['evaluation_summary']['trials'][0]['artifact_path'],
                          (self.run / '001-experiments/E1/artifacts/notes.txt').relative_to(self.workspace).as_posix()])
        from evaluation_contract import evaluate
        with self.assertRaisesRegex(rt.Blocked, 'current matching parent record'):
            evaluate(draft, copy.deepcopy(invalid), self.workspace)

    def test_run_fixes_source_then_requires_fresh_success_and_resolution(self):
        self.project_files({
            "app.py": "answer=0\n",
            "test.py": "from app import answer\nassert answer==42, answer\n",
        })
        self.backend_mode("run", [{
            "id": "R1", "title": "correct answer", "kind": "runtime",
            "required": True, "acceptance": "answer is 42",
        }], [{"command": "python3 test.py", "check_ids": ["R1"], "artifact_paths": []}])

        def replies(role, state):
            if role == "fixer":
                (self.project / "app.py").write_text("answer=42\n", encoding="utf-8")
                return {
                    "status": "changed", "reason": "Correct the fixture constant",
                    "fixed_issue_ids": [state["selected_issues"][0]["id"]],
                    "changed_files": ["app.py"], "complexity_changes": [],
                }
            if role != "reviewer-check":
                return self.default_reply(role, state)
            receipt = self.current_executions(state)[0]
            passed = receipt["exit_code"] == 0
            value = self.default_reply(role, state)
            value["checks"][0].update(
                result="pass" if passed else "fail", reason="Actual current execution",
                evidence_ids=[receipt["id"]],
            )
            previous = state.get("review", {}).get("issues", [])
            value["issues"] = [{
                "id": previous[0]["id"] if previous else "I1", "title": "Wrong answer",
                "severity": "High", "status": "resolved" if passed else "open",
                "target": "app.py", "action": "python3 test.py", "expected": "42",
                "actual": "Initial value was 0", "why": "Incorrect final output",
                "improvement": "Return 42", "root_cause": "Wrong constant",
                "check_ids": ["R1"], "evidence_ids": [receipt["id"]],
            }]
            return value

        self.drive(replies)
        self.assertEqual(self.state["status"], "passed")
        records = [r for r in self.state["evidence"].values() if r["kind"] == "test"]
        self.assertEqual([r["exit_code"] for r in records], [1, 0])
        self.assertEqual(self.state["review"]["issues"][0]["status"], "resolved")
        self.assertEqual(self.state["fixes"][0]["actual_changed_files"], ["app.py"])
        self.assertEqual(self.role_count("fixer"), 1)

    def test_bad_candidate_is_incomplete_and_resume_reuses_valid_predecessors(self):
        def replies(role, state):
            value = self.default_reply(role, state)
            if role == "producer-evidence" and state["unit_task"]["candidate_id"] == "A":
                nested = json.loads(value["patch_json"])
                nested["candidate"].pop("name")
                value["patch_json"] = json.dumps(nested)
            return value

        with self.assertRaisesRegex(rt.Blocked, "candidate A.name"):
            self.drive(replies)
        saved = json.loads((self.run / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["units"]["001-evidence-A"]["status"], "incomplete")
        self.drive()
        self.assertEqual(self.state["status"], "research_complete")
        self.assertEqual(self.role_count("producer-design"), 1)
        self.assertEqual(self.role_count("producer-assets"), 1)
        self.assertEqual(self.role_count("producer-evidence", "A"), 2)

    def test_minimal_design_cannot_replace_frozen_candidate_identities(self):
        def replies(role, state):
            value = self.default_reply(role, state)
            if role == "producer-design":
                draft = json.loads(value["dossier_json"])
                replacement = {"A": "C", "B": "D"}
                for row in draft["candidates"]:
                    row["id"] = replacement[row["id"]]
                for row in draft["comparison"]:
                    row["candidate_id"] = replacement[row["candidate_id"]]
                draft["decision"]["candidate_id"] = "C"
                value["dossier_json"] = json.dumps(draft)
            return value

        with self.assertRaisesRegex(rt.Blocked, "candidate IDs/baseline"):
            self.drive(replies)
        self.assertEqual(self.state["units"]["001-producer-design"]["status"], "incomplete")
        self.assertEqual(self.role_count("producer-assets"), 0)
        self.drive()
        self.assertEqual(self.state["status"], "research_complete")
        self.assertEqual(self.role_count("planner"), 1)
        self.assertEqual(self.role_count("producer-design"), 2)

    def test_scoped_code_ids_are_distinct_across_criteria(self):
        self.project_files({"a.py": "answer=42\n", "b.py": "answer=42\n"})
        self.backend_mode("audit", [
            {"id": cid, "title": cid, "kind": "static", "required": True,
             "acceptance": "Inspect the actual source line"}
            for cid in ("R1", "R2")
        ])

        def replies(role, state):
            value = self.default_reply(role, state)
            if role == "reviewer-check":
                cid = state["unit_task"]["criterion_ids"][0]
                value["checks"][0].update(
                    result="pass", reason="Actual source line", evidence_ids=["CODE1"],
                )
                value["code_evidence"] = [{
                    "id": "CODE1", "path": "a.py" if cid == "R1" else "b.py",
                    "line_start": 1, "line_end": 1, "description": "Actual answer constant",
                }]
            return value

        self.drive(replies)
        self.assertEqual(self.state["status"], "reviewed")
        evidence_ids = [row["evidence_ids"][0] for row in self.state["review"]["checks"]]
        self.assertEqual(len(set(evidence_ids)), 2)
        self.assertEqual(
            {self.state["evidence"][key]["source_path"] for key in evidence_ids},
            {"a.py", "b.py"},
        )

    def test_unknown_evidence_never_becomes_a_completed_review_checkpoint(self):
        self.backend_mode("audit", [{
            "id": "R1", "title": "runtime evidence", "kind": "runtime",
            "required": True, "acceptance": "A pass requires actual execution",
        }])

        def replies(role, state):
            value = self.default_reply(role, state)
            if role == "reviewer-check":
                value["checks"][0].update(result="pass", evidence_ids=["EV-never-captured"])
            return value

        with self.assertRaisesRegex(rt.Blocked, "unknown evidence IDs"):
            self.drive(replies)
        self.assertEqual(self.state["units"]["001-review-R1"]["status"], "incomplete")
        self.drive()
        self.assertEqual(self.role_count("reviewer-check"), 2)
        self.assertEqual(self.state["review"]["checks"][0]["result"], "unknown")
        self.assertEqual(self.state["status"], "reviewed")

    def test_invalid_final_dossier_can_be_corrected_without_repeating_prior_units(self):
        def replies(role, state):
            value = self.default_reply(role, state)
            if role == "reviewer-dossier":
                nested = json.loads(value["dossier_json"])
                nested.pop("question")
                value["dossier_json"] = json.dumps(nested)
            return value

        with self.assertRaisesRegex(rt.Blocked, "question"):
            self.drive(replies)
        self.assertEqual(self.state["units"]["001-reviewer-dossier"]["status"], "incomplete")
        prior_counts = {role: self.role_count(role) for role in (
            "planner", "producer-design", "producer-assets", "producer-results",
            "producer-evidence", "reviewer-check",
        )}
        self.drive()
        self.assertEqual(self.state["status"], "research_complete")
        self.assertEqual(self.role_count("reviewer-dossier"), 2)
        self.assertEqual(prior_counts, {role: self.role_count(role) for role in prior_counts})

    def test_unavailable_final_support_does_not_restart_the_whole_comparison(self):
        actual = h.decisive_source_errors
        def unavailable(dossier, state):
            if state.get('phase') == 'reviewer-dossier':
                return ['Decisive source unavailable: fixture-original']
            return actual(dossier, state)
        with patch.object(h, 'decisive_source_errors', side_effect=unavailable):
            with self.assertRaisesRegex(rt.Blocked, 'Decisive source unavailable'):
                self.drive()
        self.assertEqual(self.state['iteration'], 1)
        self.assertEqual(self.state['units']['001-reviewer-dossier']['status'], 'incomplete')
        self.assertEqual(self.role_count('producer-design'), 1)
        self.assertEqual(self.role_count('producer-evidence'), 2)
        self.drive()
        self.assertEqual(self.state['status'], 'research_complete')
        self.assertEqual(self.role_count('producer-design'), 1)
        self.assertEqual(self.role_count('reviewer-dossier'), 2)

    def test_repeated_command_declarations_execute_twice_and_resume_reuses_both(self):
        self.project_files({
            "counter.py": (
                "from pathlib import Path\np=Path('count.txt')\n"
                "n=int(p.read_text()) if p.exists() else 0\n"
                "p.write_text(str(n+1))\nprint(n+1)\n"
            ),
        })
        self.backend_mode("audit", [{
            "id": "R1", "title": "two repetitions", "kind": "runtime",
            "required": True, "acceptance": "Both declared checks actually execute",
        }], [
            {"command": "python3 counter.py", "check_ids": ["R1"], "artifact_paths": []},
            {"command": "python3 counter.py", "check_ids": ["R1"], "artifact_paths": []},
        ])

        def stopped(role, state):
            if role == "reviewer-check":
                raise rt.Blocked("Fixture interruption after completed executions")
            return self.default_reply(role, state)

        with self.assertRaisesRegex(rt.Blocked, "Fixture interruption"):
            self.drive(stopped)
        records = self.current_executions(self.state)
        self.assertEqual(len(records), 2)
        hashes = {r["id"]: r["sha256"] for r in records}
        self.assertEqual([
            (self.run / f"001-checks/{i:03d}/stdout.log").read_text(encoding="utf-8").strip()
            for i in (1, 2)
        ], ["1", "2"])

        def resumed(role, state):
            value = self.default_reply(role, state)
            if role == "reviewer-check":
                value["checks"][0].update(
                    result="pass", reason="Both immutable execution receipts",
                    evidence_ids=[r["id"] for r in self.current_executions(state)],
                )
            return value

        with patch.object(h, "capture", side_effect=AssertionError("Completed checks must not repeat")):
            self.drive(resumed)
        self.assertEqual(self.state["status"], "reviewed")
        self.assertEqual(
            {r["id"]: r["sha256"] for r in self.current_executions(self.state)}, hashes,
        )

    def test_absolute_source_is_snapshotted_and_malformed_nested_json_is_repairable(self):
        self.project_files({"source.txt": "An original source passage\n"})
        descriptor = {
            "id": "S1", "title": "Original passage", "url": "",
            "path": str(self.project / "source.txt"), "locator": "line 1",
            "read_level": "full_text",
        }
        value = {"sources": [copy.deepcopy(descriptor)], "dossier_json": json.dumps({
            "sources": [{"id": "S1", "local_path": descriptor["path"]}],
        })}
        h.normalize_unit_paths(value, self.state, self.workspace, self.run)
        snapshot = self.workspace / value["sources"][0]["path"]
        self.assertEqual(snapshot.read_text(encoding="utf-8"), "An original source passage\n")
        self.assertEqual(
            json.loads(value["dossier_json"])["sources"][0]["local_path"],
            value["sources"][0]["path"],
        )
        (self.project / "source.txt").write_text("Declared new revision\n", encoding="utf-8")
        self.state["expected_source"] = rt.fingerprint(self.project, self.workspace)
        revised = {"sources": [{**descriptor, "id": "S2"}]}
        h.normalize_unit_paths(revised, self.state, self.workspace, self.run)
        self.assertNotEqual(revised["sources"][0]["path"], value["sources"][0]["path"])
        self.assertEqual(snapshot.read_text(encoding="utf-8"), "An original source passage\n")
        self.assertEqual((self.workspace / revised["sources"][0]["path"]).read_text(encoding="utf-8"), "Declared new revision\n")
        with self.assertRaisesRegex(rt.Blocked, "outside"):
            h.normalize_unit_paths(
                {"sources": [{**descriptor, "path": "/etc/passwd"}]},
                self.state, self.workspace, self.run,
            )
        malformed = {**copy.deepcopy(self.design), "sources": [descriptor], "dossier_json": "[]"}
        with patch.object(h, "run_role", return_value=malformed) as invoked:
            with self.assertRaisesRegex(rt.Blocked, "Nested dossier JSON format"):
                h.checked_role(
                    "producer-design", h.DESIGN, self.state, self.workspace, self.run,
                    h.design_format,
                )
        self.assertEqual(invoked.call_count, 2)


if __name__ == "__main__":
    unittest.main()
