"""Emit a collector over decoded events, never a pin interface or decoder.

Generated SystemVerilog needs compilation and replay in the user's simulator.
The bounded primitive uses longint unsigned timestamps in plan.time_unit.
"""
from __future__ import annotations

from .contracts import bin_definitions, digest, require_ready


def generate_sv(plan):
    require_ready(plan)
    plan_hash = digest(plan)
    package_name = "cc_" + plan_hash[:12] + "_pkg"
    lines = ["// Generated monitor-event collector. No instruction decoding.",
             "// NOT validated by an HDL simulator. Compile and compare before use.",
             f"// plan_sha256: {plan_hash}", f"// timestamp unit: {plan['time_unit']}",
             "// Calls must be serialized; increasing timestamps per channel/subchannel/rank.",
             f"package {package_name};", "  class interval_collector;"]
    mappings = []
    lines += ["    longint unsigned last_timestamp[string];",
              "    longint unsigned config_epochs[string];",
              "    longint unsigned reset_epochs[string];"]
    for i, rule in enumerate(plan["rules"]):
        start = len(lines) + 1
        lines += [f"    // rule: {rule['id']} revision: {rule['revision']}",
                  f"    longint unsigned previous_{i}[string];",
                  f"    longint unsigned violations_{i};",
                  f"    longint unsigned suppressed_{i};",
                  f"    covergroup cg_{i} with function sample(int outcome);",
                  "      option.per_instance = 1;",
                  "      cp_interval: coverpoint outcome {",
                  "        bins at_bound = {1};",
                  "        bins above_bound = {2};",
                  "      }", "    endgroup"]
        mappings.append({"rule_id": rule["id"], "rule_revision": rule["revision"],
                         "requirement_id": rule["requirement_id"], "declaration_start_line": start,
                         "declaration_end_line": len(lines), "covergroup_symbol": f"cg_{i}"})
    lines += ["    function new();"]
    for i in range(len(plan["rules"])):
        lines += [f"      cg_{i} = new();", f"      violations_{i} = 0;", f"      suppressed_{i} = 0;"]
    lines += ["    endfunction", "", "    // Returns a per-call classification vector through an output array:",
              "    // -2=no target event, -1=suppressed, 0=violation, 1=at, 2=above.",
              "    // Adapter must log event_id, raw locator, epochs, operands and outcome.",
              "    function void observe(",
              "      input longint unsigned channel, subchannel, rank,",
              "      input longint unsigned config_epoch, reset_epoch, timestamp_ticks,",
              "      input bit is_reset, command_valid, input string command,",
              "      output int outcomes[]);",
              "      string scope_key;", "      longint unsigned delta;",
              '      scope_key = $sformatf("%0d/%0d/%0d", channel, subchannel, rank);',
              f"      outcomes = new[{len(plan['rules'])}];",
              "      foreach (outcomes[i]) outcomes[i] = -2;",
              "      if (last_timestamp.exists(scope_key)) begin",
              '        if (timestamp_ticks <= last_timestamp[scope_key]) $fatal(1, "Non-increasing scope timestamp");',
              "        if (config_epoch < config_epochs[scope_key] || reset_epoch < reset_epochs[scope_key])",
              '          $fatal(1, "Epoch regression");', "      end",
              "      if (!config_epochs.exists(scope_key) || config_epochs[scope_key] != config_epoch ||",
              "          reset_epochs[scope_key] != reset_epoch || is_reset) begin"]
    for i in range(len(plan["rules"])):
        lines.append(f"        previous_{i}.delete(scope_key);")
    lines += ["      end", "      config_epochs[scope_key] = config_epoch;",
              "      reset_epochs[scope_key] = reset_epoch;",
              "      last_timestamp[scope_key] = timestamp_ticks;", "      if (is_reset) return;"]
    for i, rule in enumerate(plan["rules"]):
        mappings[i]["sampling_start_line"] = len(lines) + 1
        condition = " || ".join(f'command == "{c}"' for c in rule["end_commands"])
        lines += [f"      if ({condition}) begin",
                  f"        if (!command_valid || !previous_{i}.exists(scope_key)) begin",
                  f"          suppressed_{i}++; outcomes[{i}] = -1;", "        end else begin",
                  f"          delta = timestamp_ticks - previous_{i}[scope_key];",
                  f"          if (delta < 64'd{rule['bound_ticks']}) begin",
                  f"            violations_{i}++; outcomes[{i}] = 0;",
                  f"          end else if (delta == 64'd{rule['bound_ticks']}) begin",
                  f"            outcomes[{i}] = 1; cg_{i}.sample(1);", "          end else begin",
                  f"            outcomes[{i}] = 2; cg_{i}.sample(2);", "          end", "        end", "      end",
                  f"      if (!command_valid) previous_{i}.delete(scope_key);",
                  f'      else if (command == "{rule["start_command"]}") previous_{i}[scope_key] = timestamp_ticks;']
        mappings[i]["sampling_end_line"] = len(lines)
    lines += ["    endfunction", "  endclass", "endpackage", ""]
    bins = bin_definitions(plan)
    for i, rule in enumerate(plan["rules"]):
        for b in bins:
            if b["rule_id"] == rule["id"]:
                b["generated_symbol"] = f"cg_{i}.cp_interval.{b['outcome']}"
                b["native_path"] = None  # resolved from actual elaborated instance, never guessed
    return "\n".join(lines), {
        "schema_version": 1, "plan_sha256": plan_hash, "package": package_name,
        "class": "interval_collector", "hdl_validation": "not_run",
        "mappings": mappings, "bins": bins,
    }
