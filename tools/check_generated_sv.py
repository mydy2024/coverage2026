"""Optional real SV front-end checks; no simulation or functional equivalence claim."""
from pathlib import Path
import copy
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / ".tools/python")]
from coverage_closure.codegen import generate_sv
from coverage_closure.contracts import read_json


def check():
    import pyslang
    from pyslang.syntax import SyntaxTree
    from pyslang.ast import Compilation

    base = read_json(ROOT / "examples/min_interval/plan.json")
    same_command = copy.deepcopy(base)
    same_command["rules"][0]["end_commands"] = ["START"]
    multiple = copy.deepcopy(base)
    second = copy.deepcopy(base["rules"][0])
    second.update(id="rel.fixture.second", start_command="OTHER", end_commands=["END", "STOP"], bound_ticks=7)
    multiple["rules"].append(second)
    results = []
    for name, plan in [("single_rule", base), ("start_equals_end", same_command), ("multiple_rules", multiple)]:
        sv, mapping = generate_sv(plan)
        harness = '''
module compile_probe;
  import PACKAGE::*;
  interval_collector collector;
  int results[];
  initial begin
    collector = new();
    collector.observe(0, 0, 0, 0, 0, 0, 0, 1, "START", results);
    collector.observe(0, 0, 0, 0, 0, 4, 0, 1, "END", results);
    collector.observe(0, 0, 0, 0, 1, 5, 1, 0, "", results);
  end
endmodule
'''.replace("PACKAGE", mapping["package"])
        tree = SyntaxTree.fromText(sv + harness)
        comp = Compilation()
        comp.addSyntaxTree(tree)
        diags = comp.getAllDiagnostics()
        results.append({"case": name, "diagnostics": len(diags), "errors": sum(d.isError() for d in diags),
                        "messages": pyslang.DiagnosticEngine.reportAll(tree.sourceManager, diags)})
    return {"tool": "pyslang", "version": pyslang.__version__, "checks": results,
            "passed": all(r["errors"] == 0 for r in results),
            "simulation_performed": False, "python_sv_equivalence_proven": False}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
