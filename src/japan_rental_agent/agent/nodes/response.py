from __future__ import annotations

import re
import unicodedata
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
        response_language = state.get("response_language", "vi")
        top_k = state.get("top_k", 5)
        search_more_limit = 5 if state.get("filters_used", {}).get("search_more") else None
        normalized_listings = normalize_listings(raw_listings, top_k=search_more_limit)
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
        if normalized_listings and (
            _looks_like_no_result_reply(draft.reply)
            or _reply_has_mismatched_listing_count(draft.reply, expected_count=len(normalized_listings))
        ):
            draft.reply = _build_search_success_reply(
                listings=normalized_listings,
                filters_used=state.get("filters_used", {}),
                language=response_language,
            )
        if normalized_listings and export_format == "chat":
            draft.reply = _append_refinement_suggestion(
                draft.reply,
                filters_used=state.get("filters_used", {}),
                language=response_language,
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
                    "filters_used": {**state.get("filters_used", {}), "response_language": response_language},
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
    lowered = unicodedata.normalize("NFKD", lowered)
    lowered = "".join(character for character in lowered if not unicodedata.combining(character))
    no_result_markers = [
        "khong tim thay",
        "khong co ket qua",
        "no results",
        "could not find",
        "did not find",
    ]
    return any(marker in lowered for marker in no_result_markers)


def _reply_has_mismatched_listing_count(reply: str, *, expected_count: int) -> bool:
    normalized = unicodedata.normalize("NFKD", reply.lower())
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    count_patterns = [
        r"(?:tim|found|find)\D{0,40}(\d{1,3})\D{0,24}(?:ket qua|lua chon|can ho|can|matches|results|listings|apartments)",
        r"(\d{1,3})\D{0,24}(?:ket qua|lua chon|can ho|can|matches|results|listings|apartments)",
    ]
    for pattern in count_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            return int(match.group(1)) != expected_count
    return False


def _build_search_success_reply(
    *,
    listings: list[dict[str, Any]],
    filters_used: dict[str, Any],
    language: str,
) -> str:
    city = filters_used.get("city") or filters_used.get("ward") or "khu vuc ban yeu cau"
    max_rent = filters_used.get("max_rent")
    source_count = len({item.get("source_name") for item in listings if item.get("source_name")})
    if language == "en":
        budget_text = f" within a budget up to {max_rent} JPY" if max_rent else ""
        return f"I found {len(listings)} public search results for {city}{budget_text} from {source_count or 'multiple'} source(s)."

    budget_text = f" với ngân sách tối đa {max_rent:,} yên" if isinstance(max_rent, int) else ""
    return (
        f"Tôi tìm được {len(listings)} kết quả công khai tại {city}{budget_text}. "
        "Tất cả kết quả bên dưới đều giữ link nguồn để bạn mở ra kiểm tra chi tiết."
    )


def _append_refinement_suggestion(reply: str, *, filters_used: dict[str, Any], language: str) -> str:
    normalized_reply = unicodedata.normalize("NFKD", reply.lower())
    normalized_reply = "".join(character for character in normalized_reply if not unicodedata.combining(character))
    if "thu hep" in normalized_reply or "narrow" in normalized_reply:
        return reply

    suggestion = _build_refinement_suggestion(filters_used=filters_used, language=language)
    if not suggestion:
        return reply

    return f"{reply.rstrip()} {suggestion}"


def _build_refinement_suggestion(*, filters_used: dict[str, Any], language: str) -> str:
    options = [
        (("max_rent",), "ngân sách tối đa", "maximum budget"),
        (("preferred_layout",), "loại phòng (1K/1LDK)", "layout (1K/1LDK)"),
        (("ward", "nearest_station", "station"), "khu/quận hay ga gần nhất", "preferred ward or nearest station"),
        (("min_area",), "diện tích tối thiểu", "minimum floor area"),
        (("occupancy",), "số người ở", "number of residents"),
        (("pet_allowed",), "có nuôi thú cưng không", "whether pets are needed"),
        (("foreigner_friendly",), "cần căn phù hợp cho người nước ngoài không", "whether it should be foreigner-friendly"),
    ]
    missing_labels = [
        vi_label if language == "vi" else en_label
        for keys, vi_label, en_label in options
        if not _has_filter_value(filters_used, keys)
    ]
    if not missing_labels:
        return ""

    labels = _join_suggestion_items(missing_labels[:3], language)
    if language == "en":
        return f"You can narrow the search further by adding {labels}."
    return f"Bạn có thể thu hẹp thêm bằng cách cho tôi biết {labels}."


def _has_filter_value(filters_used: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(filters_used.get(key) not in (None, "", [], {}) for key in keys)


def _join_suggestion_items(items: list[str], language: str) -> str:
    if len(items) <= 1:
        return items[0] if items else ""

    separator = " hoặc " if language == "vi" else " or "
    return f"{', '.join(items[:-1])}{separator}{items[-1]}"


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
        return f"Tôi mới xác định được 1 căn hợp lệ để so sánh: {title}."

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
