"""Immutable output bundles and backward/forward trace queries."""
from __future__ import annotations

import json
from pathlib import Path

from .codegen import generate_sv
from .contracts import file_digest, read_json, require


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def new_directory(path):
    path = Path(path).resolve()
    require(not path.exists(), f"output already exists; choose a new run directory: {path}")
    path.mkdir(parents=True)
    return path


def input_references(plan, plan_path, other_paths=()):
    paths = [Path(plan_path).resolve(), *(Path(p).resolve() for p in other_paths)]
    paths += [(Path(plan_path).resolve().parent / s["path"]).resolve() for s in plan["sources"]]
    paths += sorted(Path(__file__).parent.glob("*.py"))
    return [{"path": str(p), "sha256": file_digest(p)} for p in dict.fromkeys(paths)]


def write_generation(plan, out):
    sv, source_map = generate_sv(plan)
    sv_path = out / "collector.sv"
    sv_path.write_text(sv, encoding="utf-8")
    source_map["generated_file"] = "collector.sv"
    source_map["generated_sha256"] = file_digest(sv_path)
    write_json(out / "source_map.json", source_map)
    return source_map


def save_replay(report, plan, run, out, plan_path, run_path, events_path):
    out = new_directory(out)
    write_generation(plan, out)
    write_json(out / "plan_snapshot.json", plan)
    write_json(out / "run_snapshot.json", run)
    (out / "events.jsonl").write_bytes(Path(events_path).read_bytes())
    report["inputs"] = input_references(plan, plan_path, [run_path, events_path])
    report["artifacts"] = [{"path": p.name, "sha256": file_digest(p)} for p in sorted(out.iterdir()) if p.is_file()]
    write_json(out / "report.json", report)
    return out


def bundle_status(report_path):
    report_path = Path(report_path).resolve()
    report = read_json(report_path)
    stale = []
    for item in report["inputs"]:
        p = Path(item["path"])
        if not p.is_file() or file_digest(p) != item["sha256"]:
            stale.append(item["path"])
    for item in report["artifacts"]:
        p = (report_path.parent / item["path"]).resolve()
        require(p.is_relative_to(report_path.parent), "artifact path escapes bundle")
        if not p.is_file() or file_digest(p) != item["sha256"]:
            stale.append(str(p))
    return report, stale


def trace_bin(report_path, bin_id):
    report, stale = bundle_status(report_path)
    out = Path(report_path).resolve().parent
    plan = read_json(out / "plan_snapshot.json")
    mapping = read_json(out / "source_map.json")
    candidates = [b for b in report["bins"] if b["bin_id"] == bin_id]
    require(len(candidates) == 1, f"unknown or ambiguous bin: {bin_id}")
    b = candidates[0]
    rule = next(r for r in plan["rules"] if r["id"] == b["rule_id"])
    req = next(r for r in plan["requirements"] if r["id"] == rule["requirement_id"])
    return {"bin": b, "freshness": "stale" if stale else "current", "changed_or_missing": stale,
            "closure_claim": False, "rule": rule, "requirement": req,
            "sources": [s for s in plan["sources"] if s["id"] in req["source_ids"]],
            "code_mapping": [m for m in mapping["mappings"] if m["rule_id"] == rule["id"]],
            "witnesses": [s for s in report["samples"] if s["bin_id"] == bin_id],
            "related_samples": [s for s in report["samples"] if s["rule_id"] == rule["id"]],
            "verification_blockers": report["verification_blockers"]}


def impact(plan, object_id):
    sources = {s["id"] for s in plan["sources"]}
    reqs = {r["id"] for r in plan["requirements"]}
    rules = {r["id"] for r in plan["rules"]}
    require(object_id in sources | reqs | rules, f"unknown source/requirement/rule: {object_id}")
    affected_reqs = {r["id"] for r in plan["requirements"] if object_id in r["source_ids"] or object_id == r["id"]}
    affected_rules = [r for r in plan["rules"] if r["requirement_id"] in affected_reqs or r["id"] == object_id]
    return {"changed_object": object_id, "rule_ids": [r["id"] for r in affected_rules],
            "bin_ids": [r["id"] + "." + b for r in affected_rules for b in ["at_bound", "above_bound"]],
            "required_actions": ["regenerate", "replay_affected_traces", "revalidate_model", "rerun_required_regression"],
            "precision": "rule_dependency_level; regression test selection not yet implemented"}
