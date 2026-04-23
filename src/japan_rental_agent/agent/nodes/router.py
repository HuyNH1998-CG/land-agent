from __future__ import annotations

from typing import Literal

from japan_rental_agent.agent.state import RentalAgentState


def route_after_intent(state: RentalAgentState) -> Literal["clarification", "search"]:
    if state.get("missing_fields"):
        return "clarification"
    return "search"


def route_after_search(state: RentalAgentState) -> Literal["error", "enrichment"]:
    if state.get("error_message"):
        return "error"
    return "enrichment"

