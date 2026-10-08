"""Static front-end checks for the standalone DDR5 Vref SV delivery."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools/python"))


def compile_group(names):
    import pyslang
    from pyslang.ast import Compilation
    from pyslang.syntax import SyntaxTree

    delivery = ROOT / "delivery/ddr5_vref_v1"
    compilation = Compilation()
    trees = []
    for name in names:
        tree = SyntaxTree.fromFile(str(delivery / name))
        trees.append(tree)
        compilation.addSyntaxTree(tree)
    diagnostics = compilation.getAllDiagnostics()
    return {
        "files": names,
        "diagnostics": len(diagnostics),
        "errors": sum(item.isError() for item in diagnostics),
        "messages": pyslang.DiagnosticEngine.reportAll(
            trees[0].sourceManager, diagnostics
        ),
    }


def check():
    import pyslang

    groups = [
        compile_group([
            "ddr5_vref_cov_pkg.sv",
            "ddr5_vref_cov_if.sv",
            "ddr5_vref_adapter_template.sv",
        ]),
        compile_group([
            "ddr5_vref_cov_pkg.sv",
            "ddr5_vref_cov_if.sv",
            "ddr5_vref_smoke_tb.sv",
        ]),
    ]
    return {
        "tool": "pyslang",
        "version": pyslang.__version__,
        "groups": groups,
        "passed": all(group["errors"] == 0 for group in groups),
        "simulation_performed": False,
        "real_tb_binding_validated": False,
    }


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
