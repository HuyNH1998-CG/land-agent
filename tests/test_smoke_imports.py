from japan_rental_agent.agent import AgentDependencies, RentalAgentService
from japan_rental_agent.agent.llm import FallbackAgentModel
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest


def test_service_bootstraps() -> None:
    config = AppConfig(llm_api_key=None)
    default_dependencies = AgentDependencies.from_config(config)
    service = RentalAgentService(
        config=config,
        dependencies=AgentDependencies(
            config=config,
            agent_model=FallbackAgentModel(),
            parser_tool=None,
            search_tool=default_dependencies.search_tool,
            enrichment_tool=default_dependencies.enrichment_tool,
            ranking_tool=default_dependencies.ranking_tool,
            comparison_tool=default_dependencies.comparison_tool,
            export_tool=default_dependencies.export_tool,
        ),
    )
    response = service.handle_request(
        AgentRequest(
            session_id="test-session",
            message="Find me a rental in Tokyo",
        )
    )

    assert response.status in {"success", "need_clarification", "error"}
