from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.nodes import (
    input_node,
    make_clarification_node,
    make_enrichment_ranking_node,
    make_error_retry_node,
    make_intent_extraction_node,
    make_listing_search_node,
    make_response_node,
    route_after_enrichment,
    route_after_error,
    route_after_intent,
    route_after_search,
)
from japan_rental_agent.agent.state import RentalAgentState


def build_rental_agent_graph(dependencies: AgentDependencies):
    workflow = StateGraph(RentalAgentState)

    workflow.add_node("input", input_node)
    workflow.add_node("intent_extraction", make_intent_extraction_node(dependencies))
    workflow.add_node("clarification", make_clarification_node(dependencies))
    workflow.add_node("listing_search", make_listing_search_node(dependencies))
    workflow.add_node("enrichment_ranking", make_enrichment_ranking_node(dependencies))
    workflow.add_node("response", make_response_node(dependencies))
    workflow.add_node("error_retry", make_error_retry_node(dependencies))

    workflow.add_edge(START, "input")
    workflow.add_edge("input", "intent_extraction")
    workflow.add_conditional_edges(
        "intent_extraction",
        route_after_intent,
        {
            "clarification": "clarification",
            "response": "response",
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
    workflow.add_conditional_edges(
        "enrichment_ranking",
        route_after_enrichment,
        {
            "error": "error_retry",
            "response": "response",
        },
    )
    workflow.add_conditional_edges(
        "error_retry",
        route_after_error,
        {
            "listing_search": "listing_search",
            "enrichment_ranking": "enrichment_ranking",
            "response": "response",
        },
    )
    workflow.add_edge("response", END)

    return workflow.compile()
