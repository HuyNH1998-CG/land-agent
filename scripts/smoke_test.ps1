$ErrorActionPreference = "Stop"

Write-Host "[1/2] Running pytest smoke test..." -ForegroundColor Cyan
python -m pytest tests/test_smoke_imports.py -q

Write-Host "[2/2] Running direct agent smoke test..." -ForegroundColor Cyan
@'
from japan_rental_agent.agent import RentalAgentService
from japan_rental_agent.contracts import AgentRequest

service = RentalAgentService()
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
