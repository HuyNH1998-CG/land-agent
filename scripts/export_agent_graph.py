from __future__ import annotations

import argparse
import ast
import json
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH_SOURCE = REPO_ROOT / "src" / "japan_rental_agent" / "agent" / "graph.py"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "exports"


NODE_ROLES = {
    "START": "LangGraph entrypoint.",
    "input": "Normalize the incoming user request into agent state.",
    "intent_extraction": "Extract intent, constraints, comparison targets, output format, and language.",
    "clarification": "Ask for missing rental or comparison information before running tools.",
    "listing_search": "Search rental listings from public or local data providers.",
    "enrichment_ranking": "Add area context and rank listings against the user's priorities.",
    "response": "Build the user-facing answer, compare listings, or export results.",
    "error_retry": "Retry transient tool failures and draft a final error response when needed.",
    "END": "LangGraph terminal node.",
}

BUSINESS_RULES = {
    "search_path": (
        "A normal rental search must go from intent extraction to listing search, "
        "then enrichment/ranking, then response."
    ),
    "clarification_path": "Missing required fields must route to clarification before response.",
    "compare_path": "Comparison intent must route directly to response because comparison is handled there.",
    "retry_path": "Search and enrichment/ranking failures must route through error_retry.",
    "termination": "Only response should terminate the graph.",
    "reachability": "Every workflow node must be reachable from START and able to reach END.",
}


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    label: str | None = None
    kind: str = "normal"


@dataclass(frozen=True)
class GraphExport:
    source_file: str
    nodes: list[str]
    edges: list[GraphEdge]
    validation: dict[str, Any]


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in {"START", "END"}:
        return node.id
    return None


def _literal_dict(node: ast.AST) -> dict[str, str]:
    if not isinstance(node, ast.Dict):
        return {}

    result: dict[str, str] = {}
    for key_node, value_node in zip(node.keys, node.values):
        if key_node is None:
            continue
        key = _literal_string(key_node)
        value = _literal_string(value_node)
        if key and value:
            result[key] = value
    return result


def extract_graph(source_file: Path = DEFAULT_GRAPH_SOURCE) -> tuple[list[str], list[GraphEdge]]:
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    nodes: set[str] = {"START", "END"}
    edges: list[GraphEdge] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue

        if func.attr == "add_node" and node.args:
            name = _literal_string(node.args[0])
            if name:
                nodes.add(name)

        if func.attr == "add_edge" and len(node.args) >= 2:
            source = _literal_string(node.args[0])
            target = _literal_string(node.args[1])
            if source and target:
                nodes.update({source, target})
                edges.append(GraphEdge(source=source, target=target))

        if func.attr == "add_conditional_edges" and len(node.args) >= 3:
            source = _literal_string(node.args[0])
            mapping = _literal_dict(node.args[2])
            if source:
                nodes.add(source)
                for label, target in mapping.items():
                    nodes.add(target)
                    edges.append(GraphEdge(source=source, target=target, label=label, kind="conditional"))

    return sorted(nodes, key=_node_sort_key), edges


def _node_sort_key(node: str) -> tuple[int, str]:
    order = [
        "START",
        "input",
        "intent_extraction",
        "clarification",
        "listing_search",
        "enrichment_ranking",
        "error_retry",
        "response",
        "END",
    ]
    try:
        return (order.index(node), node)
    except ValueError:
        return (len(order), node)


def validate_graph(nodes: list[str], edges: list[GraphEdge]) -> dict[str, Any]:
    edge_set = {(edge.source, edge.target, edge.label) for edge in edges}
    adjacency = _adjacency(edges)
    reverse_adjacency = _reverse_adjacency(edges)

    checks: list[dict[str, str]] = []

    def check(rule: str, ok: bool, detail: str) -> None:
        checks.append(
            {
                "rule": rule,
                "status": "pass" if ok else "fail",
                "detail": detail,
            }
        )

    required_nodes = {
        "input",
        "intent_extraction",
        "clarification",
        "listing_search",
        "enrichment_ranking",
        "response",
        "error_retry",
    }
    missing_nodes = sorted(required_nodes.difference(nodes))
    check("required_nodes", not missing_nodes, f"Missing nodes: {missing_nodes or 'none'}")

    check(
        "entry_path",
        ("START", "input", None) in edge_set and ("input", "intent_extraction", None) in edge_set,
        "START must enter input, then intent_extraction.",
    )
    check(
        "search_path",
        _has_labeled_edge(edge_set, "intent_extraction", "listing_search", "search")
        and _has_labeled_edge(edge_set, "listing_search", "enrichment_ranking", "enrichment")
        and _has_labeled_edge(edge_set, "enrichment_ranking", "response", "response"),
        BUSINESS_RULES["search_path"],
    )
    check(
        "clarification_path",
        _has_labeled_edge(edge_set, "intent_extraction", "clarification", "clarification")
        and ("clarification", "response", None) in edge_set,
        BUSINESS_RULES["clarification_path"],
    )
    check(
        "compare_path",
        _has_labeled_edge(edge_set, "intent_extraction", "response", "response"),
        BUSINESS_RULES["compare_path"],
    )
    check(
        "retry_path",
        _has_labeled_edge(edge_set, "listing_search", "error_retry", "error")
        and _has_labeled_edge(edge_set, "enrichment_ranking", "error_retry", "error")
        and _has_labeled_edge(edge_set, "error_retry", "listing_search", "listing_search")
        and _has_labeled_edge(edge_set, "error_retry", "enrichment_ranking", "enrichment_ranking")
        and _has_labeled_edge(edge_set, "error_retry", "response", "response"),
        BUSINESS_RULES["retry_path"],
    )
    check(
        "termination",
        ("response", "END", None) in edge_set
        and not [edge for edge in edges if edge.target == "END" and edge.source != "response"],
        BUSINESS_RULES["termination"],
    )

    reachable = _reachable_from("START", adjacency)
    can_reach_end = _reachable_from("END", reverse_adjacency)
    workflow_nodes = set(nodes).difference({"START", "END"})
    unreachable = sorted(workflow_nodes.difference(reachable))
    dead_ends = sorted(workflow_nodes.difference(can_reach_end))
    check(
        "reachability",
        not unreachable and not dead_ends,
        f"Unreachable from START: {unreachable or 'none'}; cannot reach END: {dead_ends or 'none'}",
    )

    failures = [item for item in checks if item["status"] == "fail"]
    return {
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "failed_checks": len(failures),
        },
    }


def _has_labeled_edge(edge_set: set[tuple[str, str, str | None]], source: str, target: str, label: str) -> bool:
    return (source, target, label) in edge_set


def _adjacency(edges: list[GraphEdge]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for edge in edges:
        result.setdefault(edge.source, []).append(edge.target)
    return result


def _reverse_adjacency(edges: list[GraphEdge]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for edge in edges:
        result.setdefault(edge.target, []).append(edge.source)
    return result


def _reachable_from(start: str, adjacency: dict[str, list[str]]) -> set[str]:
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        for next_node in adjacency.get(current, []):
            if next_node in seen:
                continue
            seen.add(next_node)
            queue.append(next_node)
    return seen


def build_export(source_file: Path = DEFAULT_GRAPH_SOURCE) -> GraphExport:
    nodes, edges = extract_graph(source_file)
    return GraphExport(
        source_file=str(source_file.relative_to(REPO_ROOT)),
        nodes=nodes,
        edges=edges,
        validation=validate_graph(nodes, edges),
    )


def write_exports(export: GraphExport, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out_dir / "rental_agent_graph.json",
        "mermaid": out_dir / "rental_agent_graph.mmd",
        "dot": out_dir / "rental_agent_graph.dot",
        "validation": out_dir / "rental_agent_graph_validation.md",
    }
    paths["json"].write_text(_to_json(export), encoding="utf-8")
    paths["mermaid"].write_text(_to_mermaid(export), encoding="utf-8")
    paths["dot"].write_text(_to_dot(export), encoding="utf-8")
    paths["validation"].write_text(_to_validation_markdown(export), encoding="utf-8")
    return paths


def _to_json(export: GraphExport) -> str:
    payload = asdict(export)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _to_mermaid(export: GraphExport) -> str:
    lines = [
        "flowchart TD",
        "    START([START])",
        "    END([END])",
    ]
    for node in export.nodes:
        if node in {"START", "END"}:
            continue
        label = node.replace("_", " ")
        lines.append(f"    {node}[{label}]")
    for edge in export.edges:
        if edge.label:
            lines.append(f"    {edge.source} -- {edge.label} --> {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")
    return "\n".join(lines) + "\n"


def _to_dot(export: GraphExport) -> str:
    lines = ["digraph rental_agent_graph {"]
    lines.append('  rankdir="LR";')
    for node in export.nodes:
        shape = "oval" if node in {"START", "END"} else "box"
        label = node.replace("_", " ")
        lines.append(f'  "{node}" [label="{label}", shape="{shape}"];')
    for edge in export.edges:
        label = f' [label="{edge.label}"]' if edge.label else ""
        lines.append(f'  "{edge.source}" -> "{edge.target}"{label};')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _to_validation_markdown(export: GraphExport) -> str:
    lines = [
        "# Rental Agent Graph Validation",
        "",
        f"Source: `{export.source_file}`",
        f"Status: `{export.validation['status']}`",
        "",
        "## Nodes",
        "",
    ]
    for node in export.nodes:
        lines.append(f"- `{node}`: {NODE_ROLES.get(node, 'No role documented.')}")

    lines.extend(["", "## Business Rules", ""])
    for key, description in BUSINESS_RULES.items():
        lines.append(f"- `{key}`: {description}")

    lines.extend(["", "## Checks", ""])
    for check in export.validation["checks"]:
        lines.append(f"- `{check['status']}` `{check['rule']}`: {check['detail']}")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export and validate the Japan rental agent LangGraph.")
    parser.add_argument("--source", type=Path, default=DEFAULT_GRAPH_SOURCE, help="Path to graph.py.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Directory for exported graph artifacts.")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if validation fails.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export = build_export(args.source)
    paths = write_exports(export, args.out_dir)

    print(f"Graph validation: {export.validation['status']}")
    for name, path in paths.items():
        print(f"{name}: {path}")

    if args.strict and export.validation["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
