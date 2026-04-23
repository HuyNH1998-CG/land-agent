from __future__ import annotations

from japan_rental_agent.agent.graph import build_rental_agent_graph
from japan_rental_agent.agent.state import create_initial_state
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest, AgentResponse


class RentalAgentService:
    """Thin application service that invokes the LangGraph workflow."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self.graph = build_rental_agent_graph()

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        initial_state = create_initial_state(request)
        final_state = self.graph.invoke(initial_state)
        payload = final_state.get("response_payload")

        if not payload:
            return AgentResponse(
                status="error",
                reply="The workflow completed without a response payload.",
                error={
                    "code": "EMPTY_RESPONSE",
                    "message": "No response payload was produced by the graph.",
                },
            )

        return AgentResponse.model_validate(payload)

