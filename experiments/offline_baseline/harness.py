"""Offline baseline harness: run replay and compare against hand-authored expectations.

This harness is the comparison layer for O1 (independent offline baseline).
It reads cases.json, builds run manifests and event files, calls the replay
engine, and compares the output against the hand-authored expected results.

Key constraint: the expected results in cases.json are authored independently.
This harness never generates expectations; it only compares.

Usage:
    python experiments/offline_baseline/harness.py
    python experiments/offline_baseline/harness.py --verbose
    python experiments/offline_baseline/harness.py --case 01_at_bound
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from coverage_closure.contracts import canonical, digest, file_digest, read_json
from coverage_closure.replay import replay

FOLDER = Path(__file__).resolve().parent
PLANS_DIR = FOLDER / "plans"

VERSIONS = {key: "offline-baseline:no-" + key for key in
            ["dut", "testbench", "monitor", "binding", "config", "checker", "simulator", "sampling"]}
STAGES = {key: "not_run" for key in ["build", "run", "export"]}

SAMPLE_FIELDS = ["rule_id", "end_event_id", "start_event_id", "outcome",
                 "interval_ticks", "bin_id", "suppression_reason"]
SUMMARY_FIELDS = ["total_bins", "replay_observed_bins", "replay_observation_ratio",
                  "replayed_violations"]


def expand_event(raw, run_id):
    return {
        "event_id": raw["id"],
        "run_id": run_id,
        "timestamp_ticks": raw["t"],
        "channel": raw.get("ch", 0),
        "subchannel": raw.get("sub", 0),
        "rank": raw.get("rk", 0),
        "config_epoch": raw.get("ce", 0),
        "reset_epoch": raw.get("re", 0),
        "kind": raw.get("kind", "command"),
        "command": raw.get("cmd"),
        "valid": raw.get("valid", True),
        "source_locator": f"offline_baseline:{raw['id']}",
    }


def build_run(run_id, plan, events_path):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "origin": "synthetic_fixture",
        "time_unit": plan["time_unit"],
        "plan_sha256": digest(plan),
        "events_sha256": file_digest(events_path),
        "versions": VERSIONS,
        "stages": STAGES,
    }


def match_samples(actual_samples, expected_samples):
    errors = []
    actual_by_key = {}
    for s in actual_samples:
        key = (s["rule_id"], s["end_event_id"])
        if key in actual_by_key:
            errors.append(f"  duplicate actual sample for {key}")
        actual_by_key[key] = s
    if len(expected_samples) != len(actual_by_key):
        errors.append(f"  sample count: expected {len(expected_samples)}, got {len(actual_by_key)}")
    for exp in expected_samples:
        key = (exp["rule_id"], exp["end_event_id"])
        act = actual_by_key.get(key)
        if act is None:
            errors.append(f"  missing sample for rule={exp['rule_id']} end={exp['end_event_id']}")
            continue
        for field in SAMPLE_FIELDS:
            if act.get(field) != exp[field]:
                errors.append(f"  sample {key} field '{field}': expected {exp[field]!r}, got {act.get(field)!r}")
    return errors


def match_summary(actual_summary, expected_summary):
    errors = []
    for field in SUMMARY_FIELDS:
        if actual_summary.get(field) != expected_summary[field]:
            errors.append(f"  summary.{field}: expected {expected_summary[field]!r}, got {actual_summary.get(field)!r}")
    return errors


def match_diagnostics(actual_diag, expected_diag):
    errors = []
    if len(actual_diag) != len(expected_diag):
        errors.append(f"  diagnostics count: expected {len(expected_diag)}, got {len(actual_diag)}")
    for i, exp in enumerate(expected_diag):
        if i >= len(actual_diag):
            break
        act = actual_diag[i]
        for field in ["event_id", "code", "effect", "root_cause"]:
            if act.get(field) != exp[field]:
                errors.append(f"  diagnostics[{i}].{field}: expected {exp[field]!r}, got {act.get(field)!r}")
    return errors


def run_case(case, plan, verbose=False):
    name = case["name"]
    run_id = "offline." + name
    events = [expand_event(e, run_id) for e in case["events"]]
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        plan_subdir = tmpdir / "plans"
        plan_subdir.mkdir()
        (tmpdir / "spec.md").write_bytes((FOLDER / "spec.md").read_bytes())
        events_path = plan_subdir / "events.jsonl"
        events_path.write_text("\n".join(canonical(e) for e in events) + "\n", encoding="utf-8")
        run = build_run(run_id, plan, events_path)
        report = replay(plan, run, events_path, plan_subdir)

    expected = case["expected"]
    errors = []
    errors += match_samples(report["samples"], expected["samples"])
    errors += match_summary(report["summary"], expected["summary"])
    if report["duplicates_ignored"] != expected["duplicates_ignored"]:
        errors.append(f"  duplicates_ignored: expected {expected['duplicates_ignored']}, got {report['duplicates_ignored']}")
    errors += match_diagnostics(report["diagnostics"], expected.get("diagnostics", []))

    if errors:
        if verbose:
            print(f"FAIL  {name}")
            for e in errors:
                print(e)
        else:
            print(f"FAIL  {name}  ({len(errors)} mismatches)")
        return False, errors
    print(f"PASS  {name}")
    return True, []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Offline baseline harness")
    parser.add_argument("--verbose", action="store_true", help="Show per-field mismatches")
    parser.add_argument("--case", help="Run only the named case")
    args = parser.parse_args()

    cases_data = read_json(FOLDER / "cases.json")
    results = []
    for case in cases_data["cases"]:
        if args.case and case["name"] != args.case:
            continue
        plan_path = PLANS_DIR / (case["plan"] + ".json")
        if not plan_path.is_file():
            print(f"ERROR {case['name']}  plan file missing: {plan_path}")
            results.append(False)
            continue
        plan = read_json(plan_path)
        ok, _ = run_case(case, plan, verbose=args.verbose)
        results.append(ok)

    total = len(results)
    passed = sum(results)
    failed = total - passed
    print(f"\n{'='*40}")
    print(f"Total: {total}  Pass: {passed}  Fail: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
