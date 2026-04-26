from __future__ import annotations

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
                {"listing_id": "apt_retry", "title": "Retry apartment", "city": "Tokyo", "rent_yen": 78000, "station": "Ueno", "walk_min": 4}
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

    def execute(self, listing_ids: list[str]) -> dict:
        return {
            "comparison": [
                {"id": listing_id, "pros": ["good"], "cons": ["tradeoff"]}
                for listing_id in listing_ids
            ]
        }


class PassthroughExportTool:
    name = "export"

    def execute(self, listings: list[dict], output_format: str) -> dict:
        return {
            "file_url": f"/tmp/mock_export.{output_format}",
            "file_type": output_format,
            "count": len(listings),
        }


def build_service(agent_model: AgentModelProtocol, search_tool) -> RentalAgentService:
    config = AppConfig(llm_api_key=None, agent_max_retries=1)
    deps = AgentDependencies(
        config=config,
        agent_model=agent_model,
        parser_tool=None,
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
            response=ResponseDraft(reply="Here is the comparison summary.", confidence=0.81),
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
    assert "bảng so sánh" in response.reply
    assert len(response.data.comparison) == 2
    assert "compare" in response.meta.tool_used


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
