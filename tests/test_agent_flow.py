from __future__ import annotations

import pytest

from japan_rental_agent.agent import AgentDependencies, RentalAgentService
from japan_rental_agent.agent.llm import AgentModelProtocol
from japan_rental_agent.agent.schemas import (
    ClarificationOutput,
    ErrorDraft,
    IntentExtractionOutput,
    RankingPlanOutput,
    RankingPreferences,
    ResponseDraft,
)
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest
from japan_rental_agent.tools import QueryParserTool


class FakeAgentModel(AgentModelProtocol):
    def __init__(
        self,
        *,
        intent: IntentExtractionOutput,
        clarification: ClarificationOutput | None = None,
        ranking_plan: RankingPlanOutput | None = None,
        response: ResponseDraft | None = None,
        error: ErrorDraft | None = None,
    ) -> None:
        self.intent = intent
        self.clarification = clarification or ClarificationOutput(reply="Need more info", missing_fields=intent.missing_fields)
        self.ranking_plan = ranking_plan or RankingPlanOutput(preferences=RankingPreferences())
        self.response = response or ResponseDraft(reply="Here are your matches.")
        self.error = error or ErrorDraft(reply="Something went wrong.")

    def extract_intent(self, **kwargs) -> IntentExtractionOutput:
        return self.intent

    def draft_clarification(self, **kwargs) -> ClarificationOutput:
        return self.clarification

    def plan_ranking(self, **kwargs) -> RankingPlanOutput:
        return self.ranking_plan

    def draft_response(self, **kwargs) -> ResponseDraft:
        return self.response

    def draft_error(self, **kwargs) -> ErrorDraft:
        return self.error


class StaticSearchTool:
    name = "search"

    def __init__(self, results: list[dict]) -> None:
        self.results = results

    def execute(self, filters: dict) -> dict:
        return {"results": self.results, "total": len(self.results), "filters_used": filters}


class FlakySearchTool:
    name = "search"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, filters: dict) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary search outage")
        return {
            "results": [
                {
                    "listing_id": "apt_retry",
                    "title": "Retry apartment",
                    "city": "Tokyo",
                    "rent_yen": 78000,
                    "station": "Ueno",
                    "walk_min": 4,
                }
            ],
            "total": 1,
            "filters_used": filters,
        }


class PassthroughEnrichmentTool:
    name = "enrichment"

    def execute(self, listings: list[dict], context: dict) -> dict:
        return {"enriched": listings, "context_used": context}


class PassthroughRankingTool:
    name = "ranking"

    def execute(self, listings: list[dict], preferences: dict) -> dict:
        return {"ranked": listings, "preferences_used": preferences}


class PassthroughComparisonTool:
    name = "compare"

    def execute(
        self,
        listing_ids: list[str],
        compare_criteria: list[str] | None = None,
        language: str = "vi",
        **kwargs,
    ) -> dict:
        criteria = compare_criteria or ["price", "size"]
        return {
            "comparison": [
                {
                    "id": listing_id,
                    "title": listing_id,
                    "pros": [f"{criteria[0]}:{language}:good"],
                    "cons": [f"{criteria[-1]}:{language}:tradeoff"],
                }
                for listing_id in listing_ids
            ],
            "criteria_order": criteria,
            "language": language,
        }


class PassthroughExportTool:
    name = "export"

    def execute(self, listings: list[dict], output_format: str) -> dict:
        return {
            "file_url": f"/tmp/mock_export.{output_format}",
            "file_type": output_format,
            "count": len(listings),
        }


def build_service(agent_model: AgentModelProtocol, search_tool, parser_tool=None) -> RentalAgentService:
    config = AppConfig(llm_api_key=None, agent_max_retries=1)
    deps = AgentDependencies(
        config=config,
        agent_model=agent_model,
        parser_tool=parser_tool,
        search_tool=search_tool,
        enrichment_tool=PassthroughEnrichmentTool(),
        ranking_tool=PassthroughRankingTool(),
        comparison_tool=PassthroughComparisonTool(),
        export_tool=PassthroughExportTool(),
    )
    return RentalAgentService(config=config, dependencies=deps)


def test_clarification_path_returns_need_clarification() -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                normalized_query="Need a home",
                constraints={},
                missing_fields=["city"],
                confidence=0.9,
            ),
            clarification=ClarificationOutput(
                reply="Which city in Japan do you want to search in?",
                missing_fields=["city"],
                confidence=0.9,
            ),
        ),
        search_tool=StaticSearchTool([]),
    )

    response = service.handle_request(AgentRequest(session_id="clarify", message="Find me a rental"))

    assert response.status == "need_clarification"
    assert response.data.missing_fields == ["city"]


def test_success_path_runs_search_and_response_nodes() -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                normalized_query="Tokyo rental",
                constraints={"city": "Tokyo", "max_rent": 80000},
                missing_fields=[],
                confidence=0.8,
            ),
            response=ResponseDraft(reply="I found one strong match for you.", confidence=0.8),
        ),
        search_tool=StaticSearchTool(
            [
                {
                    "listing_id": "apt_001",
                    "title": "1K near Shinjuku",
                    "city": "Tokyo",
                    "ward": "Shinjuku",
                    "rent_yen": 75000,
                    "station": "Shinjuku",
                    "walk_min": 5,
                }
            ]
        ),
    )

    response = service.handle_request(AgentRequest(session_id="success", message="Find me a rental in Tokyo"))

    assert response.status == "success"
    assert response.reply == "I found one strong match for you."
    assert response.data.listings[0].id == "apt_001"
    assert "search" in response.meta.tool_used
    assert "llm.response" in response.meta.tool_used


def test_retry_path_retries_search_once_then_succeeds() -> None:
    flaky_search = FlakySearchTool()
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                normalized_query="Retry search",
                constraints={"city": "Tokyo"},
                missing_fields=[],
                confidence=0.75,
            ),
            response=ResponseDraft(reply="Recovered after retry.", confidence=0.7),
        ),
        search_tool=flaky_search,
    )

    response = service.handle_request(AgentRequest(session_id="retry", message="Find me a rental in Tokyo"))

    assert response.status == "success"
    assert response.reply == "Recovered after retry."
    assert flaky_search.calls == 2


def test_compare_path_uses_comparison_tool_without_search() -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="compare",
                normalized_query="Compare two listings",
                constraints={},
                missing_fields=[],
                confidence=0.82,
            ),
        ),
        search_tool=StaticSearchTool([]),
    )

    response = service.handle_request(
        AgentRequest(
            session_id="compare",
            message="Compare sap_001 and sap_002",
            context={"selected_listings": ["sap_001", "sap_002"]},
        )
    )

    assert response.status == "success"
    assert "compare" in response.meta.tool_used
    assert len(response.data.comparison) == 2


@pytest.mark.parametrize(
    ("message", "expected_language"),
    [
        ("Compare Miyanosawa Smart 1R Residence and Kita 24 Jo Quiet 1R House", "en"),
        ("so sánh Miyanosawa Smart 1R Residence và Kita 24 Jo Quiet 1R House", "vi"),
    ],
)
def test_compare_path_can_resolve_titles_without_selected_checkbox(message: str, expected_language: str) -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="compare",
                normalized_query="Compare two listing titles",
                constraints={},
                missing_fields=[],
                confidence=0.82,
            ),
        ),
        search_tool=StaticSearchTool([]),
        parser_tool=QueryParserTool(),
    )

    response = service.handle_request(AgentRequest(session_id="compare-by-title", message=message))

    assert response.status == "success"
    assert len(response.data.comparison) == 2
    assert {item.id for item in response.data.comparison} == {"sap_045", "sap_091"}
    assert response.data.filters_used["response_language"] == expected_language


@pytest.mark.parametrize(
    "message",
    [
        "Compare Miyanosawa Smart 1R Residence and Kita 24 Jo Quiet 1R House",
        "so sánh Miyanosawa Smart 1R Residence và Kita 24 Jo Quiet 1R House",
    ],
)
def test_compare_parser_hint_overrides_llm_missing_fields_when_listings_are_resolved(message: str) -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="search",
                normalized_query="ambiguous compare request",
                constraints={},
                missing_fields=["comparison_criteria"],
                confidence=0.6,
            ),
        ),
        search_tool=StaticSearchTool([]),
        parser_tool=QueryParserTool(),
    )

    response = service.handle_request(AgentRequest(session_id="compare-parser-override", message=message))

    assert response.status == "success"
    assert len(response.data.comparison) == 2
    assert "llm.clarification" not in response.meta.tool_used
    assert "compare" in response.meta.tool_used


@pytest.mark.parametrize(
    ("message", "expected_criteria", "expected_language"),
    [
        ("Compare by price, area, then location", ["price", "size", "location"], "en"),
        ("so sánh theo giá thuê, diện tích rồi vị trí", ["price", "size", "location"], "vi"),
    ],
)
def test_follow_up_compare_criteria_uses_selected_listings_from_context(
    message: str,
    expected_criteria: list[str],
    expected_language: str,
) -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="compare",
                normalized_query=message,
                constraints={},
                missing_fields=[],
                confidence=0.82,
            ),
        ),
        search_tool=StaticSearchTool([]),
        parser_tool=QueryParserTool(),
    )

    response = service.handle_request(
        AgentRequest(
            session_id="compare-follow-up",
            message=message,
            context={
                "selected_listings": ["sap_045", "sap_091"],
                "conversation_history": [
                    {"role": "user", "content": "compare the same two listings"},
                    {"role": "assistant", "content": "comparison ready"},
                ],
            },
        )
    )

    assert response.status == "success"
    assert len(response.data.comparison) == 2
    assert response.data.filters_used["compare_criteria"] == expected_criteria
    assert response.data.filters_used["response_language"] == expected_language
    assert response.data.comparison[0].pros[0].startswith(f"{expected_criteria[0]}:{expected_language}:")


@pytest.mark.parametrize(
    ("message", "expected_prefix"),
    [
        ("Compare by rent", "Which two listings do you want to compare"),
        ("so sánh theo giá thuê", "Bạn muốn so sánh 2 căn nào"),
    ],
)
def test_compare_criteria_without_selected_listings_requests_listing_input(message: str, expected_prefix: str) -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="compare",
                normalized_query=message,
                constraints={},
                missing_fields=[],
                confidence=0.8,
            ),
        ),
        search_tool=StaticSearchTool([]),
        parser_tool=QueryParserTool(),
    )

    response = service.handle_request(AgentRequest(session_id="compare-needs-listings", message=message))

    assert response.status == "need_clarification"
    assert response.data.missing_fields == ["selected_listings"]
    assert response.reply.startswith(expected_prefix)
    assert "compare.clarification" in response.meta.tool_used


@pytest.mark.parametrize(
    ("message", "expected_fragment"),
    [
        ("Compare sap_045", "I only identified one listing"),
        ("so sánh sap_045", "Tôi mới xác định được 1 căn"),
    ],
)
def test_compare_with_only_one_listing_requests_one_more_listing(message: str, expected_fragment: str) -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="compare",
                normalized_query=message,
                constraints={},
                missing_fields=[],
                confidence=0.8,
            ),
        ),
        search_tool=StaticSearchTool([]),
        parser_tool=QueryParserTool(),
    )

    response = service.handle_request(AgentRequest(session_id="compare-needs-second-listing", message=message))

    assert response.status == "need_clarification"
    assert response.data.missing_fields == ["selected_listings"]
    assert expected_fragment in response.reply
    assert "compare.clarification" in response.meta.tool_used


@pytest.mark.parametrize(
    ("message", "expected_fragment"),
    [
        ("Compare Green Court and Blue Plaza", "exact full names or listing IDs"),
        ("so sánh Green Court và Blue Plaza", "tên đầy đủ hoặc mã listing"),
    ],
)
def test_compare_with_unresolved_titles_requests_exact_titles_or_ids(message: str, expected_fragment: str) -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="compare",
                normalized_query=message,
                constraints={},
                missing_fields=[],
                confidence=0.8,
            ),
        ),
        search_tool=StaticSearchTool([]),
        parser_tool=QueryParserTool(),
    )

    response = service.handle_request(AgentRequest(session_id="compare-unresolved-titles", message=message))

    assert response.status == "need_clarification"
    assert response.data.missing_fields == ["selected_listings"]
    assert expected_fragment in response.reply
    assert "compare.clarification" in response.meta.tool_used


def test_export_path_uses_export_tool_when_output_format_is_not_chat() -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                normalized_query="Export search results",
                constraints={"city": "Tokyo"},
                missing_fields=[],
                output_format="json",
                confidence=0.77,
            ),
            response=ResponseDraft(reply="I exported the top results.", confidence=0.79),
        ),
        search_tool=StaticSearchTool(
            [
                {
                    "listing_id": "apt_001",
                    "title": "1K near Shinjuku",
                    "city": "Tokyo",
                    "ward": "Shinjuku",
                    "rent_yen": 75000,
                    "station": "Shinjuku",
                    "walk_min": 5,
                }
            ]
        ),
    )

    response = service.handle_request(
        AgentRequest(
            session_id="export",
            message="Export the results",
            options={"top_k": 3, "output_format": "json"},
        )
    )

    assert response.status == "success"
    assert response.reply == "I exported the top results."
    assert response.data.file == "/tmp/mock_export.json"
    assert "export" in response.meta.tool_used


@pytest.mark.parametrize(
    ("message", "expected_language"),
    [
        ("Compare the listings from the same area listed above", "en"),
        ("so sánh các căn trong cùng khu vực vừa list ra", "vi"),
    ],
)
def test_compare_can_use_recent_search_results_for_same_area(message: str, expected_language: str) -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="compare",
                normalized_query=message,
                constraints={},
                missing_fields=[],
                confidence=0.84,
            ),
        ),
        search_tool=StaticSearchTool([]),
        parser_tool=QueryParserTool(),
    )

    recent_listings = [
        {"id": "sap_045", "title": "A", "city": "Sapporo", "ward": "Nishi", "nearest_station": "Miyanosawa"},
        {"id": "sap_046", "title": "B", "city": "Sapporo", "ward": "Nishi", "nearest_station": "Miyanosawa"},
        {"id": "sap_091", "title": "C", "city": "Sapporo", "ward": "Kita", "nearest_station": "Kita 24 Jo"},
    ]

    response = service.handle_request(
        AgentRequest(
            session_id="compare-recent-same-area",
            message=message,
            context={
                "recent_listings": recent_listings,
            },
        )
    )

    assert response.status == "success"
    assert {item.id for item in response.data.comparison} == {"sap_045", "sap_046"}
    assert response.data.filters_used["response_language"] == expected_language


@pytest.mark.parametrize(
    "message",
    [
        "Compare the listings from the same area listed above",
        "so sánh các căn trong cùng khu vực vừa list ra",
    ],
)
def test_compare_same_area_from_recent_results_asks_again_when_area_is_ambiguous(message: str) -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                intent="compare",
                normalized_query=message,
                constraints={},
                missing_fields=[],
                confidence=0.84,
            ),
        ),
        search_tool=StaticSearchTool([]),
        parser_tool=QueryParserTool(),
    )

    recent_listings = [
        {"id": "sap_045", "title": "A", "city": "Sapporo", "ward": "Nishi", "nearest_station": "Miyanosawa"},
        {"id": "sap_091", "title": "B", "city": "Sapporo", "ward": "Kita", "nearest_station": "Kita 24 Jo"},
        {"id": "sap_120", "title": "C", "city": "Sapporo", "ward": "Shiroishi", "nearest_station": "Shiroishi"},
    ]

    response = service.handle_request(
        AgentRequest(
            session_id="compare-recent-ambiguous",
            message=message,
            context={
                "recent_listings": recent_listings,
            },
        )
    )

    assert response.status == "need_clarification"
    assert response.data.missing_fields == ["selected_listings"]
    assert "compare.clarification" in response.meta.tool_used


def test_search_response_overrides_no_result_reply_when_listings_exist() -> None:
    service = build_service(
        FakeAgentModel(
            intent=IntentExtractionOutput(
                normalized_query="Find me a rental in Sapporo",
                constraints={"city": "Sapporo"},
                missing_fields=[],
                confidence=0.8,
            ),
            response=ResponseDraft(
                reply="Rất tiếc, tôi không tìm thấy kết quả nào phù hợp.",
                confidence=0.9,
            ),
        ),
        search_tool=StaticSearchTool(
            [
                {
                    "listing_id": "web_001",
                    "id": "web_001",
                    "title": "Sapporo rental apartment",
                    "city": "Sapporo",
                    "rent_yen": 50000,
                    "source_url": "https://suumo.jp/chintai/example",
                    "source_name": "suumo.jp",
                }
            ]
        ),
    )

    response = service.handle_request(AgentRequest(session_id="override-no-result", message="Find me a rental in Sapporo"))

    assert response.data.listings
    assert "không tìm thấy" not in response.reply.lower()
    assert "1" in response.reply
