from __future__ import annotations

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.agent.utils import merge_constraints


def make_intent_extraction_node(dependencies: AgentDependencies):
    def intent_extraction_node(state: RentalAgentState) -> RentalAgentState:
        tool_trace = list(state.get("tool_trace", []))
        parser_hints: dict[str, object] = {}

        if dependencies.parser_tool is not None:
            try:
                parser_output = dependencies.parser_tool.execute(state.get("raw_input", ""))
                parser_hints = parser_output.get("constraints", {})
                tool_trace.append(dependencies.parser_tool.name)
            except Exception:
                tool_trace.append("parser_error")

        intent = dependencies.agent_model.extract_intent(
            message=state.get("raw_input", ""),
            previous_filters=state.get("filters_used", {}),
            selected_listings=state.get("selected_listings", []),
            conversation_history=state.get("conversation_history", []),
            output_format=state.get("selected_output_format", "chat"),
            parser_hints=parser_hints,
        )
        tool_trace.append("llm.intent")

        merged_constraints = merge_constraints(
            state.get("filters_used", {}),
            parser_hints,
            intent.constraints.model_dump(exclude_none=True),
        )

        return {
            "intent_label": intent.intent,
            "parsed_constraints": merged_constraints,
            "filters_used": merged_constraints,
            "missing_fields": intent.missing_fields,
            "ranking_preferences": intent.ranking_preferences.as_tool_payload(),
            "selected_output_format": intent.output_format or state.get("selected_output_format", "chat"),
            "tool_trace": tool_trace,
            "llm_confidence": intent.confidence,
            "error_message": None,
            "error_code": None,
            "last_failed_node": None,
            "retry_target": None,
        }

    return intent_extraction_node
