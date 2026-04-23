from __future__ import annotations

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState


def make_error_retry_node(dependencies: AgentDependencies):
    def error_retry_node(state: RentalAgentState) -> RentalAgentState:
        retry_count = state.get("retry_count", 0) + 1
        message = state.get("error_message") or "Unknown processing error."
        tool_trace = list(state.get("tool_trace", []))
        tool_trace.append("error_retry")

        failed_node = state.get("last_failed_node")
        if failed_node in {"listing_search", "enrichment_ranking"} and retry_count <= dependencies.config.agent_max_retries:
            return {
                "retry_count": retry_count,
                "retry_target": failed_node,
                "tool_trace": tool_trace,
            }

        draft = dependencies.agent_model.draft_error(
            raw_input=state.get("raw_input", ""),
            error_message=message,
            retry_count=retry_count,
            last_failed_node=failed_node,
        )
        tool_trace.append("llm.error")

        return {
            "retry_count": retry_count,
            "retry_target": None,
            "tool_trace": tool_trace,
            "response_payload": {
                "status": "error",
                "reply": draft.reply,
                "data": {
                    "filters_used": state.get("parsed_constraints", {}),
                    "listings": [],
                    "comparison": [],
                    "file": None,
                    "missing_fields": [],
                },
                "meta": {
                    "tool_used": tool_trace,
                    "confidence": draft.confidence,
                    "processing_time_ms": 0,
                },
                "error": {
                    "code": state.get("error_code") or draft.code,
                    "message": message,
                },
            },
        }

    return error_retry_node
