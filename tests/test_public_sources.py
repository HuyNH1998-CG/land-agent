from __future__ import annotations

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data.public_sources import (
    PageSnapshot,
    PublicContextProvider,
    RealEstateWebSearchProvider,
    WebSearchClient,
    WebSearchResult,
    _extract_image_urls,
    _extract_nearby_facilities,
    _prioritize_listing_images,
)
from japan_rental_agent.tools.search import ListingSearchTool


class FakeSearchClient:
    def __init__(self, results: list[WebSearchResult]) -> None:
        self.results = results
        self.queries: list[str] = []
        self.max_results: list[int | None] = []

    def search(self, query: str, *, max_results: int | None = None) -> list[WebSearchResult]:
        self.queries.append(query)
        self.max_results.append(max_results)
        return self.results[: max_results or len(self.results)]


class FakePageClient:
    def __init__(self, pages: dict[str, PageSnapshot] | None = None) -> None:
        self.pages = pages or {}
        self.urls: list[str] = []

    def fetch(self, url: str, *, max_chars: int = 60000) -> PageSnapshot:
        self.urls.append(url)
        return self.pages.get(url, PageSnapshot())


def test_extract_nearby_facilities_detects_daily_amenities() -> None:
    facilities = _extract_nearby_facilities(
        "Nearby: Lawson convenience store, supermarket, park. 周辺施設: コンビニ スーパー 病院"
    )

    assert "convenience_store" in facilities
    assert "supermarket" in facilities
    assert "park" in facilities
    assert "hospital" in facilities


class CountingWebSearchClient(WebSearchClient):
    def __init__(self, results: list[WebSearchResult]) -> None:
        super().__init__(AppConfig(llm_api_key=None, web_search_region="test-region"))
        self.results = results
        self.calls = 0

    def _search_with_langchain(self, query: str, limit: int) -> list[WebSearchResult]:
        self.calls += 1
        return self.results[:limit]


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
    provider = RealEstateWebSearchProvider(
        config,
        search_client=search_client,
        page_client=FakePageClient(
            {
                "https://suumo.jp/chintai/example-1": PageSnapshot(
                    title="Sapporo 1LDK apartment",
                    description="Rent 78000 yen 35m2 walk 6 min near Odori station",
                    text="1LDK apartment near Odori station. 35m2. Walk 6 minutes. 78000 yen.",
                )
            }
        ),
    )
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
    provider = RealEstateWebSearchProvider(
        config,
        search_client=search_client,
        page_client=FakePageClient(
            {
                "https://homes.co.jp/chintai/example-2": PageSnapshot(
                    title="Sapporo 2LDK apartment",
                    description="2LDK apartment. Rent 100000 yen. 48m2.",
                    text="2LDK apartment in Sapporo. Rent 100000 yen. 48m2. Walk 7 minutes.",
                )
            }
        ),
    )

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
    provider = RealEstateWebSearchProvider(
        config,
        search_client=search_client,
        page_client=FakePageClient(
            {
                "https://suumo.jp/chintai/example-3": PageSnapshot(
                    title="Sapporo rental apartment",
                    description="札幌 賃貸 アパート 5.5万円 1K 22㎡ 徒歩4分",
                    text="札幌 賃貸 アパート 5.5万円 1K 22㎡ 徒歩4分",
                )
            }
        ),
    )

    result = provider.search_listings({"city": "Sapporo", "prefecture": "Hokkaido", "max_rent": 100000})

    assert result["total"] == 1
    assert result["results"][0]["rent_yen"] == 55000
    assert result["filters_used"]["search_queries"]
    assert all(" OR " not in query for query in result["filters_used"]["search_queries"])


def test_web_listing_search_provider_respects_query_limit() -> None:
    search_client = FakeSearchClient([])
    config = AppConfig(
        llm_api_key=None,
        search_provider="web",
        web_search_max_results=5,
        web_search_query_limit=2,
    )
    provider = RealEstateWebSearchProvider(config, search_client=search_client, page_client=FakePageClient())

    provider.search_listings({"city": "Sapporo", "prefecture": "Hokkaido", "max_rent": 80000})

    assert len(search_client.queries) == 2


def test_web_search_client_caches_successful_query_results() -> None:
    result = WebSearchResult(
        title="Sapporo rental",
        url="https://suumo.jp/chintai/example-cache",
        snippet="Rent 50000 yen",
        source="suumo.jp",
    )
    search_client = CountingWebSearchClient([result])

    first = search_client.search(" Sapporo   rent ", max_results=3)
    second = search_client.search("Sapporo rent", max_results=3)

    assert first == second
    assert search_client.calls == 1


def test_web_listing_search_provider_search_more_excludes_recent_results_and_expands_batch() -> None:
    results = [
        WebSearchResult(
            title=f"Sapporo rental {index}",
            url=f"https://suumo.jp/chintai/bc_10000000000{index}/",
            snippet=f"Rent {50000 + index * 1000} yen 1K {20 + index}m2 walk {index} min",
            source="suumo.jp",
        )
        for index in range(1, 7)
    ]
    pages = {
        item.url: PageSnapshot(
            title=item.title,
            description=item.snippet,
            text=f"{item.title}. {item.snippet}. Sapporo rental apartment.",
        )
        for item in results
    }
    search_client = FakeSearchClient(results)
    provider = RealEstateWebSearchProvider(
        AppConfig(llm_api_key=None, search_provider="web", web_search_max_results=3, web_search_query_limit=1),
        search_client=search_client,
        page_client=FakePageClient(pages),
    )

    result = provider.search_listings(
        {
            "city": "Sapporo",
            "search_more": True,
            "result_page": 2,
            "exclude_source_urls": [item.url for item in results[:3]],
        }
    )

    returned_urls = {item["source_url"] for item in result["results"]}
    assert returned_urls
    assert returned_urls.isdisjoint({item.url for item in results[:3]})
    assert max(search_client.max_results) > 3
    assert result["filters_used"]["excluded_previous_results"] == 3


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
    provider = RealEstateWebSearchProvider(
        config,
        search_client=search_client,
        page_client=FakePageClient(
            {
                "https://suumo.jp/chintai/example-4": PageSnapshot(
                    title="Sapporo rental apartment",
                    description="Rent 64000 yen 1K 24m2 walk 5 min",
                    text="Sapporo rental apartment. Rent 64000 yen. 1K 24m2. Walk 5 min.",
                )
            }
        ),
    )

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
    provider = RealEstateWebSearchProvider(
        config,
        search_client=search_client,
        page_client=FakePageClient(
            {
                "https://suumo.jp/chintai/hokkaido_/sc_sapporoshichuo/bc_100000000000/": PageSnapshot(
                    title="Sapporo rental apartment",
                    description="札幌 賃貸 5万円 1K 20㎡ 徒歩5分",
                    text="札幌 賃貸 5万円 1K 20㎡ 徒歩5分",
                )
            }
        ),
    )

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


def test_web_listing_search_provider_filters_invalid_detail_pages_even_when_snippet_has_metadata() -> None:
    url = "https://suumo.jp/chintai/bc_100505032485/"
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="[SUUMO] 2DK/8階/47.32m2",
                url=url,
                snippet="2DK 42,000 JPY 47.32m2 Sapporo",
                source="suumo.jp",
            )
        ]
    )
    page_client = FakePageClient(
        {
            url: PageSnapshot(
                title="ページが見つかりません",
                description="お探しのページは見つかりません。",
                text="お探しのページは見つかりません。掲載が終了したか、URLが変更されています。",
            )
        }
    )
    provider = RealEstateWebSearchProvider(
        AppConfig(llm_api_key=None, search_provider="web", web_search_max_results=5),
        search_client=search_client,
        page_client=page_client,
    )

    result = provider.search_listings({"city": "Sapporo"})

    assert result["total"] == 0
    assert result["results"] == []


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


def test_extract_image_urls_filters_non_listing_gallery_images() -> None:
    html_page = """
    <html>
      <head><title>Sapporo 1R apartment</title></head>
      <body>
        <header>
          <img src="/assets/header-menu.png" alt="menu icon" class="header menu icon" />
        </header>
        <section class="property-gallery">
          <img src="/images/property/gaikan01.jpg" alt="外観" />
          <img src="/images/property/madori01.jpg" alt="間取り" />
          <img src="/images/property/room01.jpg" alt="居室" />
        </section>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://homes.co.jp/chintai/b-123456/")

    assert "https://homes.co.jp/assets/header-menu.png" not in image_urls
    assert "https://homes.co.jp/images/property/gaikan01.jpg" in image_urls
    assert "https://homes.co.jp/images/property/madori01.jpg" in image_urls
    assert "https://homes.co.jp/images/property/room01.jpg" in image_urls


def test_prioritize_listing_images_drops_noise_urls() -> None:
    prioritized = _prioritize_listing_images(
        [
            "https://homes.co.jp/assets/header-menu.png",
            "https://homes.co.jp/images/property/gaikan01.jpg",
            "https://homes.co.jp/images/property/madori01.jpg",
            "https://homes.co.jp/images/property/room01.jpg",
        ]
    )

    assert "https://homes.co.jp/assets/header-menu.png" not in prioritized
    assert prioritized


def test_extract_image_urls_supports_lazy_loaded_listing_images() -> None:
    html_page = """
    <html>
      <body>
        <div class="property-gallery slider">
          <img data-src="/images/property/gaikan01.jpg" alt="外観" width="640" height="480" />
          <img data-original="/images/property/room01.jpg" alt="居室" width="640" height="480" />
          <source data-src="/images/property/madori01.jpg" />
        </div>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://able.co.jp/detail/bk123/")

    assert "https://able.co.jp/images/property/gaikan01.jpg" in image_urls
    assert "https://able.co.jp/images/property/room01.jpg" in image_urls
    assert "https://able.co.jp/images/property/madori01.jpg" in image_urls


def test_extract_image_urls_supports_background_image_gallery_assets() -> None:
    html_page = """
    <html>
      <body>
        <div class="property-gallery thumb-list">
          <div class="thumb room-photo" style="background-image:url('/images/property/room_bg_01')"></div>
          <div class="thumb floor-plan" style="background-image:url('/images/property/madori_bg_01?format=jpg')"></div>
        </div>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.chintai.net/detail/bk-000000302000000000318340002/")

    assert "https://www.chintai.net/images/property/room_bg_01" in image_urls
    assert "https://www.chintai.net/images/property/madori_bg_01?format=jpg" in image_urls


def test_extract_image_urls_filters_able_equipment_icons() -> None:
    html_page = """
    <html>
      <body>
        <section class="roomGallery slider">
          <img src="/detail/image/gaikan_01.jpg" alt="外観" width="640" height="480" />
          <img src="/detail/image/room_01.jpg" alt="室内" width="640" height="480" />
        </section>
        <section class="equipment-list">
          <h2>設備・特徴</h2>
          <img src="/detail/image/equipment_aircon.jpg" alt="エアコン" width="320" height="240" />
        </section>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.able.co.jp/detail/Detail.do?bk=000000000123456")

    assert "https://www.able.co.jp/detail/image/gaikan_01.jpg" in image_urls
    assert "https://www.able.co.jp/detail/image/room_01.jpg" in image_urls
    assert "https://www.able.co.jp/detail/image/equipment_aircon.jpg" not in image_urls


def test_extract_image_urls_supports_chintai_escaped_script_cdn_urls() -> None:
    html_page = r"""
    <html>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "gallery": [
              {"caption": "外観", "imageUrl": "https:\/\/img01.chintai.net\/images\/000000312000000000261080034\/001?type=image"},
              {"caption": "間取り", "imageUrl": "\/images\/property\/madori_01?format=jpg"}
            ]
          };
        </script>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.chintai.net/detail/bk-000000312000000000261080034/")

    assert "https://img01.chintai.net/images/000000312000000000261080034/001?type=image" in image_urls
    assert "https://www.chintai.net/images/property/madori_01?format=jpg" in image_urls


def test_prioritize_listing_images_keeps_chintai_cdn_urls_without_filename_hints() -> None:
    prioritized = _prioritize_listing_images(
        [
            "https://www.chintai.net/assets/logo.svg",
            "https://img01.chintai.net/000000312000000000261080034/001",
        ]
    )

    assert prioritized == ["https://img01.chintai.net/000000312000000000261080034/001"]


def test_chintai_image_dedupe_prefers_full_size_over_blurry_variants() -> None:
    html_page = r"""
    <html>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "gallery": [
              {"imageUrl": "https:\/\/img01.chintai.net\/images\/000000312000000000261080034\/001?type=image&width=120&blur=1"},
              {"imageUrl": "https:\/\/img01.chintai.net\/images\/000000312000000000261080034\/001?type=image&width=800"},
              {"imageUrl": "https:\/\/img01.chintai.net\/images\/000000312000000000261080034\/002?type=image&width=800"}
            ]
          };
        </script>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.chintai.net/detail/bk-000000312000000000261080034/")

    assert image_urls == [
        "https://img01.chintai.net/images/000000312000000000261080034/001?type=image&width=800",
        "https://img01.chintai.net/images/000000312000000000261080034/002?type=image&width=800",
    ]


def test_chintai_image_extraction_rejects_blur_when_no_fullsize_duplicate_exists() -> None:
    html_page = r"""
    <html>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "gallery": [
              {"imageUrl": "https:\/\/img01.chintai.net\/images\/000000312000000000261080034\/001?type=image&width=180&blur=1"},
              {"imageUrl": "https:\/\/img01.chintai.net\/images\/000000312000000000261080034\/002?type=image&width=800&q=85"}
            ]
          };
        </script>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.chintai.net/detail/bk-000000312000000000261080034/")

    assert image_urls == ["https://img01.chintai.net/images/000000312000000000261080034/002?type=image&width=800&q=85"]


def test_prioritize_listing_images_no_longer_limits_gallery_to_eight() -> None:
    prioritized = _prioritize_listing_images(
        [f"https://img01.chintai.net/images/000000312000000000261080034/{index:03d}?type=image&width=800" for index in range(1, 11)]
    )

    assert len(prioritized) == 10


def test_chintai_image_extraction_rejects_surrounding_facility_images() -> None:
    html_page = r"""
    <html>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "gallery": [
              {"caption": "外観", "imageUrl": "https:\/\/img01.chintai.net\/images\/000000312000000000261080034\/001?type=image&width=800"},
              {"caption": "周辺環境 スーパー", "imageUrl": "https:\/\/img01.chintai.net\/images\/000000312000000000261080034\/901?type=image&width=800"}
            ]
          };
        </script>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.chintai.net/detail/bk-000000312000000000261080034/")

    assert "https://img01.chintai.net/images/000000312000000000261080034/001?type=image&width=800" in image_urls
    assert "https://img01.chintai.net/images/000000312000000000261080034/901?type=image&width=800" not in image_urls


def test_able_image_extraction_rejects_icons_and_dedupes_blurry_variants() -> None:
    html_page = r"""
    <html>
      <body>
        <section class="roomGallery">
          <img src="https://img.able.co.jp/property/0001/thumb/001.jpg?width=120&blur=1" alt="外観" />
          <img src="https://img.able.co.jp/property/0001/large/001.jpg?width=800" alt="外観" />
          <img src="https://img.able.co.jp/property/0001/large/002.jpg?width=800" alt="室内" />
        </section>
        <section class="equipment-list">
          <img src="https://www.able.co.jp/common/icon/ico_autolock.png" alt="オートロック" />
        </section>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.able.co.jp/detail/Detail.do?bk=000000000123456")

    assert image_urls == [
        "https://img.able.co.jp/property/0001/large/001.jpg?width=800",
        "https://img.able.co.jp/property/0001/large/002.jpg?width=800",
    ]


def test_homes_image_extraction_supports_cdn_and_query_backed_images() -> None:
    html_page = r"""
    <html>
      <body>
        <section class="main-photo gallery">
          <img data-src="//image.homes.co.jp/image/rent/bukken-123/0?width=800" alt="外観" width="640" height="480" />
          <img data-original="/rent/bukken-123/photo?file=room01&width=800" alt="室内" width="640" height="480" />
          <img src="/assets/header-menu.png" alt="menu icon" />
        </section>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.homes.co.jp/chintai/b-123456/")

    assert "https://image.homes.co.jp/image/rent/bukken-123/0?width=800" in image_urls
    assert "https://www.homes.co.jp/rent/bukken-123/photo?file=room01&width=800" in image_urls
    assert "https://www.homes.co.jp/assets/header-menu.png" not in image_urls


def test_homes_image_extraction_rejects_numeric_lazy_placeholders() -> None:
    html_page = r"""
    <html>
      <body>
        <section class="main-photo gallery">
          <img src="0" data-src="0" alt="loading placeholder" />
          <img data-src="//image.homes.co.jp/image/rent/bukken-123/main?width=800" alt="外観" />
        </section>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.homes.co.jp/chintai/b-123456/")

    assert image_urls == ["https://image.homes.co.jp/image/rent/bukken-123/main?width=800"]


def test_homes_image_extraction_keeps_only_property_gallery_context() -> None:
    html_page = r"""
    <html>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "photoGallery": [
              {"caption": "間取り", "imageUrl": "https:\/\/image.homes.co.jp\/image\/rent\/bukken-123\/madori?width=800"},
              {"caption": "外観", "imageUrl": "https:\/\/image.homes.co.jp\/image\/rent\/bukken-123\/gaikan?width=800"}
            ],
            "contactBanners": [
              {"caption": "LIFULL HOME'S 物件鮮度No.1 人気物件 お問合せ", "imageUrl": "https:\/\/image.homes.co.jp\/image\/campaign\/mascot?width=800"},
              {"caption": "取扱い不動産会社 株式会社Relations 店舗", "imageUrl": "https:\/\/image.homes.co.jp\/image\/shop\/relations?width=800"}
            ]
          };
        </script>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.homes.co.jp/chintai/b-123456/")

    assert image_urls == [
        "https://image.homes.co.jp/image/rent/bukken-123/gaikan?width=800",
        "https://image.homes.co.jp/image/rent/bukken-123/madori?width=800",
    ]


def test_homes_image_extraction_rejects_non_gallery_assets_in_scripts() -> None:
    html_page = r"""
    <html>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "photoGallery": [
              {"caption": "間取り", "imageUrl": "https:\/\/image.homes.co.jp\/image\/rent\/bukken-123\/0?width=800"},
              {"caption": "外観", "imageUrl": "https:\/\/image.homes.co.jp\/image\/rent\/bukken-123\/gaikan?width=800"}
            ],
            "uiAssets": [
              {"caption": "お気に入り # icon", "imageUrl": "https:\/\/image.homes.co.jp\/image\/rent\/bukken-123\/1?width=800"},
              {"caption": "LIFULL HOME'S campaign mascot", "imageUrl": "https:\/\/image.homes.co.jp\/image\/campaign\/hash?width=800"}
            ]
          };
        </script>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://www.homes.co.jp/chintai/b-123456/")

    assert "https://image.homes.co.jp/image/rent/bukken-123/gaikan?width=800" in image_urls
    assert "https://image.homes.co.jp/image/rent/bukken-123/0?width=800" in image_urls
    assert "https://image.homes.co.jp/image/rent/bukken-123/1?width=800" not in image_urls
    assert "https://image.homes.co.jp/image/campaign/hash?width=800" not in image_urls


def test_minimini_image_extraction_dedupes_thumbnail_and_fullsize_variants() -> None:
    html_page = r"""
    <html>
      <body>
        <section class="roomGallery">
          <img src="https://img.minimini.jp/bukken/0001/thumb/001.jpg?width=120" alt="外観" />
          <img src="https://img.minimini.jp/bukken/0001/full/001.jpg?width=800" alt="外観" />
          <img src="https://img.minimini.jp/bukken/0001/full/002.jpg?width=800" alt="室内" />
        </section>
      </body>
    </html>
    """

    image_urls = _extract_image_urls(html_page, "https://minimini.jp/detail/0001/")

    assert image_urls == [
        "https://img.minimini.jp/bukken/0001/full/001.jpg?width=800",
        "https://img.minimini.jp/bukken/0001/full/002.jpg?width=800",
    ]
