from __future__ import annotations

from dataclasses import dataclass

from japan_rental_agent.agent.llm import AgentModelProtocol, create_agent_model
from japan_rental_agent.config import AppConfig
from japan_rental_agent.tools import (
    AreaEnrichmentTool,
    ComparisonTool,
    ExportTool,
    ListingSearchTool,
    QueryParserTool,
    RankingTool,
)


@dataclass(slots=True)
class AgentDependencies:
    config: AppConfig
    agent_model: AgentModelProtocol
    parser_tool: QueryParserTool | None
    search_tool: ListingSearchTool
    enrichment_tool: AreaEnrichmentTool
    ranking_tool: RankingTool
    comparison_tool: ComparisonTool
    export_tool: ExportTool

    @classmethod
    def from_config(cls, config: AppConfig) -> "AgentDependencies":
        return cls(
            config=config,
            agent_model=create_agent_model(config),
            parser_tool=QueryParserTool(config),
            search_tool=ListingSearchTool(config),
            enrichment_tool=AreaEnrichmentTool(config),
            ranking_tool=RankingTool(),
            comparison_tool=ComparisonTool(config),
            export_tool=ExportTool(config),
        )
