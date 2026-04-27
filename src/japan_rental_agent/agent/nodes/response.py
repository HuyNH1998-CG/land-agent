from __future__ import annotations

from typing import Any

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.agent.utils import normalize_listings
from japan_rental_agent.tools.support import DEFAULT_COMPARE_CRITERIA, criterion_label


def make_response_node(dependencies: AgentDependencies):
    def response_node(state: RentalAgentState) -> RentalAgentState:
        if state.get("response_payload"):
            return {}

        tool_trace = list(state.get("tool_trace", []))
        intent_label = state.get("intent_label", "search")
        raw_listings = state.get("ranked_results") or state.get("search_results") or []
        top_k = state.get("top_k", 5)
        normalized_listings = normalize_listings(raw_listings, top_k=top_k)
        comparison_results: list[dict[str, Any]] = list(state.get("comparison_results", []))
        exported_file = state.get("exported_file")

        if intent_label == "compare":
            selected_listing_ids = state.get("selected_listings", [])
            compare_criteria = state.get("compare_criteria") or list(DEFAULT_COMPARE_CRITERIA)
            response_language = state.get("response_language", "vi")
            comparison_payload = dependencies.comparison_tool.execute(
                selected_listing_ids,
                compare_criteria=compare_criteria,
                language=response_language,
                listing_context=state.get("recent_listings", []),
            )
            comparison_results = comparison_payload.get("comparison", [])
            tool_trace.append(dependencies.comparison_tool.name)
            comparison_count = len(comparison_results)
            reply = _build_compare_reply(
                comparison_results=comparison_results,
                compare_criteria=compare_criteria,
                language=response_language,
            )

            return {
                "tool_trace": tool_trace,
                "comparison_results": comparison_results,
                "exported_file": exported_file,
                "response_payload": {
                    "status": "success" if comparison_count >= 2 else "need_clarification",
                    "reply": reply,
                    "data": {
                        "filters_used": {
                            "operation": "compare",
                            "selected_listings": selected_listing_ids,
                            "compare_criteria": compare_criteria,
                            "response_language": response_language,
                        },
                        "listings": [],
                        "comparison": comparison_results,
                        "file": None,
                        "missing_fields": [] if comparison_count >= 2 else ["selected_listings"],
                    },
                    "meta": {
                        "tool_used": tool_trace,
                        "confidence": state.get("llm_confidence"),
                        "processing_time_ms": 0,
                    },
                    "error": None,
                },
            }

        export_format = state.get("selected_output_format", "chat")
        export_candidates = raw_listings[:top_k]
        if export_format != "chat" and export_candidates:
            export_payload = dependencies.export_tool.execute(export_candidates, export_format)
            exported_file = export_payload.get("file_url")
            tool_trace.append(dependencies.export_tool.name)

        draft = dependencies.agent_model.draft_response(
            raw_input=state.get("raw_input", ""),
            filters_used=state.get("filters_used", {}),
            listings=normalized_listings,
            output_format=export_format,
            tool_trace=tool_trace,
        )
        if normalized_listings and _looks_like_no_result_reply(draft.reply):
            draft.reply = _build_search_success_reply(
                listings=normalized_listings,
                filters_used=state.get("filters_used", {}),
                language=state.get("response_language", "vi"),
            )
        tool_trace.append("llm.response")

        return {
            "tool_trace": tool_trace,
            "comparison_results": comparison_results,
            "exported_file": exported_file,
            "response_payload": {
                "status": "success",
                "reply": draft.reply,
                "data": {
                    "filters_used": state.get("filters_used", {}),
                    "listings": normalized_listings,
                    "comparison": comparison_results,
                    "file": exported_file,
                    "missing_fields": [],
                },
                "meta": {
                    "tool_used": tool_trace,
                    "confidence": draft.confidence or state.get("llm_confidence"),
                    "processing_time_ms": 0,
                },
                "error": None,
            },
        }

    return response_node


def _looks_like_no_result_reply(reply: str) -> bool:
    lowered = reply.lower()
    no_result_markers = [
        "không tìm thấy",
        "khong tim thay",
        "không có kết quả",
        "khong co ket qua",
        "no results",
        "could not find",
        "did not find",
    ]
    return any(marker in lowered for marker in no_result_markers)


def _build_search_success_reply(
    *,
    listings: list[dict[str, Any]],
    filters_used: dict[str, Any],
    language: str,
) -> str:
    city = filters_used.get("city") or filters_used.get("ward") or "khu vực bạn yêu cầu"
    max_rent = filters_used.get("max_rent")
    source_count = len({item.get("source_name") for item in listings if item.get("source_name")})
    if language == "en":
        budget_text = f" within a budget up to {max_rent} JPY" if max_rent else ""
        return f"I found {len(listings)} public search results for {city}{budget_text} from {source_count or 'multiple'} source(s)."

    budget_text = f" với ngân sách tối đa {max_rent:,} yên" if isinstance(max_rent, int) else ""
    return (
        f"Tôi tìm được {len(listings)} kết quả công khai tại {city}{budget_text}. "
        "Các kết quả bên dưới có kèm link nguồn để bạn kiểm tra chi tiết."
    )


def _build_compare_reply(
    *,
    comparison_results: list[dict[str, Any]],
    compare_criteria: list[str],
    language: str,
) -> str:
    comparison_count = len(comparison_results)
    criteria_labels = [criterion_label(item, language) for item in compare_criteria]
    criteria_text = " -> ".join(criteria_labels)

    if comparison_count == 0:
        if language == "en":
            return "I could not find enough comparison data for the selected listings."
        return "Tôi không tìm thấy đủ dữ liệu để so sánh các căn đã chọn."

    if comparison_count == 1:
        title = comparison_results[0].get("title") or comparison_results[0].get("id")
        if language == "en":
            return f"I only found one valid listing to compare: {title}."
        return f"Tôi chỉ tìm thấy một căn hợp lệ để so sánh: {title}."

    labels = [str(item.get("title") or item.get("id")) for item in comparison_results[:3]]
    if language == "en":
        return (
            f"I prepared a comparison for {comparison_count} listings: {', '.join(labels)}. "
            f"Criteria order: {criteria_text}."
        )
    return (
        f"Tôi đã chuẩn bị bảng so sánh cho {comparison_count} căn: {', '.join(labels)}. "
        f"Thứ tự tiêu chí: {criteria_text}."
    )
