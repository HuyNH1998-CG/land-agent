from __future__ import annotations

from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.tools import AreaEnrichmentTool, RankingTool


def enrichment_ranking_node(state: RentalAgentState) -> RentalAgentState:
    enrichment_tool = AreaEnrichmentTool()
    ranking_tool = RankingTool()
    tool_trace = list(state.get("tool_trace", []))
    tool_trace.extend([enrichment_tool.name, ranking_tool.name])

    enriched = enrichment_tool.execute(
        listings=state.get("search_results", []),
        context=state.get("parsed_constraints", {}),
    )
    ranked = ranking_tool.execute(
        listings=enriched.get("enriched", []),
        preferences={},
    )

    return {
        "enriched_results": enriched.get("enriched", []),
        "ranked_results": ranked.get("ranked", []),
        "tool_trace": tool_trace,
    }

