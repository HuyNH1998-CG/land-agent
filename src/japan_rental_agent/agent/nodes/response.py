from __future__ import annotations

from japan_rental_agent.agent.state import RentalAgentState


def response_node(state: RentalAgentState) -> RentalAgentState:
    if state.get("response_payload"):
        return {}

    listings = state.get("ranked_results") or state.get("search_results") or []
    reply = "Project skeleton is ready. Search logic has not been implemented yet."
    if listings:
        reply = f"I found {len(listings)} placeholder listing results."

    return {
        "response_payload": {
            "status": "success",
            "reply": reply,
            "data": {
                "filters_used": state.get("filters_used", {}),
                "listings": listings,
                "comparison": state.get("comparison_results", []),
                "file": state.get("exported_file"),
                "missing_fields": [],
            },
            "meta": {
                "tool_used": state.get("tool_trace", []),
                "confidence": 0.35,
                "processing_time_ms": 0,
            },
            "error": None,
        }
    }

