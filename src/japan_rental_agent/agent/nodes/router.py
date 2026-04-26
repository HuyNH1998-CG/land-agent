from __future__ import annotations

from typing import Literal

from japan_rental_agent.agent.state import RentalAgentState


def route_after_intent(state: RentalAgentState) -> Literal["clarification", "search", "response"]:
    if state.get("missing_fields"):
        return "clarification"
    if state.get("intent_label") == "compare":
        return "response"
    return "search"


def route_after_search(state: RentalAgentState) -> Literal["error", "enrichment"]:
    if state.get("error_message"):
        return "error"
    return "enrichment"


def route_after_enrichment(state: RentalAgentState) -> Literal["error", "response"]:
    if state.get("error_message"):
        return "error"
    return "response"


def route_after_error(
    state: RentalAgentState,
) -> Literal["listing_search", "enrichment_ranking", "response"]:
    retry_target = state.get("retry_target")
    if retry_target == "listing_search":
        return "listing_search"
    if retry_target == "enrichment_ranking":
        return "enrichment_ranking"
    return "response"
