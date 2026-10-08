"""Strict, intentionally small contracts. No arbitrary expression execution."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key: {key}")
        value[key] = item
    return value


def parse_json(text):
    try:
        return json.loads(text, object_pairs_hook=_unique_pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(ContractError(f"invalid number: {x}")))
    except json.JSONDecodeError as exc:
        raise ContractError(str(exc)) from exc


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8-sig"))


def fields(value, keys, label):
    require(isinstance(value, dict), f"{label}: expected object")
    require(set(value) == set(keys),
            f"{label}: missing={sorted(set(keys)-set(value))}, unknown={sorted(set(value)-set(keys))}")


def integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, f"{label}: expected integer >= {minimum}")


def string(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label}: expected nonempty string")


def identifier(value, label):
    string(value, label)
    require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", value) is not None, f"{label}: invalid identifier")


def index(items, label):
    require(isinstance(items, list), f"{label}: expected list")
    result = {}
    for item in items:
        require(isinstance(item, dict) and "id" in item, f"{label}: missing id")
        identifier(item["id"], label)
        require(item["id"] not in result, f"{label}: duplicate id {item['id']}")
        result[item["id"]] = item
    return result


def validate_plan(plan, base_dir):
    fields(plan, ["schema_version", "plan_id", "revision", "protocol", "time_unit",
                  "sources", "requirements", "rules"], "plan")
    require(type(plan["schema_version"]) is int and plan["schema_version"] == 1, "unsupported plan schema")
    identifier(plan["plan_id"], "plan_id")
    integer(plan["revision"], "revision", 1)
    string(plan["protocol"], "protocol")
    require(plan["time_unit"] in ["fs", "ps", "ns"], "unsupported time_unit; no implicit conversion")
    sources = index(plan["sources"], "sources")
    requirements = index(plan["requirements"], "requirements")
    rules = index(plan["rules"], "rules")
    require(sources and requirements and rules, "empty source/requirement/rule sets cannot pass")
    require(len(set(sources) | set(requirements) | set(rules)) == len(sources) + len(requirements) + len(rules),
            "source, requirement and rule IDs must be globally unique")
    for sid, source in sources.items():
        fields(source, ["id", "path", "sha256", "locator"], sid)
        string(source["path"], "source.path")
        string(source["locator"], "source.locator")
        path = (Path(base_dir) / source["path"]).resolve()
        require(path.is_file(), f"{sid}: missing source {path}")
        require(source["sha256"] == file_digest(path), f"{sid}: source hash mismatch")
    for rid, req in requirements.items():
        fields(req, ["id", "source_ids", "text", "review_status"], rid)
        string(req["text"], "requirement.text")
        require(req["review_status"] in ["draft", "reviewed"], "invalid requirement review_status")
        require(isinstance(req["source_ids"], list) and req["source_ids"], f"{rid}: sources required")
        require(all(isinstance(x, str) and x in sources for x in req["source_ids"]), f"{rid}: dangling source")
    for rid, rule in rules.items():
        fields(rule, ["id", "revision", "requirement_id", "review_status", "blockers", "op",
                      "start_command", "end_commands", "bound_ticks", "history_policy",
                      "start_anchor", "end_anchor"], rid)
        integer(rule["revision"], "rule.revision", 1)
        require(isinstance(rule["requirement_id"], str) and rule["requirement_id"] in requirements, f"{rid}: dangling requirement")
        require(rule["review_status"] in ["draft", "reviewed"], "invalid rule review_status")
        require(isinstance(rule["blockers"], list) and all(isinstance(x, str) and x for x in rule["blockers"]), "invalid blockers")
        require(rule["op"] == "min_interval", f"{rid}: unsupported op")
        identifier(rule["start_command"], "start_command")
        require(isinstance(rule["end_commands"], list) and rule["end_commands"], "end_commands required")
        for command in rule["end_commands"]:
            identifier(command, "end_command")
        require(len(set(rule["end_commands"])) == len(rule["end_commands"]), "duplicate end command")
        require(rule["history_policy"] == "latest_start", "unsupported history_policy")
        for anchor in ["start_anchor", "end_anchor"]:
            string(rule[anchor], anchor)
        if rule["bound_ticks"] is not None:
            integer(rule["bound_ticks"], "bound_ticks", 1)
            require(rule["bound_ticks"] < 2**63, "bound_ticks exceeds backend range")
    # A requirement with no rule must remain visible, not silently leave the denominator.
    missing = set(requirements) - {rule["requirement_id"] for rule in rules.values()}
    require(not missing, f"unmapped requirements: {sorted(missing)}")
    return plan


def readiness_blockers(plan):
    issues = []
    for req in plan["requirements"]:
        if req["review_status"] != "reviewed":
            issues.append(f"{req['id']}: requirement_not_reviewed")
    for rule in plan["rules"]:
        if rule["review_status"] != "reviewed":
            issues.append(f"{rule['id']}: rule_not_reviewed")
        if rule["bound_ticks"] is None:
            issues.append(f"{rule['id']}: unresolved_bound")
        issues.extend(f"{rule['id']}: {item}" for item in rule["blockers"])
    return issues


def require_ready(plan):
    issues = readiness_blockers(plan)
    require(not issues, "plan blocked: " + "; ".join(issues))


def bin_definitions(plan):
    return [{"bin_id": rule["id"] + "." + outcome, "bin_revision": rule["revision"],
             "rule_id": rule["id"], "requirement_id": rule["requirement_id"], "outcome": outcome}
            for rule in plan["rules"] for outcome in ["at_bound", "above_bound"]]


def validate_run(run, plan):
    fields(run, ["schema_version", "run_id", "origin", "time_unit", "plan_sha256", "events_sha256",
                 "versions", "stages"], "run")
    require(type(run["schema_version"]) is int and run["schema_version"] == 1, "unsupported run schema")
    identifier(run["run_id"], "run_id")
    require(run["origin"] in ["synthetic_fixture", "monitor_export"], "driver intent is not an observation")
    require(run["time_unit"] == plan["time_unit"], "time_unit mismatch")
    require(run["plan_sha256"] == digest(plan), "stale plan fingerprint")
    require(isinstance(run["events_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", run["events_sha256"]), "events hash required")
    fields(run["versions"], ["dut", "testbench", "monitor", "binding", "config", "checker", "simulator", "sampling"], "versions")
    for key, value in run["versions"].items():
        string(value, "versions." + key)
    fields(run["stages"], ["build", "run", "export"], "stages")
    allowed = ["passed", "failed", "not_run"]
    require(all(v in allowed for v in run["stages"].values()), "invalid stage status")
    if run["origin"] == "monitor_export":
        require(all(v == "passed" for v in run["stages"].values()), "invalid simulation run: all stages must pass")
    else:
        require(all(v == "not_run" for v in run["stages"].values()), "fixture must not claim simulation stages passed")


def validate_event(event, run):
    fields(event, ["event_id", "run_id", "timestamp_ticks", "channel", "subchannel", "rank",
                   "config_epoch", "reset_epoch", "kind", "command", "valid", "source_locator"], "event")
    identifier(event["event_id"], "event_id")
    require(event["run_id"] == run["run_id"], "mixed run IDs")
    for name in ["timestamp_ticks", "channel", "subchannel", "rank", "config_epoch", "reset_epoch"]:
        integer(event[name], name)
        require(event[name] < 2**63, f"{name}: exceeds backend range")
    require(type(event["valid"]) is bool, "valid must be boolean")
    require(event["kind"] in ["command", "reset"], "unsupported event kind")
    if event["kind"] == "reset":
        require(event["command"] is None and not event["valid"], "reset must have null command and valid=false")
    else:
        identifier(event["command"], "event.command")
    string(event["source_locator"], "source_locator")


def load_events(path, run):
    require(file_digest(path) == run["events_sha256"], "event file hash mismatch")
    events, seen, previous = [], {}, {}
    duplicate_count = 0
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        event = parse_json(line)
        validate_event(event, run)
        eid = event["event_id"]
        if eid in seen:
            require(seen[eid] == canonical(event), f"conflicting duplicate event: {eid}")
            duplicate_count += 1
            continue
        seen[eid] = canonical(event)
        scope = tuple(event[k] for k in ["channel", "subchannel", "rank"])
        if scope in previous:
            prev = previous[scope]
            require(event["timestamp_ticks"] > prev["timestamp_ticks"], f"line {line_number}: unordered or ambiguous scope timestamp")
            require(event["config_epoch"] >= prev["config_epoch"] and event["reset_epoch"] >= prev["reset_epoch"], "epoch regression")
        previous[scope] = event
        events.append(event)
    require(events, "empty event stream")
    return events, duplicate_count
