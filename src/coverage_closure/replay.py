"""Reference replay of the min_interval primitive; never a sign-off engine."""
from __future__ import annotations

from pathlib import Path

from . import __version__
from .contracts import (bin_definitions, digest, file_digest, load_events, require_ready,
                        validate_plan, validate_run)


def replay(plan, run, events_path, plan_dir):
    validate_plan(plan, plan_dir)
    require_ready(plan)
    validate_run(run, plan)
    events, duplicates = load_events(events_path, run)
    histories = {}
    epochs = {}
    samples = []
    bins = bin_definitions(plan)
    counts = {b["bin_id"]: 0 for b in bins}
    diagnostics = []
    metrics = {r["id"]: {"opportunities": 0, "guard_true": 0, "samples": 0,
                           "classified": 0, "legal_hits": 0, "violations": 0}
               for r in plan["rules"]}
    for event in events:
        scope = tuple(event[k] for k in ["channel", "subchannel", "rank"])
        epoch = (event["config_epoch"], event["reset_epoch"])
        if epochs.get(scope) != epoch or event["kind"] == "reset":
            for rule in plan["rules"]:
                histories.pop((rule["id"], scope), None)
        epochs[scope] = epoch
        if event["kind"] == "reset":
            continue
        if not event["valid"]:
            diagnostics.append({"event_id": event["event_id"], "code": "invalid_observation",
                                "effect": "scope_history_invalidated", "root_cause": "unknown"})
        for rule in plan["rules"]:
            rid = rule["id"]
            key = (rid, scope)
            prior = histories.get(key)
            if event["command"] in rule["end_commands"]:
                metrics[rid]["opportunities"] += 1
                reason = "invalid_observation" if not event["valid"] else "no_history" if prior is None else None
                sample = {
                    "sample_id": digest([run["run_id"], event["event_id"], rid, rule["revision"], digest(plan)]),
                    "rule_id": rid, "rule_revision": rule["revision"],
                    "requirement_id": rule["requirement_id"], "scope": list(scope),
                    "config_epoch": epoch[0], "reset_epoch": epoch[1],
                    "start_event_id": prior["event_id"] if prior else None,
                    "end_event_id": event["event_id"], "guard": reason is None,
                    "suppression_reason": reason, "bound_ticks": rule["bound_ticks"],
                    "time_unit": plan["time_unit"], "interval_ticks": None,
                    "outcome": "suppressed", "bin_id": None,
                    "end_source_locator": event["source_locator"],
                    "start_source_locator": prior["source_locator"] if prior else None,
                }
                if reason is None:
                    delta = event["timestamp_ticks"] - prior["timestamp_ticks"]
                    outcome = "below_bound" if delta < rule["bound_ticks"] else "at_bound" if delta == rule["bound_ticks"] else "above_bound"
                    sample.update(interval_ticks=delta, outcome=outcome)
                    for m in ["guard_true", "samples", "classified"]:
                        metrics[rid][m] += 1
                    if outcome == "below_bound":
                        metrics[rid]["violations"] += 1
                    else:
                        sample["bin_id"] = rid + "." + outcome
                        counts[sample["bin_id"]] += 1
                        metrics[rid]["legal_hits"] += 1
                samples.append(sample)
            # Evaluate against old history before latching this event. This covers
            # the case where the same command belongs to both start and end sets.
            if not event["valid"]:
                histories.pop(key, None)
            elif event["command"] == rule["start_command"]:
                histories[key] = event
    for b in bins:
        b.update(replay_hit_count=counts[b["bin_id"]], verified_hit_count=0,
                 disposition="unresolved", diagnosis="unknown")
    hit_bins = sum(n > 0 for n in counts.values())
    return {
        "schema_version": 1, "engine_version": __version__,
        "engine_sha256": file_digest(Path(__file__)),
        "plan_sha256": digest(plan), "run_id": run["run_id"], "origin": run["origin"],
        "status": "needs_integration" if run["origin"] == "synthetic_fixture" else "needs_validation",
        "closure_claim": False,
        "verification_blockers": ["native_coverage_not_joined", "independent_checker_evidence_missing",
                                   "model_validation_evidence_missing", "required_regression_not_evaluated"],
        "events_loaded": len(events), "duplicates_ignored": duplicates,
        "metrics": metrics, "bins": bins, "samples": samples, "diagnostics": diagnostics,
        "summary": {"total_bins": len(bins), "replay_observed_bins": hit_bins,
                    "replay_observation_ratio": hit_bins / len(bins),
                    "verified_hit_bins": 0, "verified_coverage": None,
                    "unresolved_bins": len(bins), "excluded_bins": 0,
                    "replayed_violations": sum(m["violations"] for m in metrics.values())},
    }
