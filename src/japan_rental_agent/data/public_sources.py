from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import unicodedata
import urllib.parse
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

from japan_rental_agent.config import AppConfig

try:
    from langchain_community.tools import DuckDuckGoSearchResults
    from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
except ImportError:  # pragma: no cover
    DuckDuckGoSearchAPIWrapper = None
    DuckDuckGoSearchResults = None

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover
    DDGS = None


@dataclass(frozen=True, slots=True)
class SourceProfile:
    name: str
    site_scope: str
    domains: tuple[str, ...]
    required_path_prefixes: tuple[str, ...] = ()
    excluded_path_fragments: tuple[str, ...] = ()


REAL_ESTATE_SOURCE_PROFILES = [
    SourceProfile(
        name="suumo.jp",
        site_scope="suumo.jp/chintai",
        domains=("suumo.jp",),
        required_path_prefixes=("/chintai/",),
        excluded_path_fragments=("/ms/", "/ikkodate/", "/tochi/", "/shop/", "/soba/", "/hikkoshi/"),
    ),
    SourceProfile(
        name="homes.co.jp",
        site_scope="homes.co.jp/chintai",
        domains=("homes.co.jp", "chintai.homes.co.jp"),
        required_path_prefixes=("/chintai/", "/rent/"),
        excluded_path_fragments=("/mansion/", "/kodate/", "/tochi/", "/shop/", "/archive/"),
    ),
    SourceProfile(
        name="athome.co.jp",
        site_scope="athome.co.jp/chintai",
        domains=("athome.co.jp",),
        required_path_prefixes=("/chintai/",),
        excluded_path_fragments=("/mansion/", "/kodate/", "/tochi/", "/shop/"),
    ),
    SourceProfile(
        name="chintai.net",
        site_scope="chintai.net",
        domains=("chintai.net",),
        excluded_path_fragments=("/shop/", "/article/", "/campaign/", "/feature/"),
    ),
    SourceProfile(
        name="able.co.jp",
        site_scope="able.co.jp",
        domains=("able.co.jp", "offer.able.co.jp"),
        excluded_path_fragments=("/shop/", "/article/", "/company/", "/parking/"),
    ),
    SourceProfile(
        name="minimini.jp",
        site_scope="minimini.jp",
        domains=("minimini.jp",),
        excluded_path_fragments=("/shop/", "/company/", "/campaign/"),
    ),
]

REAL_ESTATE_SEARCH_DOMAINS = [profile.name for profile in REAL_ESTATE_SOURCE_PROFILES]
SOURCE_PRIORITY = {
    "suumo.jp": 0,
    "homes.co.jp": 1,
    "athome.co.jp": 2,
    "chintai.net": 3,
    "able.co.jp": 4,
    "minimini.jp": 5,
}
SEARCH_CACHE_MAX_SIZE = 256
PAGE_CACHE_MAX_SIZE = 256
_SEARCH_CACHE: OrderedDict[tuple[str, str, int], tuple[Any, ...]] = OrderedDict()
_PAGE_CACHE: OrderedDict[tuple[str, int], Any] = OrderedDict()
_SEARCH_CACHE_LOCK = threading.Lock()
_PAGE_CACHE_LOCK = threading.Lock()

DATASET_CONTEXT_QUERIES = {
    "housing_land_survey": "e-Stat Housing and Land Survey rental housing {area}",
    "mlit_real_estate": "MLIT Real Estate Information Library land price real estate {area}",
    "hazard_safety": "MLIT hazard map flood earthquake safety {area}",
    "regional_indicators": "e-Stat Statistics Dashboard regional indicators population household {area}",
}

NEARBY_FACILITY_PROFILES = (
    (
        "convenience_store",
        (
            "convenience store",
            "conbini",
            "konbini",
            "seven eleven",
            "7-eleven",
            "7 eleven",
            "lawson",
            "familymart",
            "family mart",
            "\u30b3\u30f3\u30d3\u30cb",
            "\u30bb\u30d6\u30f3\u30a4\u30ec\u30d6\u30f3",
            "\u30ed\u30fc\u30bd\u30f3",
            "\u30d5\u30a1\u30df\u30ea\u30fc\u30de\u30fc\u30c8",
        ),
    ),
    (
        "supermarket",
        (
            "supermarket",
            "super market",
            "grocery",
            "grocery store",
            "aeon",
            "maxvalu",
            "\u30b9\u30fc\u30d1\u30fc",
            "\u30a4\u30aa\u30f3",
            "\u30de\u30c3\u30af\u30b9\u30d0\u30ea\u30e5",
        ),
    ),
    (
        "drugstore",
        (
            "drugstore",
            "drug store",
            "pharmacy",
            "sapporo drug store",
            "tsuruha",
            "\u30c9\u30e9\u30c3\u30b0\u30b9\u30c8\u30a2",
            "\u85ac\u5c40",
            "\u30c4\u30eb\u30cf",
        ),
    ),
    ("park", ("park", "\u516c\u5712")),
    ("hospital", ("hospital", "clinic", "\u75c5\u9662", "\u30af\u30ea\u30cb\u30c3\u30af")),
    ("school", ("school", "elementary school", "junior high", "\u5b66\u6821", "\u5c0f\u5b66\u6821", "\u4e2d\u5b66\u6821")),
    ("shopping_mall", ("shopping mall", "shopping center", "\u30b7\u30e7\u30c3\u30d4\u30f3\u30b0", "\u5546\u696d\u65bd\u8a2d")),
)

YEN_LABELS = ("円", "yen", "jpy", "蜀")
MAN_LABELS = ("万", "万円", "man", "10k", "荳")
RENT_LABELS = ("賃料", "家賃", "賃貸", "rent", "price", "雉", "萓")
FEE_LABELS = ("管理費", "共益費", "fee", "management", "邂", "蜈")
WALK_LABELS = ("徒歩", "walk", "walking", "蠕呈ｭｩ", "豁ｩ")
AREA_LABELS = ("㎡", "m2", "m²", "sqm", "緕｡", "蟷ｳ邀ｳ")
BUILDING_AGE_LABELS = ("築", "新築", "built", "age", "遽")
CONSTRUCTION_YEAR_LABELS = ("築年月", "建築年", "建築", "construction", "built in", "竣工", "完成", "新築年月")
FLOOR_LABELS = ("階", "floor", "髫")
STATION_LABELS = ("駅", "station")
SAPPORO_TOKENS = ("sapporo", "札幌", "譛ｭ蟷")
WARD_TOKENS = {
    "中央区": "Chuo",
    "北区": "Kita",
    "東区": "Higashi",
    "白石区": "Shiroishi",
    "豊平区": "Toyohira",
    "南区": "Minami",
    "西区": "Nishi",
    "厚別区": "Atsubetsu",
    "手稲区": "Teine",
    "清田区": "Kiyota",
    "荳ｭ螟ｮ蛹ｺ": "Chuo",
    "蛹怜玄": "Kita",
    "譚ｱ蛹ｺ": "Higashi",
    "逋ｽ遏ｳ蛹ｺ": "Shiroishi",
    "雎雁ｹｳ蛹ｺ": "Toyohira",
    "蜊怜玄": "Minami",
    "隘ｿ蛹ｺ": "Nishi",
    "蜴壼挨蛹ｺ": "Atsubetsu",
    "謇狗ｨｲ蛹ｺ": "Teine",
    "貂・伐蛹ｺ": "Kiyota",
}
LISTING_IMAGE_HINTS = ("madori", "floor", "plan", "layout", "room", "photo", "image", "gaikan", "外観", "間取", "間取り")
IMAGE_NOISE_HINTS = (
    "logo",
    "icon",
    "sprite",
    "banner",
    "header",
    "menu",
    "button",
    "blank",
    "spacer",
    "loading",
    "common",
    "sectigo",
    "ssl",
    "secure",
    "cert",
    "certificate",
    "trustlogo",
    "security",
    "equipment",
    "facility",
    "setsubi",
    "ico_",
    "/ico/",
    "/icons/",
    "/icon/",
)
LISTING_IMAGE_CONTEXT_HINTS = (
    "gallery",
    "slider",
    "carousel",
    "thumb",
    "thumbnail",
    "photo list",
    "image list",
    "slideshow",
    "main visual",
    "mainimage",
    "main image",
    "subimage",
    "detail image",
    "main image",
    "main photo",
    "property image",
    "property photo",
    "room",
    "living",
    "bedroom",
    "kitchen",
    "bath",
    "toilet",
    "wash",
    "entrance",
    "balcony",
    "floor plan",
    "layout",
    "property",
    "apartment",
    "mansion",
    "heya",
    "gaikan",
    "naikan",
    "panorama",
    "外観",
    "内観",
    "居室",
    "洋室",
    "和室",
    "キッチン",
    "浴室",
    "風呂",
    "トイレ",
    "洗面",
    "玄関",
    "バルコニー",
    "間取",
    "間取り",
    "物件",
    "室内",
)
IMAGE_CONTEXT_NOISE_HINTS = (
    "logo",
    "icon",
    "sprite",
    "banner",
    "header",
    "footer",
    "menu",
    "button",
    "favorite",
    "bookmark",
    "share",
    "sns",
    "campaign",
    "advert",
    "badge",
    "sectigo",
    "ssl",
    "secure",
    "cert",
    "certificate",
    "security",
    "label",
    "marker",
    "arrow",
    "close",
    "hamburger",
    "search",
    "company",
    "agent",
    "shop",
    "staff",
    "map",
    "qr",
)
EQUIPMENT_IMAGE_CONTEXT_HINTS = (
    "equipment",
    "facility",
    "amenity",
    "setsubi",
    "設備",
    "設備・特徴",
    "こだわり",
    "条件",
    "エアコン",
    "オートロック",
    "宅配ボックス",
    "防犯カメラ",
    "温水洗浄便座",
    "室内洗濯機",
    "バス・トイレ別",
    "駐車場",
    "ペット",
)
SURROUNDING_FACILITY_CONTEXT_HINTS = (
    "surrounding",
    "neighborhood",
    "nearby",
    "around",
    "周辺",
    "周辺環境",
    "周辺施設",
    "周辺情報",
    "買い物",
    "生活施設",
    "スーパー",
    "コンビニ",
    "ドラッグストア",
    "ホームセンター",
    "ショッピング",
    "銀行",
    "郵便局",
    "病院",
    "クリニック",
    "学校",
    "小学校",
    "中学校",
    "大学",
    "幼稚園",
    "保育園",
    "公園",
    "飲食店",
    "店舗",
    "商業施設",
)
HOMES_PROPERTY_IMAGE_CONTEXT_HINTS = (
    "photogallery",
    "photo gallery",
    "main-photo",
    "main photo",
    "gallery",
    "slider",
    "間取り",
    "間取",
    "外観",
    "内観",
    "室内",
    "居室",
    "洋室",
    "和室",
    "リビング",
    "リビング/ダイニング",
    "ダイニング",
    "キッチン",
    "浴室",
    "風呂",
    "トイレ",
    "洗面",
    "収納",
    "玄関",
    "バルコニー",
    "エントランス",
    "駐車場",
    "madori",
    "gaikan",
    "naikan",
    "room",
    "living",
    "kitchen",
    "bath",
    "toilet",
    "wash",
    "closet",
    "entrance",
    "balcony",
)
HOMES_NON_PROPERTY_IMAGE_CONTEXT_HINTS = (
    "lifull home's",
    "物件鮮度",
    "人気物件",
    "引越し",
    "お問合せ",
    "問合せ",
    "相談",
    "会社",
    "店舗",
    "取扱い不動産会社",
    "株式会社",
    "お気に入り",
    "掲載110番",
    "line",
    "ログイン",
    "おすすめ",
    "オススメ",
)
HOMES_NON_PROPERTY_IMAGE_URL_HINTS = (
    "/campaign/",
    "/shop/",
    "/company/",
    "/contact/",
    "/inquiry/",
    "/favorite/",
    "/common/",
    "/static/",
    "/assets/",
    "/bnr/",
    "/banner/",
    "/icon/",
    "/icons/",
    "/logo/",
    "mascot",
    "character",
    "campaign",
    "shop",
    "company",
    "contact",
    "inquiry",
    "favorite",
    "logo",
    "icon",
    "button",
    "arrow",
    "sprite",
    "hash",
    "sharp",
    "noimage",
    "loading",
)
HOMES_PROPERTY_IMAGE_URL_HINTS = (
    "/image/rent/",
    "/rent/",
    "/chintai/",
    "/bukken",
    "/photo",
    "/photos",
    "/picture",
    "/pic",
    "madori",
    "gaikan",
    "naikan",
    "room",
    "living",
    "kitchen",
    "bath",
    "toilet",
    "balcony",
)
IMAGE_ATTRIBUTE_CANDIDATES = (
    "src",
    "data-src",
    "data-original",
    "data-lazy",
    "data-lazy-src",
    "data-image",
    "data-img",
    "data-photo",
    "data-room-image",
    "data-gallery-image",
    "data-large",
    "data-full",
    "data-fullsize",
    "data-main",
    "data-zoom-image",
    "data-detail-src",
    "srcset",
)
INVALID_LISTING_PAGE_HINTS = (
    "お探しのページは見つかりません",
    "ページが見つかりません",
    "該当するページが見つかりません",
    "アクセスいただいたページは存在しません",
    "該当する物件情報の掲載は、終了しました",
    "該当する物件情報の掲載は終了しました",
    "この物件は掲載終了",
    "掲載が終了",
    "物件情報は掲載を終了しました",
    "このページは表示できません",
    "掲載店舗への状況確認はこちら",
    "こちらより再度、ご希望の賃貸物件をお探し頂けます",
    "404",
    "not found",
    "page not found",
)


@dataclass(slots=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    source: str


@dataclass(slots=True)
class PageSnapshot:
    title: str | None = None
    description: str | None = None
    text: str | None = None
    links: list[str] | None = None
    link_contexts: dict[str, str] | None = None
    image_urls: list[str] | None = None
    error: str | None = None


class WebSearchClient:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def search(self, query: str, *, max_results: int | None = None) -> list[WebSearchResult]:
        limit = max_results or self.config.web_search_max_results
        normalized_query = _normalize_cache_query(query)
        cache_key = (self.config.web_search_region, normalized_query, limit)
        cached = _cache_get(_SEARCH_CACHE, _SEARCH_CACHE_LOCK, cache_key)
        if cached is not None:
            return list(cached)

        results = self._search_with_langchain(normalized_query, limit)
        if results:
            _cache_set(_SEARCH_CACHE, _SEARCH_CACHE_LOCK, cache_key, tuple(results), SEARCH_CACHE_MAX_SIZE)
            return results
        results = self._search_with_ddgs(normalized_query, limit)
        if results:
            _cache_set(_SEARCH_CACHE, _SEARCH_CACHE_LOCK, cache_key, tuple(results), SEARCH_CACHE_MAX_SIZE)
        return results

    def _search_with_langchain(self, query: str, limit: int) -> list[WebSearchResult]:
        if DuckDuckGoSearchAPIWrapper is None or DuckDuckGoSearchResults is None:
            return []
        try:
            wrapper = DuckDuckGoSearchAPIWrapper(
                region=self.config.web_search_region,
                max_results=limit,
                safesearch="moderate",
                source="text",
            )
            search = DuckDuckGoSearchResults(api_wrapper=wrapper, output_format="list")
            raw_results = search.invoke(query)
        except Exception:
            return []

        if not isinstance(raw_results, list):
            return []
        return _coerce_search_results(raw_results)

    def _search_with_ddgs(self, query: str, limit: int) -> list[WebSearchResult]:
        if DDGS is None:
            return []
        try:
            with DDGS(timeout=8) as client:
                raw_results = client.text(query, region=self.config.web_search_region, max_results=limit)
        except Exception:
            return []
        return _coerce_search_results(raw_results or [])


class WebPageClient:
    def fetch(self, url: str, *, max_chars: int = 60000) -> PageSnapshot:
        cache_key = (_canonical_url(url), max_chars)
        cached = _cache_get(_PAGE_CACHE, _PAGE_CACHE_LOCK, cache_key)
        if cached is not None:
            return cached

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                ),
                "Accept-Language": "ja,en;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                raw = response.read(max_chars * 4)
                charset = response.headers.get_content_charset() or "utf-8"
                markup = raw.decode(charset, errors="ignore")
        except Exception as exc:
            snapshot = PageSnapshot(error=str(exc))
            _cache_set(_PAGE_CACHE, _PAGE_CACHE_LOCK, cache_key, snapshot, PAGE_CACHE_MAX_SIZE)
            return snapshot

        title = _extract_tag_text(markup, "title")
        description = _extract_meta_content(markup, "description")
        text = _html_to_text(markup)
        link_contexts = _extract_link_contexts(markup, url)
        image_urls = _extract_image_urls(markup, url)
        links = list(link_contexts)
        snapshot = PageSnapshot(
            title=title,
            description=description,
            text=text[:max_chars],
            links=links,
            link_contexts=link_contexts,
            image_urls=image_urls,
        )
        _cache_set(_PAGE_CACHE, _PAGE_CACHE_LOCK, cache_key, snapshot, PAGE_CACHE_MAX_SIZE)
        return snapshot


class RealEstateWebSearchProvider:
    def __init__(
        self,
        config: AppConfig | None = None,
        search_client: WebSearchClient | None = None,
        page_client: WebPageClient | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.search_client = search_client or WebSearchClient(self.config)
        self.page_client = page_client or WebPageClient()

    def search_listings(self, filters: dict[str, Any]) -> dict[str, Any]:
        queries = self._build_queries(filters)
        search_results = self._search_queries(queries, filters)
        expanded_results = self._expand_detail_results(search_results)
        detail_results = [item for item in expanded_results if _is_detail_listing_url(item.url)]
        search_results = detail_results or expanded_results or search_results
        search_results = _filter_excluded_search_results(search_results, filters)
        if isinstance(self.page_client, WebPageClient) and len(search_results) > 1:
            workers = max(1, min(self.config.web_page_fetch_workers, len(search_results)))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                payloads = list(executor.map(lambda item: self._to_listing_payload(item[1], item[0]), enumerate(search_results, start=1)))
            listings = [payload for payload in payloads if payload is not None]
        else:
            listings = [
                payload
                for index, item in enumerate(search_results, start=1)
                if (payload := self._to_listing_payload(item, index)) is not None
            ]
        listings = sorted(listings, key=_listing_sort_key)
        listings = _filter_excluded_listing_payloads(listings, filters)

        validated = [listing for listing in listings if listing.get("source_validated") is True]
        metadata_rich = [listing for listing in validated if _has_core_listing_metadata(listing)]
        candidates = metadata_rich or validated
        if filters.get("max_rent"):
            rent_known = [listing for listing in candidates if listing.get("rent_yen") is not None or listing.get("rent") is not None]
            if rent_known:
                candidates = rent_known
        filtered = [listing for listing in candidates if self._matches_soft_filters(listing, filters)]
        results = filtered or candidates

        return {
            "results": results,
            "total": len(results),
            "filters_used": {
                **filters,
                "search_provider": "web",
                "search_query": queries[0] if queries else "",
                "search_queries": queries,
                "validated_results": len(validated),
                "metadata_rich_results": len(metadata_rich),
                "excluded_previous_results": _excluded_result_count(filters),
                "soft_filters_relaxed": bool(candidates and not filtered),
            },
        }

    def _search_queries(self, queries: list[str], filters: dict[str, Any] | None = None) -> list[WebSearchResult]:
        filters = filters or {}
        result_page = max(1, _parse_int(filters.get("result_page")) or 1)
        search_more = bool(filters.get("search_more") or filters.get("exclude_source_urls") or result_page > 1)
        query_limit = max(1, self.config.web_search_query_limit)
        if search_more:
            query_limit = min(len(queries), query_limit + (4 * (result_page - 1)))
        queries = queries[:query_limit]
        seen: set[str] = set()
        results: list[WebSearchResult] = []
        if search_more:
            per_query_limit = min(12, max(6, self.config.web_search_max_results * min(result_page, 3)))
            target_count = min(max(self.config.web_search_max_results * (result_page + 1), self.config.web_search_max_results), 60)
        else:
            per_query_limit = min(6, max(2, self.config.web_search_max_results))
            target_count = min(max(self.config.web_search_max_results * 2, self.config.web_search_max_results), 24)
        if isinstance(self.search_client, WebSearchClient) and len(queries) > 1:
            workers = max(1, min(self.config.web_search_query_workers, len(queries)))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                query_results = list(executor.map(lambda query: self.search_client.search(query, max_results=per_query_limit), queries))
        else:
            query_results = [self.search_client.search(query, max_results=per_query_limit) for query in queries]

        for items in query_results:
            for item in items:
                if not _is_allowed_listing_source(item.url):
                    continue
                normalized_url = _canonical_url(item.url)
                if normalized_url in seen:
                    continue
                seen.add(normalized_url)
                results.append(item)
                if len(results) >= target_count:
                    return results
        return results

    def _expand_detail_results(self, search_results: list[WebSearchResult]) -> list[WebSearchResult]:
        seen: set[str] = set()
        expanded: list[WebSearchResult] = []
        for result in search_results:
            if _is_detail_listing_url(result.url):
                normalized = _canonical_url(result.url)
                if normalized not in seen:
                    expanded.append(result)
                    seen.add(normalized)
                continue

            snapshot = self.page_client.fetch(result.url, max_chars=30000)
            detail_links = [
                link
                for link in snapshot.links or []
                if _is_allowed_listing_source(link) and _is_detail_listing_url(link)
            ]
            for link in detail_links[:3]:
                normalized = _canonical_url(link)
                if normalized in seen:
                    continue
                expanded.append(
                    WebSearchResult(
                        title=result.title,
                        url=link,
                        snippet=(snapshot.link_contexts or {}).get(link) or snapshot.description or result.snippet,
                        source=_source_name(link),
                    )
                )
                seen.add(normalized)
                if len(expanded) >= self.config.web_search_max_results:
                    return expanded

            if not detail_links and not _is_collection_url(result.url):
                normalized = _canonical_url(result.url)
                if normalized not in seen:
                    expanded.append(result)
                    seen.add(normalized)
        return expanded

    def _build_queries(self, filters: dict[str, Any]) -> list[str]:
        area_parts = [
            str(filters.get("prefecture") or ""),
            str(filters.get("city") or ""),
            str(filters.get("ward") or ""),
            str(filters.get("nearest_station") or filters.get("station") or ""),
        ]
        area_label = " ".join(part for part in area_parts if part.strip()) or "Japan"
        jp_area_label = _to_japanese_area_label(filters) or area_label
        budget_yen = _parse_int(filters.get("max_rent"))
        budget_man = round(budget_yen / 10000, 1) if budget_yen else None
        layout = str(filters.get("preferred_layout") or "").strip()

        base_terms: list[str] = []
        if budget_yen:
            base_terms.extend(
                [
                    f"{jp_area_label} 賃貸 {budget_man:g}万円",
                ]
            )
        base_terms.extend(
            [
                f"{jp_area_label} 賃貸 マンション アパート",
                f"{area_label} chintai apartment",
            ]
        )
        if budget_yen:
            base_terms.append(f"{area_label} chintai apartment under {budget_yen} yen")
        if layout:
            base_terms = [f"{term} {layout}" for term in base_terms]
        if filters.get("near_station"):
            base_terms = [f"{term} 駅徒歩" for term in base_terms]

        queries: list[str] = []
        for term in base_terms:
            for profile in REAL_ESTATE_SOURCE_PROFILES:
                queries.append(f"{term} site:{profile.site_scope}")
        queries.append(f"{jp_area_label} 賃貸")
        return list(dict.fromkeys(queries))

    def _matches_soft_filters(self, listing: dict[str, Any], filters: dict[str, Any]) -> bool:
        max_rent = _parse_int(filters.get("max_rent"))
        rent = _parse_int(listing.get("rent_yen") or listing.get("rent"))
        if max_rent is not None and rent is not None and rent > max_rent:
            return False

        preferred_layout = filters.get("preferred_layout")
        if preferred_layout and listing.get("layout") and str(preferred_layout).upper() != str(listing["layout"]).upper():
            return False

        return True

    def _to_listing_payload(self, result: WebSearchResult, index: int) -> dict[str, Any] | None:
        page = self.page_client.fetch(result.url)
        page_source_text = " ".join(part for part in [page.title, page.description, page.text] if part)
        page_metadata = _extract_listing_metadata(page_source_text)
        validation_reason = "validated"
        source_validated = False
        if page_source_text.strip():
            source_validated = _page_has_listing_content(page, page_metadata)
            if not source_validated:
                return None
        else:
            validation_reason = page.error or "empty_detail_page"

        source_text = " ".join(part for part in [result.title, result.snippet, page_source_text] if part)
        combined_metadata = _extract_listing_metadata(source_text)
        listing_id = _stable_listing_id(result.url, prefix="web")
        rent = page_metadata["rent_yen"] if page_metadata["rent_yen"] is not None else combined_metadata["rent_yen"]
        management_fee = (
            page_metadata["management_fee"] if page_metadata["management_fee"] is not None else combined_metadata["management_fee"]
        )
        walk_min = page_metadata["walk_min"] if page_metadata["walk_min"] is not None else combined_metadata["walk_min"]
        area_m2 = page_metadata["area_m2"] if page_metadata["area_m2"] is not None else combined_metadata["area_m2"]
        layout = page_metadata["layout"] if page_metadata["layout"] is not None else combined_metadata["layout"]
        city, ward = _extract_area_labels(page_source_text)
        if city is None and ward is None:
            city, ward = _extract_area_labels(source_text)
        station = page_metadata["nearest_station"] if page_metadata["nearest_station"] is not None else combined_metadata["nearest_station"]
        building_age = page_metadata["building_age"] if page_metadata["building_age"] is not None else combined_metadata["building_age"]
        construction_year = (
            page_metadata["construction_year"]
            if page_metadata["construction_year"] is not None
            else combined_metadata["construction_year"]
        )
        if construction_year is None and building_age is not None:
            construction_year = date.today().year - building_age
        if building_age is None and construction_year is not None:
            building_age = max(0, date.today().year - construction_year)
        floor = page_metadata["floor"] if page_metadata["floor"] is not None else combined_metadata["floor"]
        title = _clean_title(page.title or result.title or result.source)
        image_urls = _prioritize_listing_images(page.image_urls or [])
        metadata_fields = {
            "rent_yen": rent,
            "management_fee": management_fee,
            "layout": layout,
            "area_m2": area_m2,
            "walk_min": walk_min,
            "nearest_station": station,
            "building_age": building_age,
            "construction_year": construction_year,
            "floor": floor,
        }

        return {
            "listing_id": listing_id,
            "id": listing_id,
            "title": title,
            "city": city,
            "ward": ward,
            "rent_yen": rent,
            "rent": rent,
            "management_fee": management_fee,
            "layout": layout,
            "area_m2": area_m2,
            "building_age": building_age,
            "construction_year": construction_year,
            "floor": floor,
            "walk_min": walk_min,
            "distance_to_station_min": walk_min,
            "nearest_station": station,
            "station": station,
            "nearby_facilities": _extract_nearby_facilities(source_text),
            "image_urls": image_urls,
            "source_url": result.url,
            "source_name": result.source,
            "source_snippet": page.description or result.snippet,
            "source_kind": _source_kind(result.url, metadata_fields),
            "source_validated": source_validated,
            "source_validation_reason": validation_reason,
            "metadata_fields_found": sorted(key for key, value in metadata_fields.items() if value is not None),
            "metadata_error": page.error,
            "extraction_confidence": _estimate_listing_confidence(result, metadata_fields, image_urls=image_urls),
            "document": source_text[:4000],
            "result_rank": index,
        }


class PublicContextProvider:
    def __init__(self, config: AppConfig | None = None, search_client: WebSearchClient | None = None) -> None:
        self.config = config or AppConfig()
        self.search_client = search_client or WebSearchClient(self.config)

    def get_context(self, area: dict[str, Any]) -> dict[str, Any]:
        if not self.config.public_context_enabled:
            return {}

        area_label = " ".join(
            str(area.get(key) or "")
            for key in ["prefecture", "city", "ward", "nearest_station"]
            if area.get(key)
        ).strip() or "Japan"

        return {
            "area_label": area_label,
            "datasets": {
                "housing_land_survey": self._estat_housing_context(area_label),
                "mlit_real_estate": self._mlit_market_context(area),
                "hazard_safety": self._search_dataset_context("hazard_safety", area_label),
                "regional_indicators": self._estat_dashboard_context(area_label),
            },
        }

    def _estat_housing_context(self, area_label: str) -> dict[str, Any]:
        data = self._search_dataset_context("housing_land_survey", area_label)
        data["api"] = {
            "provider": "e-Stat",
            "requires_key": True,
            "configured": bool(self.config.estat_app_id),
            "dataset": "Housing and Land Survey",
        }
        return data

    def _estat_dashboard_context(self, area_label: str) -> dict[str, Any]:
        data = self._search_dataset_context("regional_indicators", area_label)
        data["api"] = {
            "provider": "e-Stat Statistics Dashboard API",
            "requires_key": False,
            "configured": True,
            "dataset": "Regional indicators",
        }
        return data

    def _mlit_market_context(self, area: dict[str, Any]) -> dict[str, Any]:
        area_label = " ".join(str(area.get(key) or "") for key in ["prefecture", "city", "ward"] if area.get(key)).strip()
        data = self._search_dataset_context("mlit_real_estate", area_label or "Japan")
        data["api"] = {
            "provider": "MLIT Real Estate Information Library",
            "requires_key": True,
            "configured": bool(self.config.mlit_api_key),
            "dataset": "Real estate transaction / land price context",
        }
        return data

    def _search_dataset_context(self, dataset_key: str, area_label: str) -> dict[str, Any]:
        query = DATASET_CONTEXT_QUERIES[dataset_key].format(area=area_label)
        results = self.search_client.search(query, max_results=5)
        return {
            "source": "web_search",
            "query": query,
            "items": [
                {"title": item.title, "url": item.url, "snippet": item.snippet, "source": item.source}
                for item in results
            ],
        }


class EStatApiClient:
    base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def get_stats_data(self, stats_data_id: str, **params: Any) -> dict[str, Any]:
        if not self.config.estat_app_id:
            return {"error": "ESTAT_APP_ID is not configured"}
        query = {"appId": self.config.estat_app_id, "statsDataId": stats_data_id, "lang": params.pop("lang", "J"), **params}
        return _get_json(f"{self.base_url}/getStatsData", query)


class MLITRealEstateApiClient:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def get_transaction_prices(self, **params: Any) -> dict[str, Any]:
        if not self.config.mlit_api_key:
            return {"error": "MLIT_API_KEY is not configured"}
        return self._get("XIT001", params)

    def get_land_price_points(self, **params: Any) -> dict[str, Any]:
        if not self.config.mlit_api_key:
            return {"error": "MLIT_API_KEY is not configured"}
        return self._get("XPT002", params)

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        return _get_json(
            f"{self.config.mlit_api_base_url.rstrip('/')}/{endpoint}",
            params,
            headers={"Ocp-Apim-Subscription-Key": self.config.mlit_api_key or ""},
        )


def _get_json(url: str, params: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    encoded = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
    request = urllib.request.Request(f"{url}?{encoded}", headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc), "url": url}


def _coerce_search_results(raw_results: list[dict[str, Any]]) -> list[WebSearchResult]:
    results: list[WebSearchResult] = []
    for item in raw_results:
        title = str(item.get("title") or "").strip()
        url = str(item.get("link") or item.get("href") or item.get("url") or "").strip()
        snippet = str(item.get("snippet") or item.get("body") or "").strip()
        if not title or not url:
            continue
        results.append(WebSearchResult(title=title, url=url, snippet=snippet, source=_source_name(url)))
    return results


def _normalize_cache_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _cache_get(cache: OrderedDict[Any, Any], lock: threading.Lock, key: Any) -> Any | None:
    with lock:
        if key not in cache:
            return None
        value = cache.pop(key)
        cache[key] = value
        return value


def _cache_set(cache: OrderedDict[Any, Any], lock: threading.Lock, key: Any, value: Any, max_size: int) -> None:
    with lock:
        if key in cache:
            cache.pop(key)
        cache[key] = value
        while len(cache) > max_size:
            cache.popitem(last=False)


def _canonical_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", parsed.query, ""))


def _source_name(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _matching_profile(url: str) -> SourceProfile | None:
    parsed = urllib.parse.urlparse(url)
    source = _source_name(url)
    path = parsed.path.lower()
    for profile in REAL_ESTATE_SOURCE_PROFILES:
        if not any(source == domain or source.endswith(f".{domain}") for domain in profile.domains):
            continue
        if any(fragment in path for fragment in profile.excluded_path_fragments):
            return None
        prefixes = tuple(prefix for prefix in profile.required_path_prefixes if prefix)
        if prefixes and not any(path.startswith(prefix) for prefix in prefixes):
            if source.startswith("chintai.") and profile.name == "homes.co.jp":
                return profile
            return None
        return profile
    return None


def _is_allowed_listing_source(url: str) -> bool:
    return _matching_profile(url) is not None


def _source_kind(url: str, metadata_fields: dict[str, Any]) -> str:
    found = sum(value is not None for value in metadata_fields.values())
    if _is_detail_listing_url(url) and found >= 3:
        return "listing_detail"
    if _is_detail_listing_url(url):
        return "listing_candidate"
    return "search_result"


def _is_collection_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    source = _source_name(url)
    markers = ("/list", "/area/", "/ensen/", "/city/", "-mcity", "-locate", "/locate/", "/sapporo/", "/hokkaido/sapporo")
    if any(marker in path for marker in markers):
        return True
    return source.startswith("chintai.") and not _is_detail_listing_url(url)


def _is_detail_listing_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    query = parsed.query.lower()
    source = _source_name(url)
    if source.endswith("suumo.jp"):
        return "/chintai/" in path and bool(re.search(r"/(?:bc|jc)_\d+", path))
    if source.endswith("homes.co.jp"):
        return "/chintai/" in path and bool(re.search(r"/(?:b-|room|detail|rent-)", path))
    if source.endswith("athome.co.jp"):
        return "/chintai/" in path and bool(re.search(r"/(?:\d{6,}|kr_|detail|room)", path))
    if source.endswith("chintai.net"):
        return "/detail/" in path or "/bk-" in path
    if source.endswith("able.co.jp"):
        return ("detail.do" in path and "bk=" in query) or "/detail/bk" in path
    if source.endswith("minimini.jp"):
        return "/detail" in path or bool(re.search(r"/\d{5,}", path))
    return False


def _has_core_listing_metadata(listing: dict[str, Any]) -> bool:
    return bool(
        listing.get("rent_yen")
        or (listing.get("layout") and listing.get("area_m2"))
        or (listing.get("nearest_station") and listing.get("walk_min"))
    )


def _listing_sort_key(listing: dict[str, Any]) -> tuple[Any, ...]:
    rent = _parse_int(listing.get("rent_yen") or listing.get("rent"))
    walk = _parse_int(listing.get("walk_min") or listing.get("distance_to_station_min"))
    return (
        -float(listing.get("extraction_confidence") or 0),
        0 if rent is not None else 1,
        rent if rent is not None else 999999999,
        walk if walk is not None else 999,
        SOURCE_PRIORITY.get(str(listing.get("source_name") or ""), 99),
        _canonical_url(str(listing.get("source_url") or "")),
        int(listing.get("result_rank") or 9999),
    )


def _filter_excluded_search_results(results: list[WebSearchResult], filters: dict[str, Any]) -> list[WebSearchResult]:
    excluded_urls = _excluded_source_urls(filters)
    if not excluded_urls:
        return results
    return [result for result in results if _canonical_url(result.url) not in excluded_urls]


def _filter_excluded_listing_payloads(listings: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    excluded_ids = _excluded_listing_ids(filters)
    excluded_urls = _excluded_source_urls(filters)
    if not excluded_ids and not excluded_urls:
        return listings
    filtered: list[dict[str, Any]] = []
    for listing in listings:
        listing_id = str(listing.get("id") or listing.get("listing_id") or "")
        source_url = str(listing.get("source_url") or "")
        if listing_id and listing_id in excluded_ids:
            continue
        if source_url and _canonical_url(source_url) in excluded_urls:
            continue
        filtered.append(listing)
    return filtered


def _excluded_result_count(filters: dict[str, Any]) -> int:
    return len(_excluded_listing_ids(filters) | _excluded_source_urls(filters))


def _excluded_listing_ids(filters: dict[str, Any]) -> set[str]:
    raw_values = filters.get("exclude_listing_ids") or []
    if not isinstance(raw_values, list):
        return set()
    return {str(value).strip() for value in raw_values if str(value).strip()}


def _excluded_source_urls(filters: dict[str, Any]) -> set[str]:
    raw_values = filters.get("exclude_source_urls") or []
    if not isinstance(raw_values, list):
        return set()
    return {_canonical_url(str(value)) for value in raw_values if str(value).strip()}


def _extract_listing_metadata(text: str) -> dict[str, Any]:
    return {
        "rent_yen": _extract_rent_yen(text),
        "management_fee": _extract_management_fee_yen(text),
        "walk_min": _extract_walk_min(text),
        "area_m2": _extract_area_m2(text),
        "layout": _extract_layout(text),
        "nearest_station": _extract_station(text),
        "building_age": _extract_building_age(text),
        "construction_year": _extract_construction_year(text),
        "floor": _extract_floor(text),
    }


def _extract_nearby_facilities(text: str) -> list[str]:
    if not text.strip():
        return []

    lowered = text.lower()
    normalized = _normalize_phrase(text)
    facilities: list[str] = []
    for facility_key, tokens in NEARBY_FACILITY_PROFILES:
        for token in tokens:
            lowered_token = token.lower()
            normalized_token = _normalize_phrase(token)
            if lowered_token in lowered or (normalized_token and normalized_token in normalized):
                facilities.append(facility_key)
                break
    return facilities


def _page_has_listing_content(page: PageSnapshot, metadata: dict[str, Any]) -> bool:
    if page.error:
        return False

    page_text = " ".join(part for part in [page.title, page.description, page.text] if part)
    normalized = _normalize_phrase(page_text)
    normalized_invalid_markers = [marker for marker in (_normalize_phrase(item) for item in INVALID_LISTING_PAGE_HINTS) if marker]
    if any(marker in normalized for marker in normalized_invalid_markers):
        return False
    if any(marker.lower() in page_text.lower() for marker in INVALID_LISTING_PAGE_HINTS):
        return False

    if len(page_text.strip()) < 40:
        return False

    rent = metadata.get("rent_yen")
    area = metadata.get("area_m2")
    layout = metadata.get("layout")
    walk = metadata.get("walk_min")
    station = metadata.get("nearest_station")
    build_marker = metadata.get("construction_year") or metadata.get("building_age")
    signal_count = sum(
        value is not None
        for value in [rent, area, layout, walk, station, build_marker]
    )
    primary_count = sum(value is not None for value in [rent, area, layout])
    location_count = sum(value is not None for value in [walk, station])

    if signal_count >= 4 and primary_count >= 2:
        return True
    if primary_count >= 2 and location_count >= 1:
        return True
    if page.image_urls and primary_count >= 2 and build_marker is not None:
        return True
    listing_value_markers = (
        "㎡",
        "m2",
        "m²",
        "ldk",
        "dk",
        "1k",
        "1r",
        "徒歩",
        "駅",
        "間取り",
        "専有面積",
        "階",
        "築",
        "緕｡",
        "蠕呈ｭｩ",
        "髢灘叙",
        "蟆よ怏",
        "髫",
        "遽",
    )
    money_markers = ("賃料", "家賃", "管理費", "円", "万円", "rent", "price", "雉", "邂", "蜀", "荳")
    if any(marker.lower() in page_text.lower() for marker in money_markers) and any(
        marker.lower() in page_text.lower() for marker in listing_value_markers
    ):
        return True
    listing_marker_count = sum(
        1 for marker in listing_value_markers if marker.lower() in page_text.lower()
    ) + sum(1 for marker in money_markers if marker.lower() in page_text.lower())
    return len(page_text.strip()) >= 40 and listing_marker_count >= 2


def _stable_listing_id(value: str, *, prefix: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _extract_tag_text(markup: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", markup, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _clean_text(match.group(1))


def _extract_meta_content(markup: str, name: str) -> str | None:
    patterns = [
        rf"<meta[^>]+(?:name|property)=['\"](?:{re.escape(name)}|og:{re.escape(name)})['\"][^>]+content=['\"]([^'\"]+)['\"][^>]*>",
        rf"<meta[^>]+content=['\"]([^'\"]+)['\"][^>]+(?:name|property)=['\"](?:{re.escape(name)}|og:{re.escape(name)})['\"][^>]*>",
    ]
    for pattern in patterns:
        match = re.search(pattern, markup, re.IGNORECASE | re.DOTALL)
        if match:
            return _clean_text(match.group(1))
    return None


def _html_to_text(markup: str) -> str:
    cleaned = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", markup, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<br\s*/?>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</(?:p|div|li|tr|h[1-6])>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return _clean_text(cleaned)


def _extract_link_contexts(markup: str, base_url: str) -> dict[str, str]:
    contexts: dict[str, str] = {}
    for match in re.finditer(r"<a\b[^>]+href=['\"]([^'\"#]+)['\"][^>]*>(.*?)</a>", markup, re.IGNORECASE | re.DOTALL):
        href = html.unescape(match.group(1)).strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:")):
            continue
        absolute = _canonical_url(urllib.parse.urljoin(base_url, href))
        anchor_text = _html_to_text(match.group(2))
        window = markup[max(0, match.start() - 1200) : min(len(markup), match.end() + 1200)]
        context = _clean_text(f"{anchor_text} {_html_to_text(window)}")
        if absolute not in contexts or len(context) > len(contexts[absolute]):
            contexts[absolute] = context[:3000]
    return contexts


def _extract_image_urls(markup: str, base_url: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    meta_image = _extract_meta_content(markup, "image")
    if meta_image:
        absolute_meta = urllib.parse.urljoin(base_url, meta_image)
        meta_score = _score_listing_image_candidate(absolute_meta, "meta image listing preview", width=None, height=None)
        if meta_score > 0:
            candidates.append((meta_score, absolute_meta))

    for match in re.finditer(r"<(?:img|source)\b([^>]*?)>", markup, re.IGNORECASE | re.DOTALL):
        tag_markup = match.group(0)
        tag_attrs = match.group(1)
        width = _extract_html_numeric_attr(tag_markup, "width")
        height = _extract_html_numeric_attr(tag_markup, "height")
        window = markup[max(0, match.start() - 800) : min(len(markup), match.end() + 800)]
        context = _clean_text(f"{tag_attrs} {window} {_html_to_text(window)}")
        for raw_value in _extract_image_attribute_values(tag_markup):
            for candidate_url in _iter_image_attribute_urls(raw_value):
                absolute = urllib.parse.urljoin(base_url, candidate_url)
                score = _score_listing_image_candidate(absolute, context, width=width, height=height)
                if score > 0:
                    candidates.append((score, absolute))

    for match in re.finditer(r"<a\b([^>]*?)href=['\"]([^'\"]+)['\"]([^>]*?)>", markup, re.IGNORECASE | re.DOTALL):
        tag_markup = match.group(0)
        raw_value = html.unescape(match.group(2)).strip()
        if not raw_value:
            continue
        absolute = urllib.parse.urljoin(base_url, raw_value)
        window = markup[max(0, match.start() - 800) : min(len(markup), match.end() + 800)]
        context = _clean_text(f"{match.group(1)} {match.group(3)} {window} {_html_to_text(window)}")
        score = _score_listing_image_candidate(absolute, context, width=None, height=None)
        if score > 0:
            candidates.append((score, absolute))

    for match in re.finditer(r"""url\((['"]?)([^'")]+)\1\)""", markup, re.IGNORECASE):
        raw_value = html.unescape(match.group(2)).strip()
        if not raw_value:
            continue
        absolute = urllib.parse.urljoin(base_url, raw_value)
        window = markup[max(0, match.start() - 800) : min(len(markup), match.end() + 800)]
        context = _clean_text(f"{window} {_html_to_text(window)}")
        score = _score_listing_image_candidate(absolute, context, width=None, height=None)
        if score > 0:
            candidates.append((score, absolute))

    for score, url in _extract_script_image_candidates(markup, base_url):
        if score > 0:
            candidates.append((score, url))

    candidates.sort(key=lambda item: (-item[0], -_image_quality_score(item[1]), item[1]))
    deduped: list[str] = []
    seen: set[str] = set()
    for _, url in candidates:
        normalized = _canonical_image_url(url)
        dedupe_key = _image_dedupe_key(normalized)
        if dedupe_key in seen or not _looks_like_image_url(normalized) or _looks_like_low_quality_image_url(normalized):
            continue
        seen.add(dedupe_key)
        deduped.append(normalized)
    return deduped


def _canonical_image_url(url: str) -> str:
    url = _normalize_image_url_candidate(url)
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


def _looks_like_image_url(url: str) -> bool:
    lowered = url.lower()
    if lowered.startswith("data:"):
        return False
    if _domain_listing_image_score(lowered) > 0:
        return True
    if any(ext in lowered for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return True
    if any(token in lowered for token in ("image", "photo", "gallery", "madori", "gaikan", "room", "shashin", "thumbnail")):
        return True
    if any(token in lowered for token in ("/img/", "/image/", "/images/", "/photo/", "/gallery/")):
        return True
    if any(token in lowered for token in ("format=jpg", "format=jpeg", "fm=jpg", "fm=jpeg", "type=image")):
        return True
    return False


def _prioritize_listing_images(image_urls: list[str]) -> list[str]:
    scored: list[tuple[int, str]] = []
    for url in image_urls:
        lowered = url.lower()
        if any(token in lowered for token in IMAGE_NOISE_HINTS):
            continue
        normalized = _canonical_image_url(url)
        if _looks_like_low_quality_image_url(normalized):
            continue
        score = _domain_listing_image_score(lowered)
        if any(token in lowered for token in LISTING_IMAGE_HINTS):
            score += 3
        if "madori" in lowered or "floor" in lowered or "plan" in lowered or "%E9%96%93%E5%8F%96" in lowered:
            score += 4
        if "gaikan" in lowered or "room" in lowered or "photo" in lowered:
            score += 2
        if score > 0:
            scored.append((score, normalized))
    scored.sort(key=lambda item: (-item[0], -_image_quality_score(item[1]), item[1]))
    deduped: list[str] = []
    seen: set[str] = set()
    for _, url in scored:
        dedupe_key = _image_dedupe_key(url)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(url)
    return deduped


def _image_dedupe_key(url: str) -> str:
    normalized = _normalize_image_url_candidate(url)
    parsed = urllib.parse.urlparse(normalized)
    host = parsed.netloc.lower()
    path = re.sub(r"/+", "/", parsed.path.lower())
    if host.endswith("chintai.net") or host.endswith("able.co.jp") or host.endswith("minimini.jp") or host.endswith("homes.co.jp"):
        path = re.sub(r"_(?:s|m|l|ll|thumb|thumbnail|blur)(?=\.[a-z0-9]+$|$)", "", path)
        path = re.sub(r"(?:-|_)(?:\d{2,4})x\d{2,4}(?=\.[a-z0-9]+$|$)", "", path)
        path = re.sub(r"/(?:thumb|thumbnail|small|blur|large|full|original)(?=/)", "/", path)
        path = re.sub(r"/(?:pc|sp|mobile)/(?=(?:thumb|thumbnail|small|large|full)/)", "/", path)
        return f"{host}{path}"
    return urllib.parse.urlunparse((parsed.scheme, host, parsed.path, "", parsed.query, ""))


def _image_quality_score(url: str) -> int:
    lowered = _normalize_image_url_candidate(url).lower()
    score = 0
    if any(token in lowered for token in ("original", "large", "full", "main", "detail", "width=800", "width=1024", "width=1200")):
        score += 4
    if any(token in lowered for token in ("thumb", "thumbnail", "small", "blur", "loading", "placeholder")):
        score -= 8
    width_match = re.search(r"(?:[?&](?:w|width|img_width|resize)=|[_/-])(\d{2,4})(?:[x&/_-]|$)", lowered)
    if width_match:
        width = _parse_int(width_match.group(1)) or 0
        if width >= 640:
            score += 3
        elif width and width <= 320:
            score -= 4
    quality_match = re.search(r"[?&](?:q|quality)=(\d{1,3})(?:&|$)", lowered)
    if quality_match:
        quality = _parse_int(quality_match.group(1)) or 0
        if quality >= 75:
            score += 2
        elif quality and quality <= 50:
            score -= 5
    return score


def _looks_like_low_quality_image_url(url: str) -> bool:
    lowered = _normalize_image_url_candidate(url).lower()
    if any(token in lowered for token in ("blur=1", "blur=true", "placeholder", "loading", "noimage", "no_image")):
        return True
    width_match = re.search(r"[?&](?:w|width|img_width|resize)=(\d{1,4})(?:&|$)", lowered)
    if width_match and (_parse_int(width_match.group(1)) or 0) < 300:
        return True
    quality_match = re.search(r"[?&](?:q|quality)=(\d{1,3})(?:&|$)", lowered)
    return bool(quality_match and (_parse_int(quality_match.group(1)) or 0) < 40)


def _score_listing_image_candidate(url: str, context: str, *, width: int | None, height: int | None) -> int:
    url = _normalize_image_url_candidate(url)
    lowered_url = url.lower()
    lowered_context = _normalize_phrase(context)
    domain_score = _domain_listing_image_score(lowered_url)
    if not _looks_like_image_url(lowered_url):
        return -10
    if any(token in lowered_url for token in IMAGE_NOISE_HINTS) or _looks_like_icon_url(lowered_url):
        return -10
    if _looks_like_homes_non_property_image(lowered_url, context):
        return -9
    if _looks_like_surrounding_facility_context(context, lowered_context, lowered_url):
        return -9
    if _looks_like_equipment_icon_context(context, lowered_context):
        return -8
    has_listing_context = any(_context_contains_hint(lowered_context, token) for token in LISTING_IMAGE_CONTEXT_HINTS)
    if domain_score <= 0 and not has_listing_context and any(
        _context_contains_hint(lowered_context, token) for token in IMAGE_CONTEXT_NOISE_HINTS
    ):
        return -8

    score = domain_score
    if any(token in lowered_url for token in LISTING_IMAGE_HINTS):
        score += 4
    if has_listing_context:
        score += 5
    if any(_context_contains_hint(lowered_context, token) for token in ("gallery", "slider", "carousel", "photo", "image", "property", "listing")):
        score += 2
    if "madori" in lowered_url or "間取り" in context or "間取" in context:
        score += 5
    if "gaikan" in lowered_url or "外観" in context:
        score += 4
    if "naikan" in lowered_url or "室内" in context or "内観" in context:
        score += 4
    if any(token in lowered_url for token in ("room", "living", "kitchen", "bath", "toilet", "balcony")):
        score += 3
    if width is not None and width <= 180:
        score -= 5
    if height is not None and height <= 120:
        score -= 5
    if any(token in lowered_url for token in ("logo", "icon", "button", "banner", "header", "footer", "sprite")):
        score -= 10
    return score


def _looks_like_homes_non_property_image(lowered_url: str, context: str) -> bool:
    parsed = urllib.parse.urlparse(lowered_url)
    if not parsed.netloc.endswith("homes.co.jp"):
        return False
    path_and_query = f"{parsed.path.lower()}?{parsed.query.lower()}"
    if any(token in path_and_query for token in HOMES_NON_PROPERTY_IMAGE_URL_HINTS):
        return True
    lowered_context = context.lower()
    center = _url_context_center(lowered_context, lowered_url)
    nearest_property = _nearest_marker_distance(context, HOMES_PROPERTY_IMAGE_CONTEXT_HINTS, center=center)
    has_strong_property_url_hint = any(
        token in path_and_query
        for token in ("madori", "gaikan", "naikan", "room", "living", "kitchen", "bath", "toilet", "balcony")
    )
    has_numeric_tail = bool(re.search(r"/(?:0|[1-9]\d?)(?:$|[?._-])", parsed.path.lower()))
    if has_numeric_tail and (nearest_property is None or nearest_property > 120):
        return True
    if nearest_property is not None and nearest_property <= 160:
        return False
    nearest_noise = _nearest_marker_distance(context, HOMES_NON_PROPERTY_IMAGE_CONTEXT_HINTS, center=center)
    if nearest_noise is not None and (nearest_property is None or nearest_noise < nearest_property):
        return True
    if any(token in lowered_context for token in ("character", "mascot", "illust", "campaign")):
        return True
    return nearest_property is None and not has_strong_property_url_hint


def _domain_listing_image_score(url: str) -> int:
    parsed = urllib.parse.urlparse(_normalize_image_url_candidate(url))
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()
    if host.endswith("chintai.net"):
        if re.match(r"^(?:img|image|photo)\d*\.", host) or any(token in path for token in ("/image", "/photo", "/img")):
            return 5
        if any(token in query for token in ("image", "photo", "img")):
            return 3
    if host.endswith("able.co.jp"):
        if re.match(r"^(?:img|image|photo)\d*\.", host):
            return 5
        if any(token in path for token in ("/image", "/photo", "/img", "/room", "/madori", "/gaikan")):
            return 5
        if any(token in query for token in ("image", "photo", "img", "bk=")):
            return 3
    if host.endswith("homes.co.jp"):
        if re.match(r"^(?:image|img|photo|image\d+)\.", host):
            return 5
        if any(token in path for token in ("/image", "/images", "/photo", "/photos", "/img", "/picture", "/pic")):
            return 5
        if any(token in query for token in ("image", "photo", "img", "picture", "pic", "file=")):
            return 4
    if host.endswith("minimini.jp"):
        if re.match(r"^(?:img|image|photo)\d*\.", host):
            return 5
        if any(token in path for token in ("/image", "/photo", "/img", "/room", "/madori", "/gaikan", "/bukken")):
            return 5
        if any(token in query for token in ("image", "photo", "img", "picture", "pic")):
            return 4
    return 0


def _looks_like_icon_url(lowered_url: str) -> bool:
    parsed = urllib.parse.urlparse(lowered_url)
    path = parsed.path
    filename = path.rsplit("/", 1)[-1]
    return bool(
        re.search(r"(?:^|[_-])(?:ico|icon|mark|badge|setsubi|facility|equipment)(?:[_-]|\.|$)", filename)
        or re.search(r"/(?:ico|icon|icons|setsubi|equipment|facility)/", path)
    )


def _looks_like_equipment_icon_context(context: str, normalized_context: str) -> bool:
    if _context_has_strong_listing_photo_marker(context, normalized_context):
        return False
    lowered_context = context.lower()
    if any(_context_contains_hint(normalized_context, token) for token in EQUIPMENT_IMAGE_CONTEXT_HINTS):
        return True
    return any(token in lowered_context for token in EQUIPMENT_IMAGE_CONTEXT_HINTS)


def _looks_like_surrounding_facility_context(context: str, normalized_context: str, lowered_url: str) -> bool:
    lowered_context = context.lower()
    if not (
        any(_context_contains_hint(normalized_context, token) for token in SURROUNDING_FACILITY_CONTEXT_HINTS)
        or any(token in lowered_context for token in SURROUNDING_FACILITY_CONTEXT_HINTS)
    ):
        return False
    center = _url_context_center(lowered_context, lowered_url)
    facility_distance = _nearest_marker_distance(context, SURROUNDING_FACILITY_CONTEXT_HINTS, center=center)
    property_distance = _nearest_marker_distance(context, PROPERTY_IMAGE_CONTEXT_HINTS, center=center)
    if property_distance is not None and (facility_distance is None or property_distance < facility_distance):
        return False
    return True


def _url_context_center(lowered_context: str, lowered_url: str) -> int | None:
    parsed = urllib.parse.urlparse(lowered_url)
    path = parsed.path.lower()
    needles = [
        lowered_url,
        lowered_url.replace("/", "\\/"),
        path,
        path.replace("/", "\\/"),
        urllib.parse.unquote(path),
    ]
    if parsed.query:
        queryless = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", "")).lower()
        needles.extend([queryless, queryless.replace("/", "\\/")])
    for needle in sorted({item for item in needles if item}, key=len, reverse=True):
        url_index = lowered_context.find(needle)
        if url_index >= 0:
            return url_index + (len(needle) // 2)
    filename = path.rsplit("/", 1)[-1]
    if filename:
        filename_index = lowered_context.find(filename)
        if filename_index >= 0:
            return filename_index + (len(filename) // 2)
    return None


def _context_has_strong_listing_photo_marker(context: str, normalized_context: str) -> bool:
    lowered_context = context.lower()
    if any(token in lowered_context for token in PROPERTY_IMAGE_CONTEXT_HINTS):
        return True
    return any(_context_contains_hint(normalized_context, token) for token in ("main photo", "property photo", "room", "floor plan", "layout"))


PROPERTY_IMAGE_CONTEXT_HINTS = (
    "roomgallery",
    "property-gallery",
    "mainphoto",
    "main-photo",
    "roomphoto",
    "room-photo",
    "floorplan",
    "floor-plan",
    "madori",
    "gaikan",
    "naikan",
    "外観",
    "内観",
    "室内",
    "間取り",
    "間取",
)


def _nearest_marker_distance(context: str, markers: tuple[str, ...], *, center: int | None = None) -> int | None:
    lowered_context = context.lower()
    center = max(0, center if center is not None else len(lowered_context) // 2)
    distances: list[int] = []
    for marker in markers:
        lowered_marker = marker.lower()
        start = 0
        while True:
            index = lowered_context.find(lowered_marker, start)
            if index < 0:
                break
            distances.append(abs(index - center))
            start = index + max(1, len(lowered_marker))
    return min(distances) if distances else None


def _context_contains_hint(normalized_context: str, hint: str) -> bool:
    normalized_hint = _normalize_phrase(hint)
    if not normalized_hint:
        return False
    if " " in normalized_hint:
        return normalized_hint in normalized_context
    return normalized_hint in set(normalized_context.split())


def _extract_image_attribute_values(tag_markup: str) -> list[str]:
    values: list[str] = []
    for attribute in IMAGE_ATTRIBUTE_CANDIDATES:
        for match in re.finditer(rf"{re.escape(attribute)}=['\"]([^'\"]+)['\"]", tag_markup, re.IGNORECASE):
            raw_value = html.unescape(match.group(1)).strip()
            if raw_value:
                values.append(raw_value)
    return values


def _iter_image_attribute_urls(raw_value: str) -> list[str]:
    urls: list[str] = []
    for item in raw_value.split(","):
        candidate = _normalize_image_url_candidate(item.strip().split(" ")[0])
        if _is_placeholder_image_candidate(candidate):
            continue
        if candidate:
            urls.append(candidate)
    return urls


def _is_placeholder_image_candidate(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    if lowered in {"0", "1", "#", "-", "none", "null", "undefined", "about:blank"}:
        return True
    if lowered.startswith(("javascript:", "data:")):
        return True
    return False


def _normalize_image_url_candidate(value: str) -> str:
    cleaned = html.unescape(value).strip()
    cleaned = cleaned.replace("\\/", "/")
    cleaned = cleaned.replace("\\u002F", "/").replace("\\u002f", "/")
    return cleaned


def _extract_html_numeric_attr(tag_markup: str, attr_name: str) -> int | None:
    match = re.search(rf"{re.escape(attr_name)}=['\"]?(\d{{1,4}})", tag_markup, re.IGNORECASE)
    if not match:
        return None
    return _parse_int(match.group(1))


def _extract_script_image_candidates(markup: str, base_url: str) -> list[tuple[int, str]]:
    candidates: list[tuple[int, str]] = []
    for match in re.finditer(r"<script\b[^>]*>(.*?)</script>", markup, re.IGNORECASE | re.DOTALL):
        script_body = _normalize_image_url_candidate(match.group(1))
        if not any(
            token in script_body.lower()
            for token in (
                "image",
                "img",
                "photo",
                "gallery",
                "madori",
                "gaikan",
                "room",
                "chintai.net",
                "able.co.jp",
                "homes.co.jp",
                "minimini.jp",
            )
        ):
            continue
        for url_match in re.finditer(r"""https?:\/\/[^"'\\\s>]+?\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"'\\\s>]*)?""", script_body, re.IGNORECASE):
            raw_url = url_match.group(0)
            window = script_body[max(0, url_match.start() - 240) : min(len(script_body), url_match.end() + 240)]
            score = _score_listing_image_candidate(raw_url, window, width=None, height=None)
            if score > 0:
                candidates.append((score, raw_url))
        for path_match in re.finditer(r"""(?:\/|\.\.?\/)[^"'\\\s>]+?\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"'\\\s>]*)?""", script_body, re.IGNORECASE):
            raw_path = path_match.group(0)
            absolute = urllib.parse.urljoin(base_url, raw_path)
            window = script_body[max(0, path_match.start() - 240) : min(len(script_body), path_match.end() + 240)]
            score = _score_listing_image_candidate(absolute, window, width=None, height=None)
            if score > 0:
                candidates.append((score, absolute))
        for quoted_match in re.finditer(r"""['"]((?:https?:)?//[^'"]+|(?:/|\.\.?/)[^'"]+)['"]""", script_body, re.IGNORECASE):
            raw_value = _normalize_image_url_candidate(quoted_match.group(1))
            if raw_value.startswith("//"):
                raw_value = f"{urllib.parse.urlparse(base_url).scheme or 'https'}:{raw_value}"
            absolute = urllib.parse.urljoin(base_url, raw_value)
            if not _looks_like_image_url(absolute):
                continue
            window = script_body[max(0, quoted_match.start() - 240) : min(len(script_body), quoted_match.end() + 240)]
            score = _score_listing_image_candidate(absolute, window, width=None, height=None)
            if score > 0:
                candidates.append((score, absolute))
    return candidates


def _clean_text(value: str) -> str:
    unescaped = html.unescape(value)
    return re.sub(r"\s+", " ", unescaped).strip()


def _clean_title(value: str) -> str:
    title = _clean_text(value)
    title = re.sub(r"\s*\|\s*(SUUMO|HOME'S|LIFULL HOME'S|athome|CHINTAI|ABLE|minimini).*$", "", title, flags=re.IGNORECASE)
    return title[:120] or "Rental listing"


def _normalize_phrase(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("\u0111", "d"))
    ascii_like = "".join(character for character in normalized if not unicodedata.combining(character))
    compact = re.sub(r"[^a-z0-9]+", " ", ascii_like)
    return re.sub(r"\s+", " ", compact).strip()


def _normalize_text(value: str) -> str:
    return _normalize_phrase(value).replace(" ", "")


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value).replace(",", "")))
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _extract_money_yen(text: str, labels: tuple[str, ...] = ()) -> int | None:
    label_pattern = "|".join(re.escape(label) for label in labels if label)
    patterns: list[tuple[str, str]] = []
    if label_pattern:
        patterns.extend(
            [
                (rf"(?:{label_pattern})\s*[:：]?\s*(\d+(?:\.\d+)?)\s*万(?:円)?", "man"),
                (rf"(?:{label_pattern})\s*[:：]?\s*(\d{{1,3}}(?:,\d{{3}})+|\d{{4,7}})\s*円", "yen"),
                (rf"(?:{label_pattern})\D{{0,18}}(\d+(?:\.\d+)?)\s*(?:万|万円|man|10k|荳)", "man"),
                (rf"(?:{label_pattern})\D{{0,18}}(\d{{1,3}}(?:,\d{{3}})+|\d{{4,7}})\s*(?:円|yen|jpy|蜀)", "yen"),
            ]
        )
    patterns.extend(
        [
            (r"(\d+(?:\.\d+)?)\s*万(?:円)?", "man"),
            (r"(\d{1,3}(?:,\d{3})+|\d{4,7})\s*円", "yen"),
        ]
    )
    for pattern, value_type in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        if value_type == "man":
            return int(float(match.group(1)) * 10000)
        return _parse_int(match.group(1))
    return None


def _extract_rent_yen(text: str) -> int | None:
    rent = _extract_money_yen(text, RENT_LABELS)
    if rent is not None:
        return rent
    normalized = _normalize_phrase(text)
    man_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:man|10k)", normalized, re.IGNORECASE)
    if man_match:
        return int(float(man_match.group(1)) * 10000)
    yen_match = re.search(r"(\d{2,3}[,\s]?\d{3})\s*(?:yen|jpy)", text, re.IGNORECASE)
    if yen_match:
        return _parse_int(yen_match.group(1))
    compact_match = re.search(r"rent\s*(\d{4,6})", normalized)
    if compact_match:
        return _parse_int(compact_match.group(1))
    return _extract_money_yen(text)


def _extract_management_fee_yen(text: str) -> int | None:
    return _extract_money_yen(text, FEE_LABELS)


def _extract_walk_min(text: str) -> int | None:
    patterns = [
        r"徒歩\s*(\d{1,2})\s*分",
        r"駅\s*徒歩\s*(\d{1,2})\s*分",
        r"蠕呈ｭｩ\s*(\d{1,2})\s*蛻",
        r"豁ｩ\s*(\d{1,2})\s*蛻",
        r"(?:walk|walking)\s*(\d{1,2})\s*(?:min|minutes)?",
        r"(\d{1,2})\s*(?:min|minutes)\s*(?:walk|walking)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _parse_int(match.group(1))
    return None


def _extract_area_m2(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:㎡|m2|m²|sqm|平米|緕｡|蟷ｳ邀ｳ)", text, re.IGNORECASE)
    if match:
        return _parse_float(match.group(1))
    return None


def _extract_layout(text: str) -> str | None:
    match = re.search(r"\b([1-4]LDK|[1-4]DK|[1-4]K|1R)\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def _extract_station(text: str) -> str | None:
    patterns = [
        (r"([^\s]{2,24}?)駅", "駅"),
        (r"([^\s]{2,24}?)(?:蠕呈ｭｩ|徒歩)", ""),
        (r"([A-Za-z0-9][A-Za-z0-9\s-]{1,31})\s*station", " station"),
    ]
    for pattern, suffix in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            candidate = _clean_text(match.group(1)) + suffix
            if not candidate or any(label in candidate.lower() for label in ("walk", "rent", "price")):
                continue
            if 2 <= len(candidate) <= 32:
                return candidate
    return None


def _extract_building_age(text: str) -> int | None:
    if "新築" in text:
        return 0
    patterns = [
        r"築\s*(\d{1,3})\s*年",
        r"築年数\s*(\d{1,3})\s*年",
        r"遽.\s*(\d{1,3})\s*蟷",
        r"built\s*(\d{1,3})\s*years?",
        r"age\s*(\d{1,3})\s*years?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _parse_int(match.group(1))
    return None


def _extract_construction_year(text: str) -> int | None:
    patterns = [
        r"(?:築年月|建築年|建築|竣工|完成|新築年月)\D{0,12}((?:19|20)\d{2})\s*年",
        r"((?:19|20)\d{2})\s*年\s*(?:築|建築|竣工)",
        r"(?:construction|built in)\D{0,12}((?:19|20)\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _parse_int(match.group(1))
    return None


def _extract_floor(text: str) -> int | None:
    patterns = [
        r"(\d{1,2})\s*階",
        r"(\d{1,2})\s*階建",
        r"(\d{1,2})\s*髫",
        r"(\d{1,2})(?:st|nd|rd|th)?\s*floor",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _parse_int(match.group(1))
    return None


def _extract_area_labels(text: str) -> tuple[str | None, str | None]:
    normalized = _normalize_text(text)
    city = "Sapporo" if any(_normalize_text(token) in normalized for token in SAPPORO_TOKENS) else None
    ward = next((value for key, value in WARD_TOKENS.items() if key in text), None)
    ward_match = re.search(r"([A-Za-z]+)\s+(?:ward|ku)", text, re.IGNORECASE)
    if ward_match:
        ward = ward_match.group(1).title()
    return city, ward


def _to_japanese_area_label(filters: dict[str, Any]) -> str | None:
    city = str(filters.get("city") or "")
    if _normalize_text(city) == "sapporo":
        return "札幌"
    return None


def _estimate_listing_confidence(
    result: WebSearchResult,
    metadata_fields: dict[str, Any],
    *,
    image_urls: list[str],
) -> float:
    score = 0.2
    if _is_allowed_listing_source(result.url):
        score += 0.25
    if metadata_fields.get("rent_yen") is not None:
        score += 0.2
    if metadata_fields.get("layout") is not None:
        score += 0.12
    if metadata_fields.get("area_m2") is not None:
        score += 0.12
    if metadata_fields.get("walk_min") is not None or metadata_fields.get("nearest_station") is not None:
        score += 0.08
    if metadata_fields.get("building_age") is not None or metadata_fields.get("construction_year") is not None:
        score += 0.03
    if image_urls:
        score += 0.03
    return round(min(score, 0.98), 2)
