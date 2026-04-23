from __future__ import annotations

from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.tools import ListingSearchTool


def listing_search_node(state: RentalAgentState) -> RentalAgentState:
    search_tool = ListingSearchTool()
    tool_trace = list(state.get("tool_trace", []))
    tool_trace.append(search_tool.name)

    search_result = search_tool.execute(state.get("parsed_constraints", {}))
    return {
        "search_results": search_result.get("results", []),
        "filters_used": search_result.get("filters_used", {}),
        "tool_trace": tool_trace,
    }

