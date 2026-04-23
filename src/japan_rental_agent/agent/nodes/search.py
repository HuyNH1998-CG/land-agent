from __future__ import annotations

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState


def make_listing_search_node(dependencies: AgentDependencies):
    def listing_search_node(state: RentalAgentState) -> RentalAgentState:
        tool_trace = list(state.get("tool_trace", []))
        tool_trace.append(dependencies.search_tool.name)

        try:
            search_result = dependencies.search_tool.execute(state.get("parsed_constraints", {}))
        except Exception as exc:
            return {
                "tool_trace": tool_trace,
                "error_message": str(exc),
                "error_code": "SEARCH_TOOL_ERROR",
                "last_failed_node": "listing_search",
            }

        results = search_result.get("results", [])
        if not isinstance(results, list):
            return {
                "tool_trace": tool_trace,
                "error_message": "Search tool returned an invalid `results` payload.",
                "error_code": "SEARCH_TOOL_INVALID_PAYLOAD",
                "last_failed_node": "listing_search",
            }

        return {
            "search_results": results,
            "search_total": int(search_result.get("total", len(results))),
            "filters_used": search_result.get("filters_used", state.get("parsed_constraints", {})),
            "tool_trace": tool_trace,
            "error_message": None,
            "error_code": None,
            "last_failed_node": None,
            "retry_target": None,
        }

    return listing_search_node
