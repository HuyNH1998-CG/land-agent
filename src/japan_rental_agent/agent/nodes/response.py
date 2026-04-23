from __future__ import annotations

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.agent.utils import normalize_listings


def make_response_node(dependencies: AgentDependencies):
    def response_node(state: RentalAgentState) -> RentalAgentState:
        if state.get("response_payload"):
            return {}

        tool_trace = list(state.get("tool_trace", []))
        raw_listings = state.get("ranked_results") or state.get("search_results") or []
        top_k = state.get("top_k", 5)
        normalized_listings = normalize_listings(raw_listings, top_k=top_k)
        draft = dependencies.agent_model.draft_response(
            raw_input=state.get("raw_input", ""),
            filters_used=state.get("filters_used", {}),
            listings=normalized_listings,
            output_format=state.get("selected_output_format", "chat"),
            tool_trace=tool_trace,
        )
        tool_trace.append("llm.response")

        return {
            "tool_trace": tool_trace,
            "response_payload": {
                "status": "success",
                "reply": draft.reply,
                "data": {
                    "filters_used": state.get("filters_used", {}),
                    "listings": normalized_listings,
                    "comparison": state.get("comparison_results", []),
                    "file": state.get("exported_file"),
                    "missing_fields": [],
                },
                "meta": {
                    "tool_used": tool_trace,
                    "confidence": draft.confidence or state.get("llm_confidence"),
                    "processing_time_ms": 0,
                },
                "error": None,
            },
        }

    return response_node
