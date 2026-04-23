from japan_rental_agent.agent import RentalAgentService
from japan_rental_agent.contracts import AgentRequest


def test_service_bootstraps() -> None:
    service = RentalAgentService()
    response = service.handle_request(
        AgentRequest(
            session_id="test-session",
            message="Find me a rental in Tokyo",
        )
    )

    assert response.status in {"success", "need_clarification", "error"}
