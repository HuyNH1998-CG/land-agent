from __future__ import annotations

import re
import unicodedata

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.agent.utils import merge_constraints
from japan_rental_agent.tools.support import resolve_recent_listing_candidates


def make_intent_extraction_node(dependencies: AgentDependencies):
    def intent_extraction_node(state: RentalAgentState) -> RentalAgentState:
        tool_trace = list(state.get("tool_trace", []))
        parser_output: dict[str, object] = {}

        if dependencies.parser_tool is not None:
            try:
                parser_output = dependencies.parser_tool.execute(state.get("raw_input", ""))
                tool_trace.append(dependencies.parser_tool.name)
            except Exception:
                tool_trace.append("parser_error")

        intent = dependencies.agent_model.extract_intent(
            message=state.get("raw_input", ""),
            previous_filters=state.get("filters_used", {}),
            selected_listings=state.get("selected_listings", []),
            conversation_history=state.get("conversation_history", []),
            output_format=state.get("selected_output_format", "chat"),
            parser_hints=parser_output,
        )
        tool_trace.append("llm.intent")

        parser_constraints = parser_output.get("constraints", {})
        parser_intent_hint = parser_output.get("intent_hint")
        parser_compare_criteria = [
            value
            for value in parser_output.get("compare_criteria", [])
            if isinstance(value, str) and value.strip()
        ]
        parser_compare_targets = [
            value
            for value in parser_output.get("compare_targets", [])
            if isinstance(value, str) and value.strip()
        ]
        parser_selected_listing_ids = [
            value
            for value in parser_output.get("selected_listing_ids", [])
            if isinstance(value, str)
        ]
        merged_selected_listings = list(dict.fromkeys(state.get("selected_listings", []) + parser_selected_listing_ids))
        effective_intent = intent.intent
        if parser_intent_hint in {"compare", "export"}:
            effective_intent = parser_intent_hint

        is_more_results_request = _is_more_results_request(state.get("raw_input", ""))
        previous_filters = state.get("filters_used", {})
        previous_filter_base = _base_search_filters(previous_filters) if is_more_results_request else previous_filters
        merged_constraints = merge_constraints(
            previous_filter_base,
            parser_constraints if isinstance(parser_constraints, dict) else {},
            intent.constraints.model_dump(exclude_none=True),
        )
        recent_listings = [
            item
            for item in state.get("recent_listings", [])
            if isinstance(item, dict) and item.get("id")
        ]
        if effective_intent == "search" and is_more_results_request and recent_listings:
            previous_page = _safe_int(previous_filters.get("result_page")) or 1
            merged_constraints["search_more"] = True
            merged_constraints["result_page"] = max(previous_page + 1, (_safe_int(merged_constraints.get("result_page")) or 1))
            excluded_ids = _recent_listing_values(recent_listings, "id")
            excluded_urls = _recent_listing_values(recent_listings, "source_url")
            if excluded_ids:
                merged_constraints["exclude_listing_ids"] = excluded_ids
            if excluded_urls:
                merged_constraints["exclude_source_urls"] = excluded_urls
        if effective_intent == "compare" and len(merged_selected_listings) < 2 and recent_listings:
            inferred_recent_ids = resolve_recent_listing_candidates(
                message=state.get("raw_input", ""),
                recent_listings=recent_listings,
                parsed_constraints=merged_constraints,
            )
            if inferred_recent_ids:
                merged_selected_listings = list(dict.fromkeys(merged_selected_listings + inferred_recent_ids))
        compare_criteria = parser_compare_criteria or state.get("compare_criteria", [])
        response_language = str(
            parser_output.get("response_language")
            or state.get("response_language")
            or "vi"
        )

        missing_fields = list(intent.missing_fields)
        if effective_intent == "search" and is_more_results_request and _has_search_anchor(merged_constraints):
            missing_fields = []
        if effective_intent == "compare":
            if len(merged_selected_listings) >= 2:
                missing_fields = []
            else:
                missing_fields = ["selected_listings"]

        return {
            "intent_label": effective_intent,
            "parsed_constraints": merged_constraints,
            "filters_used": merged_constraints,
            "missing_fields": missing_fields,
            "ranking_preferences": intent.ranking_preferences.as_tool_payload(),
            "selected_output_format": (
                intent.output_format
                or parser_output.get("output_format")
                or state.get("selected_output_format", "chat")
            ),
            "selected_listings": merged_selected_listings,
            "compare_targets": parser_compare_targets,
            "compare_criteria": compare_criteria,
            "response_language": response_language,
            "tool_trace": tool_trace,
            "llm_confidence": intent.confidence,
            "error_message": None,
            "error_code": None,
            "last_failed_node": None,
            "retry_target": None,
        }

    return intent_extraction_node


def _is_more_results_request(message: object) -> bool:
    if not isinstance(message, str):
        return False
    lowered = message.lower()
    normalized = _ascii_fold(lowered)
    phrases = (
        "tim them",
        "them ket qua",
        "nhieu hon",
        "ket qua khac",
        "lua chon khac",
        "khong vua y",
        "xem them",
        "more results",
        "show more",
        "find more",
        "more options",
        "next page",
        "other options",
    )
    jp_phrases = ("もっと", "他の", "別の", "追加", "さらに")
    return any(phrase in normalized for phrase in phrases) or any(phrase in lowered for phrase in jp_phrases)


def _base_search_filters(filters: dict[str, object]) -> dict[str, object]:
    metadata_keys = {
        "search_provider",
        "search_query",
        "search_queries",
        "validated_results",
        "metadata_rich_results",
        "soft_filters_relaxed",
        "response_language",
        "excluded_previous_results",
        "exclude_listing_ids",
        "exclude_source_urls",
        "search_more",
        "result_page",
    }
    return {key: value for key, value in filters.items() if key not in metadata_keys}


def _has_search_anchor(filters: dict[str, object]) -> bool:
    return any(filters.get(key) for key in ("prefecture", "city", "ward", "nearest_station", "station", "max_rent", "preferred_layout"))


def _ascii_fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_value).strip()


def _recent_listing_values(recent_listings: list[dict], key: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in recent_listings:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = value.strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        values.append(normalized)
    return values


def _safe_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
