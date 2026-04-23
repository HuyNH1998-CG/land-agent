from __future__ import annotations

from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.tools import QueryParserTool


def intent_extraction_node(state: RentalAgentState) -> RentalAgentState:
    parser = QueryParserTool()
    parsed = parser.execute(state.get("raw_input", ""))
    tool_trace = list(state.get("tool_trace", []))
    tool_trace.append(parser.name)

    return {
        "parsed_constraints": parsed.get("constraints", {}),
        "missing_fields": parsed.get("missing_fields", []),
        "tool_trace": tool_trace,
    }

