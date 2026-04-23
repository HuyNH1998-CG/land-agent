from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from japan_rental_agent.agent.nodes import (
    clarification_node,
    enrichment_ranking_node,
    error_retry_node,
    input_node,
    intent_extraction_node,
    listing_search_node,
    response_node,
    route_after_intent,
    route_after_search,
)
from japan_rental_agent.agent.state import RentalAgentState


def build_rental_agent_graph():
    workflow = StateGraph(RentalAgentState)

    workflow.add_node("input", input_node)
    workflow.add_node("intent_extraction", intent_extraction_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("listing_search", listing_search_node)
    workflow.add_node("enrichment_ranking", enrichment_ranking_node)
    workflow.add_node("response", response_node)
    workflow.add_node("error_retry", error_retry_node)

    workflow.add_edge(START, "input")
    workflow.add_edge("input", "intent_extraction")
    workflow.add_conditional_edges(
        "intent_extraction",
        route_after_intent,
        {
            "clarification": "clarification",
            "search": "listing_search",
        },
    )
    workflow.add_edge("clarification", "response")
    workflow.add_conditional_edges(
        "listing_search",
        route_after_search,
        {
            "error": "error_retry",
            "enrichment": "enrichment_ranking",
        },
    )
    workflow.add_edge("enrichment_ranking", "response")
    workflow.add_edge("error_retry", "response")
    workflow.add_edge("response", END)

    return workflow.compile()

