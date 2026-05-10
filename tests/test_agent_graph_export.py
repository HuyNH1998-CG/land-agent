from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_agent_graph.py"


def _load_export_module():
    spec = importlib.util.spec_from_file_location("export_agent_graph", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_agent_graph_matches_real_estate_business_rules() -> None:
    module = _load_export_module()

    export = module.build_export()

    assert export.validation["status"] == "pass"
    assert export.validation["summary"]["node_count"] == 9
    assert export.validation["summary"]["failed_checks"] == 0


def test_agent_graph_exports_expected_formats() -> None:
    module = _load_export_module()
    export = module.build_export()
    out_dir = Path(__file__).resolve().parents[1] / "data" / "exports" / "_test_graph_export"
    if out_dir.exists():
        shutil.rmtree(out_dir)

    paths = module.write_exports(export, out_dir)

    assert set(paths) == {"json", "mermaid", "dot", "validation"}
    assert "flowchart TD" in paths["mermaid"].read_text(encoding="utf-8")
    assert "digraph rental_agent_graph" in paths["dot"].read_text(encoding="utf-8")
    assert '"validation"' in paths["json"].read_text(encoding="utf-8")
    assert "Status: `pass`" in paths["validation"].read_text(encoding="utf-8")
