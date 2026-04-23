from __future__ import annotations

from typing import Any, TypedDict

from japan_rental_agent.contracts import AgentRequest


class RentalAgentState(TypedDict, total=False):
    raw_input: str
    input_type: str
    session_id: str
    parsed_constraints: dict[str, Any]
    missing_fields: list[str]
    search_results: list[dict[str, Any]]
    enriched_results: list[dict[str, Any]]
    ranked_results: list[dict[str, Any]]
    comparison_results: list[dict[str, Any]]
    selected_output_format: str
    retry_count: int
    error_message: str | None
    conversation_history: list[dict[str, str]]
    response_payload: dict[str, Any]
    selected_listings: list[str]
    filters_used: dict[str, Any]
    tool_trace: list[str]
    exported_file: str | None


def create_initial_state(request: AgentRequest) -> RentalAgentState:
    return RentalAgentState(
        raw_input=request.message,
        input_type=request.input_type,
        session_id=request.session_id,
        parsed_constraints={},
        missing_fields=[],
        search_results=[],
        enriched_results=[],
        ranked_results=[],
        comparison_results=[],
        selected_output_format=request.options.output_format,
        retry_count=0,
        error_message=None,
        conversation_history=[],
        response_payload={},
        selected_listings=request.context.selected_listings,
        filters_used=request.context.previous_filters,
        tool_trace=[],
        exported_file=None,
    )
