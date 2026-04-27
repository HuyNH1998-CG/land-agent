from __future__ import annotations

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.tools.support import criterion_label


def make_clarification_node(dependencies: AgentDependencies):
    def clarification_node(state: RentalAgentState) -> RentalAgentState:
        missing_fields = state.get("missing_fields", [])
        tool_trace = list(state.get("tool_trace", []))
        intent_label = state.get("intent_label", "search")
        response_language = state.get("response_language", "vi")

        if intent_label == "compare" and "selected_listings" in missing_fields:
            selected_listings = state.get("selected_listings", [])
            compare_targets = state.get("compare_targets", [])
            compare_criteria = state.get("compare_criteria", [])
            reply = _build_compare_clarification(
                selected_listings=selected_listings,
                compare_targets=compare_targets,
                compare_criteria=compare_criteria,
                language=response_language,
            )
            tool_trace.append("compare.clarification")
            return {
                "tool_trace": tool_trace,
                "response_payload": {
                    "status": "need_clarification",
                    "reply": reply,
                    "data": {
                        "filters_used": state.get("parsed_constraints", {}),
                        "listings": [],
                        "comparison": [],
                        "file": None,
                        "missing_fields": ["selected_listings"],
                    },
                    "meta": {
                        "tool_used": tool_trace,
                        "confidence": state.get("llm_confidence"),
                        "processing_time_ms": 0,
                    },
                    "error": None,
                },
            }

        draft = dependencies.agent_model.draft_clarification(
            raw_input=state.get("raw_input", ""),
            parsed_constraints=state.get("parsed_constraints", {}),
            missing_fields=missing_fields,
            conversation_history=state.get("conversation_history", []),
        )
        tool_trace.append("llm.clarification")

        return {
            "tool_trace": tool_trace,
            "response_payload": {
                "status": "need_clarification",
                "reply": draft.reply,
                "data": {
                    "filters_used": state.get("parsed_constraints", {}),
                    "listings": [],
                    "comparison": [],
                    "file": None,
                    "missing_fields": draft.missing_fields or missing_fields,
                },
                "meta": {
                    "tool_used": tool_trace,
                    "confidence": draft.confidence,
                    "processing_time_ms": 0,
                },
                "error": None,
            },
        }

    return clarification_node


def _build_compare_clarification(
    *,
    selected_listings: list[str],
    compare_targets: list[str],
    compare_criteria: list[str],
    language: str,
) -> str:
    criteria_text = _format_criteria(compare_criteria, language)
    unresolved_targets = compare_targets
    if compare_criteria and len(selected_listings) == 0 and len(compare_targets) <= 1:
        unresolved_targets = []

    if language == "en":
        if len(selected_listings) == 1:
            return (
                f"I only identified one listing to compare: `{selected_listings[0]}`. "
                f"Please send one more listing name or ID so I can compare them{criteria_text}."
            )
        if unresolved_targets:
            joined_targets = ", ".join(unresolved_targets[:2])
            return (
                f"I could not confidently resolve the two listings from your request ({joined_targets}). "
                f"Please send the exact full names or listing IDs of both homes{criteria_text}."
            )
        return f"Which two listings do you want to compare{criteria_text}? Please send their full names or listing IDs."

    if len(selected_listings) == 1:
        return (
            f"Tôi mới xác định được 1 căn để so sánh là `{selected_listings[0]}`. "
            f"Bạn hãy gửi thêm tên hoặc mã của một căn nữa để tôi so sánh{criteria_text}."
        )
    if unresolved_targets:
        joined_targets = ", ".join(unresolved_targets[:2])
        return (
            f"Tôi chưa xác định chắc 2 căn cần so sánh từ yêu cầu của bạn ({joined_targets}). "
            f"Bạn hãy gửi lại đúng tên đầy đủ hoặc mã listing của 2 căn{criteria_text}."
        )
    return f"Bạn muốn so sánh 2 căn nào{criteria_text}? Hãy gửi tên đầy đủ hoặc mã listing của từng căn."


def _format_criteria(compare_criteria: list[str], language: str) -> str:
    if not compare_criteria:
        return ""

    labels = [criterion_label(item, language) for item in compare_criteria]
    joined = " -> ".join(labels)
    if language == "en":
        return f" based on {joined}"
    return f" theo thứ tự {joined}"
