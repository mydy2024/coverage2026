"""Command line for the independently usable first implementation slice."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .artifacts import (impact, input_references, new_directory, save_replay, trace_bin,
                        write_generation, write_json)
from .contracts import (ContractError, fields, read_json, readiness_blockers, require,
                        validate_plan)
from .replay import replay


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def doctor(config_path):
    config = read_json(config_path)
    fields(config, ["simulator", "workdir", "smoke_argv", "monitor_path"], "environment")
    missing = []
    for key in ["simulator", "workdir", "monitor_path"]:
        value = config[key]
        require(value is None or isinstance(value, str), f"{key}: expected string or null")
        if not value:
            missing.append(key + "_not_configured")
    require(isinstance(config["smoke_argv"], list) and all(isinstance(x, str) for x in config["smoke_argv"]), "smoke_argv must be an argument array")
    if not config["smoke_argv"]:
        missing.append("smoke_argv_not_configured")
    for key in ["workdir", "monitor_path"]:
        if config[key]:
            p = Path(config[key])
            if not p.is_absolute():
                p = Path(config_path).resolve().parent / p
            if not (p.is_dir() if key == "workdir" else p.is_file()):
                missing.append(key + "_not_found_on_this_host")
    found = {name: shutil.which(name) for name in ["vcs", "xrun", "vsim", "iverilog", "verilator", "slang"]}
    if config["simulator"] and not shutil.which(config["simulator"]):
        missing.append("configured_simulator_not_found_on_this_host")
    return {"status": "blocked" if missing else "configured_not_tested", "blockers": missing,
            "tools_on_this_host": found, "simulation_executed": False,
            "note": "Discovery only; smoke commands are never executed by doctor."}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="CoverageClosure event replay and evidence prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    d = commands.add_parser("doctor", help="Inspect local integration prerequisites without executing commands")
    d.add_argument("--config", type=Path, required=True)
    v = commands.add_parser("validate", help="Validate plan and source hashes; exit 3 for a valid but blocked plan")
    v.add_argument("--plan", type=Path, required=True)
    g = commands.add_parser("generate", help="Generate an event collector and source map; no interface/decoder")
    g.add_argument("--plan", type=Path, required=True)
    g.add_argument("--out", type=Path, required=True)
    r = commands.add_parser("replay", help="Replay exported monitor events; does not claim verified coverage")
    for key in ["plan", "run", "events", "out"]:
        r.add_argument("--" + key, type=Path, required=True)
    t = commands.add_parser("trace-bin", help="Trace bin to requirement, source, generated code and events")
    t.add_argument("--report", type=Path, required=True)
    t.add_argument("--bin", required=True)
    i = commands.add_parser("impact", help="Find affected rules and bins after a source/requirement/rule change")
    i.add_argument("--plan", type=Path, required=True)
    i.add_argument("--id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor(args.config)
            emit(result)
            return 3 if result["blockers"] else 0
        if args.command == "trace-bin":
            result = trace_bin(args.report, args.bin)
            emit(result)
            return 3 if result["freshness"] == "stale" else 0
        plan = validate_plan(read_json(args.plan), args.plan.resolve().parent)
        if args.command == "validate":
            blockers = readiness_blockers(plan)
            emit({"status": "blocked" if blockers else "ready_for_generation", "blockers": blockers,
                  "semantic_correctness_proven": False})
            return 3 if blockers else 0
        if args.command == "impact":
            emit(impact(plan, args.id))
            return 0
        if args.command == "generate":
            from .contracts import require_ready
            require_ready(plan)
            out = new_directory(args.out)
            source_map = write_generation(plan, out)
            write_json(out / "inputs.json", input_references(plan, args.plan))
            emit({"status": "generated_not_hdl_validated", "out": str(out), "package": source_map["package"]})
            return 0
        run = read_json(args.run)
        report = replay(plan, run, args.events, args.plan.resolve().parent)
        out = save_replay(report, plan, run, args.out, args.plan, args.run, args.events)
        emit({"status": report["status"], "summary": report["summary"], "report": str(out / "report.json"),
              "closure_claim": False})
        return 0
    except (ContractError, OSError, ValueError) as exc:
        emit({"status": "error", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
