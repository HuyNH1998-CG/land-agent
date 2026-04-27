from __future__ import annotations

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data.public_sources import (
    PageSnapshot,
    PublicContextProvider,
    RealEstateWebSearchProvider,
    WebSearchResult,
)
from japan_rental_agent.tools.search import ListingSearchTool


class FakeSearchClient:
    def __init__(self, results: list[WebSearchResult]) -> None:
        self.results = results
        self.queries: list[str] = []

    def search(self, query: str, *, max_results: int | None = None) -> list[WebSearchResult]:
        self.queries.append(query)
        return self.results[: max_results or len(self.results)]


class FakePageClient:
    def __init__(self, pages: dict[str, PageSnapshot] | None = None) -> None:
        self.pages = pages or {}
        self.urls: list[str] = []

    def fetch(self, url: str, *, max_chars: int = 60000) -> PageSnapshot:
        self.urls.append(url)
        return self.pages.get(url, PageSnapshot())


def test_web_listing_search_provider_normalizes_search_results() -> None:
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="Sapporo 1LDK apartment rent 78000 yen 35m2 walk 6 min",
                url="https://suumo.jp/chintai/example-1",
                snippet="1LDK apartment near Odori station. 35m2. Walk 6 minutes. 78000 yen.",
                source="suumo.jp",
            )
        ]
    )
    config = AppConfig(llm_api_key=None, search_provider="web", web_search_max_results=5)
    provider = RealEstateWebSearchProvider(config, search_client=search_client, page_client=FakePageClient())
    tool = ListingSearchTool(config, web_provider=provider)

    result = tool.execute({"city": "Sapporo", "max_rent": 90000, "preferred_layout": "1LDK"})

    assert result["total"] == 1
    listing = result["results"][0]
    assert listing["id"].startswith("web_")
    assert listing["source_url"] == "https://suumo.jp/chintai/example-1"
    assert listing["rent_yen"] == 78000
    assert listing["layout"] == "1LDK"
    assert listing["area_m2"] == 35.0
    assert result["filters_used"]["search_provider"] == "web"
    assert " OR " not in result["filters_used"]["search_query"]
    assert "site:suumo.jp/chintai" in search_client.queries[0]


def test_web_listing_search_provider_relaxes_filters_when_snippets_are_sparse() -> None:
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="Sapporo 2LDK apartment rent 100000 yen",
                url="https://homes.co.jp/chintai/example-2",
                snippet="2LDK apartment. Rent 100000 yen.",
                source="homes.co.jp",
            )
        ]
    )
    config = AppConfig(llm_api_key=None, search_provider="web", web_search_max_results=5)
    provider = RealEstateWebSearchProvider(config, search_client=search_client, page_client=FakePageClient())

    result = provider.search_listings({"city": "Sapporo", "max_rent": 1, "preferred_layout": "1LDK"})

    assert result["total"] == 1
    assert result["results"][0]["source_url"] == "https://homes.co.jp/chintai/example-2"
    assert result["filters_used"]["soft_filters_relaxed"] is True


def test_web_listing_search_provider_runs_multiple_site_queries() -> None:
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="Sapporo rental apartment 5.5万円",
                url="https://suumo.jp/chintai/example-3",
                snippet="札幌 賃貸 アパート 5.5万円",
                source="suumo.jp",
            )
        ]
    )
    config = AppConfig(llm_api_key=None, search_provider="web", web_search_max_results=3)
    provider = RealEstateWebSearchProvider(config, search_client=search_client, page_client=FakePageClient())

    result = provider.search_listings({"city": "Sapporo", "prefecture": "Hokkaido", "max_rent": 100000})

    assert result["total"] == 1
    assert result["results"][0]["rent_yen"] == 55000
    assert result["filters_used"]["search_queries"]
    assert all(" OR " not in query for query in result["filters_used"]["search_queries"])


def test_web_listing_search_provider_filters_non_real_estate_domains() -> None:
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="Sapporo hotel ad",
                url="https://www.bing.com/aclick?ad=hotel",
                snippet="Hotel accommodation ad.",
                source="bing.com",
            ),
            WebSearchResult(
                title="Sapporo rental apartment",
                url="https://suumo.jp/chintai/example-4",
                snippet="Sapporo rental apartment.",
                source="suumo.jp",
            ),
        ]
    )
    config = AppConfig(llm_api_key=None, search_provider="web", web_search_max_results=5)
    provider = RealEstateWebSearchProvider(config, search_client=search_client, page_client=FakePageClient())

    result = provider.search_listings({"city": "Sapporo", "max_rent": 100000})

    assert result["total"] == 1
    assert result["results"][0]["source_name"] == "suumo.jp"


def test_web_listing_search_provider_rejects_sale_and_moving_pages() -> None:
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="Used condo for sale",
                url="https://suumo.jp/ms/chuko/hokkaido_/sc_sapporoshichuo/nc_20598782/",
                snippet="中古マンション物件情報",
                source="suumo.jp",
            ),
            WebSearchResult(
                title="Moving cost",
                url="https://hikkoshi.suumo.jp/soba/hokkaido/sapporo/january",
                snippet="引っ越し料金",
                source="hikkoshi.suumo.jp",
            ),
            WebSearchResult(
                title="Sapporo rental apartment",
                url="https://suumo.jp/chintai/hokkaido_/sc_sapporoshichuo/bc_100000000000/",
                snippet="札幌 賃貸 5万円",
                source="suumo.jp",
            ),
            WebSearchResult(
                title="Roomshare feature",
                url="https://www.chintai.net/feature/roomshare/hokkaido",
                snippet="北海道のルームシェア可の賃貸物件特集",
                source="chintai.net",
            ),
        ]
    )
    config = AppConfig(llm_api_key=None, search_provider="web", web_search_max_results=5)
    provider = RealEstateWebSearchProvider(config, search_client=search_client, page_client=FakePageClient())

    result = provider.search_listings({"city": "Sapporo", "max_rent": 100000})

    assert result["total"] == 1
    assert "/chintai/" in result["results"][0]["source_url"]


def test_web_listing_search_provider_extracts_metadata_from_page_snapshot() -> None:
    url = "https://suumo.jp/chintai/hokkaido_/sc_sapporoshichuo/bc_100000000001/"
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="Sapporo rental apartment",
                url=url,
                snippet="札幌 賃貸マンション",
                source="suumo.jp",
            )
        ]
    )
    page_client = FakePageClient(
        {
            url: PageSnapshot(
                title="札幌市中央区 1LDK 賃貸マンション",
                description="賃料 5.8万円 管理費 3000円 1LDK 34.2㎡ 大通駅 徒歩6分 築12年 4階",
                text="北海道札幌市中央区 賃料 5.8万円 管理費 3000円 間取り 1LDK 専有面積 34.2㎡ 大通駅 徒歩6分 築12年 4階",
            )
        }
    )
    config = AppConfig(llm_api_key=None, search_provider="web", web_search_max_results=5)
    provider = RealEstateWebSearchProvider(config, search_client=search_client, page_client=page_client)

    result = provider.search_listings({"city": "Sapporo", "max_rent": 70000})
    listing = result["results"][0]

    assert listing["rent_yen"] == 58000
    assert listing["management_fee"] == 3000
    assert listing["layout"] == "1LDK"
    assert listing["area_m2"] == 34.2
    assert listing["nearest_station"] == "大通駅"
    assert listing["walk_min"] == 6
    assert listing["building_age"] == 12
    assert listing["floor"] == 4
    assert listing["source_kind"] == "listing_detail"
    assert "rent_yen" in listing["metadata_fields_found"]


def test_public_context_provider_collects_dataset_2_to_5_context() -> None:
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="Official dataset result",
                url="https://www.e-stat.go.jp/example",
                snippet="Regional housing context",
                source="e-stat.go.jp",
            )
        ]
    )
    config = AppConfig(llm_api_key=None, search_provider="web")
    provider = PublicContextProvider(config, search_client=search_client)

    context = provider.get_context({"prefecture": "Hokkaido", "city": "Sapporo"})

    assert set(context["datasets"]) == {
        "housing_land_survey",
        "mlit_real_estate",
        "hazard_safety",
        "regional_indicators",
    }
    assert context["datasets"]["housing_land_survey"]["api"]["provider"] == "e-Stat"
    assert context["datasets"]["mlit_real_estate"]["api"]["provider"] == "MLIT Real Estate Information Library"
