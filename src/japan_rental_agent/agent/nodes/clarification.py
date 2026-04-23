from __future__ import annotations

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState


def make_clarification_node(dependencies: AgentDependencies):
    def clarification_node(state: RentalAgentState) -> RentalAgentState:
        missing_fields = state.get("missing_fields", [])
        tool_trace = list(state.get("tool_trace", []))
        draft = dependencies.agent_model.draft_clarification(
            raw_input=state.get("raw_input", ""),
            parsed_constraints=state.get("parsed_constraints", {}),
            missing_fields=missing_fields,
            conversation_history=state.get("conversation_history", []),
        )
        tool_trace.append("llm.clarification")

        return {
            "tool_trace": tool_trace,
            "response_payload": {
                "status": "need_clarification",
                "reply": draft.reply,
                "data": {
                    "filters_used": state.get("parsed_constraints", {}),
                    "listings": [],
                    "comparison": [],
                    "file": None,
                    "missing_fields": draft.missing_fields or missing_fields,
                },
                "meta": {
                    "tool_used": tool_trace,
                    "confidence": draft.confidence,
                    "processing_time_ms": 0,
                },
                "error": None,
            },
        }

    return clarification_node
