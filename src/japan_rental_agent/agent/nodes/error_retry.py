from __future__ import annotations

from japan_rental_agent.agent.state import RentalAgentState


def error_retry_node(state: RentalAgentState) -> RentalAgentState:
    retry_count = state.get("retry_count", 0) + 1
    message = state.get("error_message") or "Unknown processing error."

    return {
        "retry_count": retry_count,
        "response_payload": {
            "status": "error",
            "reply": "I could not complete the request in the current skeleton flow.",
            "data": {
                "filters_used": state.get("parsed_constraints", {}),
                "listings": [],
                "comparison": [],
                "file": None,
                "missing_fields": [],
            },
            "meta": {
                "tool_used": state.get("tool_trace", []),
                "confidence": 0.0,
                "processing_time_ms": 0,
            },
            "error": {
                "code": "WORKFLOW_ERROR",
                "message": message,
            },
        },
    }

