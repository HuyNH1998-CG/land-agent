from __future__ import annotations

from typing import Any, TypedDict

from japan_rental_agent.contracts import AgentRequest


class RentalAgentState(TypedDict, total=False):
    raw_input: str
    input_type: str
    session_id: str
    top_k: int
    intent_label: str
    parsed_constraints: dict[str, Any]
    missing_fields: list[str]
    ranking_preferences: dict[str, Any]
    search_results: list[dict[str, Any]]
    search_total: int
    enriched_results: list[dict[str, Any]]
    ranked_results: list[dict[str, Any]]
    comparison_results: list[dict[str, Any]]
    selected_output_format: str
    retry_count: int
    error_message: str | None
    error_code: str | None
    last_failed_node: str | None
    retry_target: str | None
    conversation_history: list[dict[str, str]]
    response_payload: dict[str, Any]
    selected_listings: list[str]
    compare_targets: list[str]
    compare_criteria: list[str]
    response_language: str
    recent_listings: list[dict[str, Any]]
    filters_used: dict[str, Any]
    tool_trace: list[str]
    exported_file: str | None
    llm_confidence: float | None


def create_initial_state(request: AgentRequest) -> RentalAgentState:
    return RentalAgentState(
        raw_input=request.message,
        input_type=request.input_type,
        session_id=request.session_id,
        top_k=request.options.top_k,
        intent_label="search",
        parsed_constraints={},
        missing_fields=[],
        ranking_preferences={},
        search_results=[],
        search_total=0,
        enriched_results=[],
        ranked_results=[],
        comparison_results=[],
        selected_output_format=request.options.output_format,
        retry_count=0,
        error_message=None,
        error_code=None,
        last_failed_node=None,
        retry_target=None,
        conversation_history=request.context.conversation_history,
        response_payload={},
        selected_listings=request.context.selected_listings,
        compare_targets=[],
        compare_criteria=[],
        response_language="vi",
        recent_listings=request.context.recent_listings,
        filters_used=request.context.previous_filters,
        tool_trace=[],
        exported_file=None,
        llm_confidence=None,
    )
