"""Recreate authored fixtures, explicitly separated from DDR5 simulation evidence."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from coverage_closure.artifacts import write_json
from coverage_closure.contracts import canonical, digest, file_digest


def main():
    folder = ROOT / "examples" / "min_interval"
    plan = {
        "schema_version": 1, "plan_id": "fixture.min_interval", "revision": 1,
        "protocol": "synthetic_fixture_not_ddr5", "time_unit": "ns",
        "sources": [{"id": "src.fixture", "path": "spec.md", "sha256": file_digest(folder / "spec.md"),
                     "locator": "Synthetic min-interval fixture, paragraphs 2-3"}],
        "requirements": [{"id": "req.fixture.interval", "source_ids": ["src.fixture"],
                          "text": "END follows latest START by at least 4 ns in the same scope and epoch.",
                          "review_status": "reviewed"}],
        "rules": [{"id": "rel.fixture.interval", "revision": 1, "requirement_id": "req.fixture.interval",
                   "review_status": "reviewed", "blockers": [], "op": "min_interval",
                   "start_command": "START", "end_commands": ["END"], "bound_ticks": 4,
                   "history_policy": "latest_start", "start_anchor": "observed_START_timestamp",
                   "end_anchor": "observed_END_timestamp"}],
    }
    write_json(folder / "plan.json", plan)
    scenarios = {
        "baseline": [(0, "START"), (6, "END")],
        "directed": [(0, "START"), (6, "END"), (10, "START"), (14, "END")],
        "negative": [(0, "START"), (3, "END")],
    }
    for label, sequence in scenarios.items():
        run_id = "fixture." + label
        events = [{"event_id": f"e{i}", "run_id": run_id, "timestamp_ticks": timestamp,
                   "channel": 0, "subchannel": 0, "rank": 0, "config_epoch": 0, "reset_epoch": 0,
                   "kind": "command", "command": command, "valid": True,
                   "source_locator": f"authored_fixture:{label}:row{i}"}
                  for i, (timestamp, command) in enumerate(sequence)]
        path = folder / (label + ".events.jsonl")
        path.write_text("\n".join(canonical(e) for e in events) + "\n", encoding="utf-8")
        run = {"schema_version": 1, "run_id": run_id, "origin": "synthetic_fixture", "time_unit": "ns",
               "plan_sha256": digest(plan), "events_sha256": file_digest(path),
               "versions": {key: "fixture-only:no-" + key for key in
                            ["dut", "testbench", "monitor", "binding", "config", "checker", "simulator", "sampling"]},
               "stages": {key: "not_run" for key in ["build", "run", "export"]}}
        write_json(folder / (label + ".run.json"), run)
    draft_dir = ROOT / "examples" / "ddr5_vref"
    draft_dir.mkdir(parents=True, exist_ok=True)
    jedec = ROOT.parent / "JESD79-5D.PDF"
    draft = {"schema_version": 1, "plan_id": "ddr5.vref.draft", "revision": 1, "protocol": "DDR5",
             "time_unit": "ps", "sources": [], "requirements": [], "rules": []}
    for command, physical_page, printed_page, table in [("VrefCA", 270, 234, 125), ("VrefCS", 271, 235, 127)]:
        name = command.lower()
        draft["sources"].append({"id": "src.ddr5." + name, "path": "../../../JESD79-5D.PDF",
                                  "sha256": file_digest(jedec),
                                  "locator": f"physical page {physical_page}; printed page {printed_page}; Table {table}; timing figure and surrounding text also required"})
        draft["requirements"].append({"id": "req.ddr5." + name, "source_ids": ["src.ddr5." + name],
                                       "text": f"{command} to next valid command delay; numeric tMRD and anchors unresolved.",
                                       "review_status": "draft"})
        draft["rules"].append({"id": "rel.ddr5." + name, "revision": 1, "requirement_id": "req.ddr5." + name,
                                "review_status": "draft", "blockers": ["event_anchors_unreviewed", "tMRD_config_unresolved",
                                                                           "end_command_scope_not_frozen", "monitor_binding_missing"],
                                "op": "min_interval", "start_command": command, "end_commands": ["NOP"],
                                "bound_ticks": None, "history_policy": "latest_start",
                                "start_anchor": "pending_timing_figure_review", "end_anchor": "pending_timing_figure_review"})
    write_json(draft_dir / "plan.draft.json", draft)
    print("Authored synthetic fixtures and blocked DDR5 draft created. No simulation results generated.")


if __name__ == "__main__":
    main()
