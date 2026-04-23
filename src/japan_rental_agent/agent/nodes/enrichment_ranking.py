from __future__ import annotations

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState


def make_enrichment_ranking_node(dependencies: AgentDependencies):
    def enrichment_ranking_node(state: RentalAgentState) -> RentalAgentState:
        tool_trace = list(state.get("tool_trace", []))

        ranking_plan = dependencies.agent_model.plan_ranking(
            raw_input=state.get("raw_input", ""),
            parsed_constraints=state.get("parsed_constraints", {}),
            search_results=state.get("search_results", []),
            current_preferences=state.get("ranking_preferences", {}),
        )
        tool_trace.append("llm.ranking_plan")
        tool_trace.append(dependencies.enrichment_tool.name)

        try:
            enriched = dependencies.enrichment_tool.execute(
                listings=state.get("search_results", []),
                context=state.get("parsed_constraints", {}),
            )
            tool_trace.append(dependencies.ranking_tool.name)
            ranked = dependencies.ranking_tool.execute(
                listings=enriched.get("enriched", []),
                preferences=ranking_plan.preferences.as_tool_payload(),
            )
        except Exception as exc:
            return {
                "tool_trace": tool_trace,
                "ranking_preferences": ranking_plan.preferences.as_tool_payload(),
                "llm_confidence": ranking_plan.confidence,
                "error_message": str(exc),
                "error_code": "ENRICHMENT_RANKING_ERROR",
                "last_failed_node": "enrichment_ranking",
            }

        return {
            "enriched_results": enriched.get("enriched", []),
            "ranked_results": ranked.get("ranked", []),
            "ranking_preferences": ranking_plan.preferences.as_tool_payload(),
            "tool_trace": tool_trace,
            "llm_confidence": ranking_plan.confidence,
            "error_message": None,
            "error_code": None,
            "last_failed_node": None,
            "retry_target": None,
        }

    return enrichment_ranking_node
