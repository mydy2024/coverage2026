"""Behavioral and failure-boundary tests; expected outcomes authored independently."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from coverage_closure.artifacts import impact, save_replay, trace_bin, write_json
from coverage_closure.codegen import generate_sv
from coverage_closure.contracts import (ContractError, canonical, digest, file_digest,
                                       parse_json, read_json, validate_plan)
from coverage_closure.replay import replay


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.plan = read_json(ROOT / "examples/min_interval/plan.json")
        self.run = read_json(ROOT / "examples/min_interval/baseline.run.json")
        (self.folder / "spec.md").write_bytes((ROOT / "examples/min_interval/spec.md").read_bytes())

    def event(self, eid, t, cmd="END", **kwargs):
        event = {"event_id": eid, "run_id": self.run["run_id"], "timestamp_ticks": t,
                 "channel": 0, "subchannel": 0, "rank": 0, "config_epoch": 0, "reset_epoch": 0,
                 "kind": "command", "command": cmd, "valid": True, "source_locator": f"fixture:{eid}"}
        event.update(kwargs)
        return event

    def execute(self, events, refresh_plan=True):
        path = self.folder / "events.jsonl"
        path.write_text("\n".join(canonical(e) for e in events) + "\n", encoding="utf-8")
        self.run["events_sha256"] = file_digest(path)
        if refresh_plan:
            self.run["plan_sha256"] = digest(self.plan)
        return replay(self.plan, self.run, path, self.folder)

    def test_boundary_and_above_are_observations_not_signoff(self):
        report = self.execute([self.event("s", 0, "START"), self.event("b", 4), self.event("a", 6)])
        self.assertEqual([s["outcome"] for s in report["samples"]], ["at_bound", "above_bound"])
        self.assertEqual(report["summary"]["replay_observation_ratio"], 1)
        self.assertEqual(report["summary"]["verified_hit_bins"], 0)
        self.assertIsNone(report["summary"]["verified_coverage"])
        self.assertFalse(report["closure_claim"])

    def test_violation_cannot_increase_legal_coverage(self):
        report = self.execute([self.event("s", 0, "START"), self.event("e", 3)])
        self.assertEqual(report["summary"]["replayed_violations"], 1)
        self.assertEqual(report["summary"]["replay_observed_bins"], 0)
        self.assertIsNone(report["samples"][0]["bin_id"])

    def test_no_history_does_not_create_zero_distance(self):
        report = self.execute([self.event("e", 4)])
        self.assertEqual(report["samples"][0]["suppression_reason"], "no_history")
        self.assertIsNone(report["samples"][0]["interval_ticks"])

    def test_latest_start_wins(self):
        report = self.execute([self.event("s1", 0, "START"), self.event("s2", 2, "START"), self.event("e", 6)])
        self.assertEqual(report["samples"][0]["start_event_id"], "s2")
        self.assertEqual(report["samples"][0]["outcome"], "at_bound")

    def test_start_equals_end_samples_old_history(self):
        self.plan["rules"][0]["end_commands"] = ["START"]
        report = self.execute([self.event("s1", 0, "START"), self.event("s2", 4, "START")])
        self.assertEqual([s["outcome"] for s in report["samples"]], ["suppressed", "at_bound"])

    def test_scopes_are_independent(self):
        for dimension in ["channel", "subchannel", "rank"]:
            with self.subTest(dimension=dimension):
                report = self.execute([self.event("s", 0, "START"), self.event("other", 4, **{dimension: 1}), self.event("own", 4)])
                self.assertEqual([s["outcome"] for s in report["samples"]], ["suppressed", "at_bound"])

    def test_reset_clears_history(self):
        report = self.execute([self.event("s", 0, "START"),
                               self.event("r", 1, None, kind="reset", valid=False), self.event("e", 4)])
        self.assertEqual(report["samples"][0]["suppression_reason"], "no_history")

    def test_epoch_changes_clear_history(self):
        for epoch in ["config_epoch", "reset_epoch"]:
            with self.subTest(epoch=epoch):
                report = self.execute([self.event("s", 0, "START"), self.event("e", 4, **{epoch: 1})])
                self.assertEqual(report["samples"][0]["suppression_reason"], "no_history")

    def test_invalid_observation_suppresses_and_invalidates(self):
        report = self.execute([self.event("s", 0, "START"), self.event("bad", 4, valid=False), self.event("e", 6)])
        self.assertEqual([s["suppression_reason"] for s in report["samples"]], ["invalid_observation", "no_history"])

    def test_exact_duplicates_are_idempotent(self):
        s, e = self.event("s", 0, "START"), self.event("e", 4)
        report = self.execute([s, e, s, e])
        self.assertEqual(report["duplicates_ignored"], 2)
        self.assertEqual(sum(b["replay_hit_count"] for b in report["bins"]), 1)

    def test_conflicting_duplicates_rejected(self):
        with self.assertRaisesRegex(ContractError, "conflicting duplicate"):
            self.execute([self.event("same", 0, "START"), self.event("same", 4)])

    def test_timestamp_and_epoch_regressions_rejected(self):
        cases = [[self.event("s", 4, "START"), self.event("e", 3)],
                 [self.event("s", 4, "START"), self.event("e", 4)],
                 [self.event("s", 0, "START", config_epoch=1), self.event("e", 4)]]
        for events in cases:
            with self.subTest(events=events), self.assertRaises(ContractError):
                self.execute(events)

    def test_integers_reject_bool_float_negative_and_overflow(self):
        for value in [True, 1.2, -1, 2**63]:
            with self.subTest(value=value), self.assertRaises(ContractError):
                self.execute([self.event("e", value)])

    def test_changed_model_cannot_reuse_manifest(self):
        self.plan["rules"][0]["bound_ticks"] = 5
        with self.assertRaisesRegex(ContractError, "stale plan"):
            self.execute([self.event("s", 0, "START")], refresh_plan=False)

    def test_source_tampering_rejected(self):
        (self.folder / "spec.md").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "source hash mismatch"):
            self.execute([self.event("e", 4)])

    def test_failed_simulation_and_driver_intent_rejected(self):
        self.run["origin"] = "monitor_export"
        self.run["stages"] = {"build": "passed", "run": "failed", "export": "passed"}
        with self.assertRaisesRegex(ContractError, "invalid simulation"):
            self.execute([self.event("e", 4)])
        self.run["origin"] = "driver_intent"
        with self.assertRaisesRegex(ContractError, "not an observation"):
            self.execute([self.event("e", 4)])

    def test_fixture_cannot_claim_simulation_passed(self):
        self.run["stages"]["run"] = "passed"
        with self.assertRaisesRegex(ContractError, "fixture must not claim"):
            self.execute([self.event("e", 4)])

    def test_empty_stream_and_unit_mismatch_rejected(self):
        with self.assertRaisesRegex(ContractError, "empty event"):
            self.execute([])
        self.run["time_unit"] = "ps"
        with self.assertRaisesRegex(ContractError, "time_unit mismatch"):
            self.execute([self.event("e", 4)])

    def test_unreviewed_and_unresolved_rules_block_generation(self):
        for key, value in [("review_status", "draft"), ("bound_ticks", None), ("blockers", ["anchor_unclear"])]:
            plan = copy.deepcopy(self.plan)
            plan["rules"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ContractError, "plan blocked"):
                generate_sv(plan)

    def test_dangling_and_unmapped_requirements_rejected(self):
        self.plan["rules"][0]["requirement_id"] = "req.missing"
        with self.assertRaisesRegex(ContractError, "dangling requirement"):
            validate_plan(self.plan, self.folder)
        self.plan["rules"][0]["requirement_id"] = "req.fixture.interval"
        extra = copy.deepcopy(self.plan["requirements"][0])
        extra["id"] = "req.unmapped"
        self.plan["requirements"].append(extra)
        with self.assertRaisesRegex(ContractError, "unmapped requirements"):
            validate_plan(self.plan, self.folder)

    def test_duplicate_json_keys_and_nan_rejected(self):
        for text in ['{"revision":1,"revision":2}', '{"bound":NaN}']:
            with self.subTest(text=text), self.assertRaises(ContractError):
                parse_json(text)

    def test_cross_type_id_collision_rejected(self):
        self.plan["rules"][0]["id"] = self.plan["sources"][0]["id"]
        with self.assertRaisesRegex(ContractError, "globally unique"):
            validate_plan(self.plan, self.folder)

    def test_bundle_trace_and_staleness(self):
        report = self.execute([self.event("s", 0, "START"), self.event("e", 4)])
        pp, rp, ep = self.folder / "plan.json", self.folder / "run.json", self.folder / "events.jsonl"
        write_json(pp, self.plan)
        write_json(rp, self.run)
        out = save_replay(report, self.plan, self.run, self.folder / "out", pp, rp, ep)
        traced = trace_bin(out / "report.json", "rel.fixture.interval.at_bound")
        self.assertEqual(traced["freshness"], "current")
        self.assertEqual(traced["witnesses"][0]["start_event_id"], "s")
        self.assertEqual(traced["sources"][0]["id"], "src.fixture")
        (out / "collector.sv").write_text("tampered", encoding="utf-8")
        self.assertEqual(trace_bin(out / "report.json", "rel.fixture.interval.at_bound")["freshness"], "stale")
        with self.assertRaisesRegex(ContractError, "output already exists"):
            save_replay(report, self.plan, self.run, out, pp, rp, ep)

    def test_impact_query_is_forward_trace(self):
        result = impact(self.plan, "src.fixture")
        self.assertEqual(result["bin_ids"], ["rel.fixture.interval.at_bound", "rel.fixture.interval.above_bound"])

    def test_cli_rejects_zero_work_and_unknown_commands(self):
        for argv in [[], ["nonexistent"]]:
            result = subprocess.run([sys.executable, str(ROOT / "cc.py"), *argv], capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_cli_draft_is_blocked_and_does_not_emit_artifacts(self):
        target = self.folder / "generated"
        result = subprocess.run([sys.executable, str(ROOT / "cc.py"), "generate", "--plan",
                                 str(ROOT / "examples/ddr5_vref/plan.draft.json"), "--out", str(target)], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(target.exists())

    def test_codegen_changes_when_semantics_change(self):
        first, first_map = generate_sv(self.plan)
        self.plan["rules"][0]["bound_ticks"] = 5
        second, second_map = generate_sv(self.plan)
        self.assertNotEqual(first, second)
        self.assertNotEqual(first_map["plan_sha256"], second_map["plan_sha256"])
        self.assertTrue(all(b["native_path"] is None for b in second_map["bins"]))


if __name__ == "__main__":
    unittest.main()
