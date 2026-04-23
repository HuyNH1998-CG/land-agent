from __future__ import annotations

from time import perf_counter

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.graph import build_rental_agent_graph
from japan_rental_agent.agent.state import create_initial_state
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest, AgentResponse


class RentalAgentService:
    """Thin application service that invokes the LangGraph workflow."""

    def __init__(
        self,
        config: AppConfig | None = None,
        dependencies: AgentDependencies | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.dependencies = dependencies or AgentDependencies.from_config(self.config)
        self.graph = build_rental_agent_graph(self.dependencies)

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        initial_state = create_initial_state(request)
        started_at = perf_counter()
        final_state = self.graph.invoke(initial_state)
        elapsed_ms = int((perf_counter() - started_at) * 1000)
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

        meta = payload.setdefault("meta", {})
        if not meta.get("processing_time_ms"):
            meta["processing_time_ms"] = elapsed_ms

        return AgentResponse.model_validate(payload)
