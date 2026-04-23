from __future__ import annotations

from japan_rental_agent.agent.state import RentalAgentState


def input_node(state: RentalAgentState) -> RentalAgentState:
    history = list(state.get("conversation_history", []))
    history.append({"role": "user", "content": state.get("raw_input", "")})
    return {
        "conversation_history": history,
        "error_message": None,
        "error_code": None,
        "last_failed_node": None,
        "retry_target": None,
    }
