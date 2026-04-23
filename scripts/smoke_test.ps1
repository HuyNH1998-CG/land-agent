$ErrorActionPreference = "Stop"

Write-Host "[1/2] Running pytest smoke test..." -ForegroundColor Cyan
python -m pytest tests/test_smoke_imports.py -q

Write-Host "[2/2] Running direct agent smoke test..." -ForegroundColor Cyan
@'
from japan_rental_agent.agent import AgentDependencies, RentalAgentService
from japan_rental_agent.agent.llm import FallbackAgentModel
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest

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
    ),
)
response = service.handle_request(
    AgentRequest(
        session_id="smoke",
        message="Find me a rental in Tokyo under 80000 yen near station",
    )
)

print("status=" + response.status)
print("reply=" + response.reply)
print("tools=" + ",".join(response.meta.tool_used))
'@ | python -

Write-Host "Smoke test completed." -ForegroundColor Green
