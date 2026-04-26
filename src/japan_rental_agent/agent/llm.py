from __future__ import annotations

import re
from typing import Any, Callable, Protocol, TypeVar

from japan_rental_agent.agent.prompts import (
    build_clarification_prompt,
    build_error_prompt,
    build_intent_extraction_prompt,
    build_ranking_plan_prompt,
    build_response_prompt,
)
from japan_rental_agent.agent.schemas import (
    ClarificationOutput,
    ErrorDraft,
    IntentExtractionOutput,
    RankingPlanOutput,
    RankingPreferences,
    ResponseDraft,
)
from japan_rental_agent.config import AppConfig

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

T = TypeVar("T")


class AgentModelProtocol(Protocol):
    def extract_intent(
        self,
        *,
        message: str,
        previous_filters: dict[str, Any],
        selected_listings: list[str],
        conversation_history: list[dict[str, str]],
        output_format: str,
        parser_hints: dict[str, Any],
    ) -> IntentExtractionOutput: ...

    def draft_clarification(
        self,
        *,
        raw_input: str,
        parsed_constraints: dict[str, Any],
        missing_fields: list[str],
        conversation_history: list[dict[str, str]],
    ) -> ClarificationOutput: ...

    def plan_ranking(
        self,
        *,
        raw_input: str,
        parsed_constraints: dict[str, Any],
        search_results: list[dict[str, Any]],
        current_preferences: dict[str, Any],
    ) -> RankingPlanOutput: ...

    def draft_response(
        self,
        *,
        raw_input: str,
        filters_used: dict[str, Any],
        listings: list[dict[str, Any]],
        output_format: str,
        tool_trace: list[str],
    ) -> ResponseDraft: ...

    def draft_error(
        self,
        *,
        raw_input: str,
        error_message: str,
        retry_count: int,
        last_failed_node: str | None,
    ) -> ErrorDraft: ...


class FallbackAgentModel:
    """Offline-safe fallback used when live Gemini access is unavailable."""

    def extract_intent(
        self,
        *,
        message: str,
        previous_filters: dict[str, Any],
        selected_listings: list[str],
        conversation_history: list[dict[str, str]],
        output_format: str,
        parser_hints: dict[str, Any],
    ) -> IntentExtractionOutput:
        constraints = dict(previous_filters)
        lowered = message.lower()
        intent = "search"

        if "compare" in lowered:
            intent = "compare"
        elif "export" in lowered or "download" in lowered:
            intent = "export"

        if "tokyo" in lowered:
            constraints["city"] = "Tokyo"
            constraints.setdefault("prefecture", "Tokyo")
        if "osaka" in lowered:
            constraints["city"] = "Osaka"
            constraints.setdefault("prefecture", "Osaka")
        if "sapporo" in lowered:
            constraints["city"] = "Sapporo"
            constraints.setdefault("prefecture", "Hokkaido")
        if "near station" in lowered or "gan ga" in lowered:
            constraints["near_station"] = True

        budget_match = re.search(r"(\d{4,6})\s*(yen|jpy)", lowered)
        if budget_match:
            constraints["max_rent"] = int(budget_match.group(1))

        man_match = re.search(r"(\d+)\s*man", lowered)
        if man_match:
            constraints["max_rent"] = int(man_match.group(1)) * 10000

        missing_fields: list[str] = []
        parser_selected_listing_ids = parser_hints.get("selected_listing_ids", []) if isinstance(parser_hints, dict) else []
        if intent == "compare":
            if not selected_listings and not parser_selected_listing_ids:
                missing_fields.append("selected_listings")
        elif "city" not in constraints:
            missing_fields.append("city")

        output_format_hint = parser_hints.get("output_format") if isinstance(parser_hints, dict) else None

        return IntentExtractionOutput(
            intent=intent,  # type: ignore[arg-type]
            normalized_query=message.strip(),
            constraints=constraints,
            missing_fields=missing_fields,
            output_format=output_format_hint or output_format,
            ranking_preferences=RankingPreferences(),
            confidence=0.35,
        )

    def draft_clarification(
        self,
        *,
        raw_input: str,
        parsed_constraints: dict[str, Any],
        missing_fields: list[str],
        conversation_history: list[dict[str, str]],
    ) -> ClarificationOutput:
        fields = ", ".join(missing_fields) if missing_fields else "một vài thông tin bổ sung"
        return ClarificationOutput(
            reply=f"Vui lòng cho tôi biết {fields} để tôi tiếp tục tìm nhà.",
            missing_fields=missing_fields,
            confidence=0.3,
        )

    def plan_ranking(
        self,
        *,
        raw_input: str,
        parsed_constraints: dict[str, Any],
        search_results: list[dict[str, Any]],
        current_preferences: dict[str, Any],
    ) -> RankingPlanOutput:
        preferences = RankingPreferences.model_validate(current_preferences or {})
        return RankingPlanOutput(
            preferences=preferences,
            summary="Đang dùng bộ trọng số mặc định trong chế độ fallback.",
            confidence=0.3,
        )

    def draft_response(
        self,
        *,
        raw_input: str,
        filters_used: dict[str, Any],
        listings: list[dict[str, Any]],
        output_format: str,
        tool_trace: list[str],
    ) -> ResponseDraft:
        if listings:
            return ResponseDraft(
                reply=f"Tôi đã tìm được {len(listings)} lựa chọn thuê nhà phù hợp với yêu cầu hiện tại.",
                confidence=0.35,
            )
        return ResponseDraft(
            reply="Tôi chưa tìm thấy lựa chọn phù hợp. Hãy nới ngân sách hoặc điều chỉnh bộ lọc rồi thử lại.",
            confidence=0.35,
        )

    def draft_error(
        self,
        *,
        raw_input: str,
        error_message: str,
        retry_count: int,
        last_failed_node: str | None,
    ) -> ErrorDraft:
        return ErrorDraft(
            reply="Tôi gặp lỗi trong quá trình xử lý yêu cầu tìm nhà. Hãy thử lại sau ít phút.",
            code="WORKFLOW_ERROR",
            confidence=0.2,
        )


class OpenAICompatibleGeminiAgentModel:
    """Gemini model accessed through Google's OpenAI-compatible endpoint."""

    def __init__(self, config: AppConfig) -> None:
        if OpenAI is None:  # pragma: no cover
            raise RuntimeError("The `openai` package is required to use the Gemini client.")
        if not config.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required to initialize the Gemini client.")
        if not config.llm_base_url:
            raise RuntimeError("LLM_BASE_URL is required for the OpenAI-compatible Gemini endpoint.")

        self.config = config
        self.client = OpenAI(
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
        )

    def _parse_structured(self, *, system_instruction: str, prompt: str, response_model: type[T]) -> T:
        request: dict[str, Any] = {
            "model": self.config.llm_chat_model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "response_format": response_model,
        }
        if self.config.llm_reasoning_effort:
            request["reasoning_effort"] = self.config.llm_reasoning_effort

        completion = self.client.beta.chat.completions.parse(**request)
        message = completion.choices[0].message
        if getattr(message, "parsed", None) is not None:
            return message.parsed
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise RuntimeError(f"Gemini refusal: {refusal}")
        raise RuntimeError("Gemini returned no structured payload.")

    def extract_intent(
        self,
        *,
        message: str,
        previous_filters: dict[str, Any],
        selected_listings: list[str],
        conversation_history: list[dict[str, str]],
        output_format: str,
        parser_hints: dict[str, Any],
    ) -> IntentExtractionOutput:
        return self._parse_structured(
            system_instruction=(
                "You are the intent extraction node of a Japan rental search agent. "
                "Return only structured data that is safe for downstream orchestration."
            ),
            prompt=build_intent_extraction_prompt(
                message=message,
                previous_filters=previous_filters,
                selected_listings=selected_listings,
                output_format=output_format,
                parser_hints=parser_hints,
            ),
            response_model=IntentExtractionOutput,
        )

    def draft_clarification(
        self,
        *,
        raw_input: str,
        parsed_constraints: dict[str, Any],
        missing_fields: list[str],
        conversation_history: list[dict[str, str]],
    ) -> ClarificationOutput:
        return self._parse_structured(
            system_instruction=(
                "You are the clarification node of a rental assistant. "
                "Ask only for the minimum missing information needed to continue. "
                "Respond in Vietnamese unless the user explicitly asked for another language."
            ),
            prompt=build_clarification_prompt(
                raw_input=raw_input,
                parsed_constraints=parsed_constraints,
                missing_fields=missing_fields,
                conversation_history=conversation_history,
            ),
            response_model=ClarificationOutput,
        )

    def plan_ranking(
        self,
        *,
        raw_input: str,
        parsed_constraints: dict[str, Any],
        search_results: list[dict[str, Any]],
        current_preferences: dict[str, Any],
    ) -> RankingPlanOutput:
        return self._parse_structured(
            system_instruction=(
                "You are the ranking planner for a rental search agent. "
                "Return ranking weights that downstream tools can use."
            ),
            prompt=build_ranking_plan_prompt(
                raw_input=raw_input,
                parsed_constraints=parsed_constraints,
                search_results=search_results,
                current_preferences=current_preferences,
            ),
            response_model=RankingPlanOutput,
        )

    def draft_response(
        self,
        *,
        raw_input: str,
        filters_used: dict[str, Any],
        listings: list[dict[str, Any]],
        output_format: str,
        tool_trace: list[str],
    ) -> ResponseDraft:
        return self._parse_structured(
            system_instruction=(
                "You are the final response node of a rental search assistant. "
                "Write concise, helpful user-facing replies grounded in the provided data. "
                "Respond in Vietnamese unless the user explicitly asked for another language."
            ),
            prompt=build_response_prompt(
                raw_input=raw_input,
                filters_used=filters_used,
                listings=listings,
                output_format=output_format,
                tool_trace=tool_trace,
            ),
            response_model=ResponseDraft,
        )

    def draft_error(
        self,
        *,
        raw_input: str,
        error_message: str,
        retry_count: int,
        last_failed_node: str | None,
    ) -> ErrorDraft:
        return self._parse_structured(
            system_instruction=(
                "You are the error-handling node of a rental search assistant. "
                "Explain failures clearly and keep the reply short. "
                "Respond in Vietnamese unless the user explicitly asked for another language."
            ),
            prompt=build_error_prompt(
                raw_input=raw_input,
                error_message=error_message,
                retry_count=retry_count,
                last_failed_node=last_failed_node,
            ),
            response_model=ErrorDraft,
        )


class ResilientAgentModel:
    """Uses the live client first and falls back to offline heuristics on failure."""

    def __init__(self, primary: AgentModelProtocol, fallback: AgentModelProtocol) -> None:
        self.primary = primary
        self.fallback = fallback

    def _call(self, primary_call: Callable[[], T], fallback_call: Callable[[], T]) -> T:
        try:
            return primary_call()
        except Exception:
            return fallback_call()

    def extract_intent(
        self,
        *,
        message: str,
        previous_filters: dict[str, Any],
        selected_listings: list[str],
        conversation_history: list[dict[str, str]],
        output_format: str,
        parser_hints: dict[str, Any],
    ) -> IntentExtractionOutput:
        kwargs = {
            "message": message,
            "previous_filters": previous_filters,
            "selected_listings": selected_listings,
            "conversation_history": conversation_history,
            "output_format": output_format,
            "parser_hints": parser_hints,
        }
        return self._call(
            lambda: self.primary.extract_intent(**kwargs),
            lambda: self.fallback.extract_intent(**kwargs),
        )

    def draft_clarification(
        self,
        *,
        raw_input: str,
        parsed_constraints: dict[str, Any],
        missing_fields: list[str],
        conversation_history: list[dict[str, str]],
    ) -> ClarificationOutput:
        kwargs = {
            "raw_input": raw_input,
            "parsed_constraints": parsed_constraints,
            "missing_fields": missing_fields,
            "conversation_history": conversation_history,
        }
        return self._call(
            lambda: self.primary.draft_clarification(**kwargs),
            lambda: self.fallback.draft_clarification(**kwargs),
        )

    def plan_ranking(
        self,
        *,
        raw_input: str,
        parsed_constraints: dict[str, Any],
        search_results: list[dict[str, Any]],
        current_preferences: dict[str, Any],
    ) -> RankingPlanOutput:
        kwargs = {
            "raw_input": raw_input,
            "parsed_constraints": parsed_constraints,
            "search_results": search_results,
            "current_preferences": current_preferences,
        }
        return self._call(
            lambda: self.primary.plan_ranking(**kwargs),
            lambda: self.fallback.plan_ranking(**kwargs),
        )

    def draft_response(
        self,
        *,
        raw_input: str,
        filters_used: dict[str, Any],
        listings: list[dict[str, Any]],
        output_format: str,
        tool_trace: list[str],
    ) -> ResponseDraft:
        kwargs = {
            "raw_input": raw_input,
            "filters_used": filters_used,
            "listings": listings,
            "output_format": output_format,
            "tool_trace": tool_trace,
        }
        return self._call(
            lambda: self.primary.draft_response(**kwargs),
            lambda: self.fallback.draft_response(**kwargs),
        )

    def draft_error(
        self,
        *,
        raw_input: str,
        error_message: str,
        retry_count: int,
        last_failed_node: str | None,
    ) -> ErrorDraft:
        kwargs = {
            "raw_input": raw_input,
            "error_message": error_message,
            "retry_count": retry_count,
            "last_failed_node": last_failed_node,
        }
        return self._call(
            lambda: self.primary.draft_error(**kwargs),
            lambda: self.fallback.draft_error(**kwargs),
        )


def create_agent_model(config: AppConfig) -> AgentModelProtocol:
    fallback = FallbackAgentModel()
    if config.llm_api_key and config.llm_base_url:
        try:
            primary = OpenAICompatibleGeminiAgentModel(config)
            return ResilientAgentModel(primary=primary, fallback=fallback)
        except Exception:
            return fallback
    return fallback
