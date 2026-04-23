from __future__ import annotations

from japan_rental_agent.agent.state import RentalAgentState


def clarification_node(state: RentalAgentState) -> RentalAgentState:
    missing_fields = state.get("missing_fields", [])
    reply = "Please provide a bit more detail so I can continue."
    if missing_fields:
        reply = f"I still need these fields before searching: {', '.join(missing_fields)}."

    return {
        "response_payload": {
            "status": "need_clarification",
            "reply": reply,
            "data": {
                "filters_used": state.get("parsed_constraints", {}),
                "listings": [],
                "comparison": [],
                "file": None,
                "missing_fields": missing_fields,
            },
            "meta": {
                "tool_used": state.get("tool_trace", []),
                "confidence": 0.0,
                "processing_time_ms": 0,
            },
            "error": None,
        }
    }

