from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
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
        required_path_prefixes=("/chintai/", "/rent/", ""),
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

DATASET_CONTEXT_QUERIES = {
    "housing_land_survey": "e-Stat Housing and Land Survey rental housing {area}",
    "mlit_real_estate": "MLIT Real Estate Information Library land price real estate {area}",
    "hazard_safety": "MLIT hazard map flood earthquake safety {area}",
    "regional_indicators": "e-Stat Statistics Dashboard regional indicators population household {area}",
}


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
    error: str | None = None


class WebSearchClient:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def search(self, query: str, *, max_results: int | None = None) -> list[WebSearchResult]:
        limit = max_results or self.config.web_search_max_results
        results = self._search_with_langchain(query, limit)
        if results:
            return results
        return self._search_with_ddgs(query, limit)

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
                raw_results = client.text(
                    query,
                    region=self.config.web_search_region,
                    max_results=limit,
                )
        except Exception:
            return []
        return _coerce_search_results(raw_results or [])


class WebPageClient:
    def fetch(self, url: str, *, max_chars: int = 60000) -> PageSnapshot:
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
            return PageSnapshot(error=str(exc))

        title = _extract_tag_text(markup, "title")
        description = _extract_meta_content(markup, "description")
        text = _html_to_text(markup)
        link_contexts = _extract_link_contexts(markup, url)
        links = list(link_contexts)
        return PageSnapshot(title=title, description=description, text=text[:max_chars], links=links, link_contexts=link_contexts)


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
        search_results = self._search_queries(queries)
        expanded_results = self._expand_detail_results(search_results)
        detail_results = [item for item in expanded_results if _is_detail_listing_url(item.url)]
        search_results = detail_results or expanded_results or search_results
        listings = [self._to_listing_payload(item, index) for index, item in enumerate(search_results, start=1)]
        listings = sorted(listings, key=lambda item: (-float(item.get("extraction_confidence") or 0), item["result_rank"]))

        metadata_rich = [listing for listing in listings if _has_core_listing_metadata(listing)]
        candidates = metadata_rich or listings
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
                "metadata_rich_results": len(metadata_rich),
                "soft_filters_relaxed": bool(candidates and not filtered),
            },
        }

    def _search_queries(self, queries: list[str]) -> list[WebSearchResult]:
        seen: set[str] = set()
        results: list[WebSearchResult] = []
        per_query_limit = min(6, max(2, self.config.web_search_max_results))
        target_count = min(max(self.config.web_search_max_results * 2, self.config.web_search_max_results), 24)
        for query in queries:
            for item in self.search_client.search(query, max_results=per_query_limit):
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

        terms = [
            f"{jp_area_label} {_jp('賃貸')} {_jp('マンション')} {_jp('アパート')}",
            f"{area_label} chintai apartment",
        ]
        if layout:
            terms = [f"{term} {layout}" for term in terms]
        if budget_yen:
            terms.extend(
                [
                    f"{jp_area_label} {_jp('賃貸')} {budget_man:g}{_jp('万円以下')}",
                    f"{area_label} chintai apartment under {budget_yen} yen",
                ]
            )
        if filters.get("near_station"):
            terms = [f"{term} {_jp('駅徒歩')}" for term in terms]

        queries: list[str] = []
        for term in terms:
            for profile in REAL_ESTATE_SOURCE_PROFILES:
                queries.append(f"{term} site:{profile.site_scope}")
        queries.append(f"{jp_area_label} {_jp('賃貸')} {_jp('物件')}")
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

    def _to_listing_payload(self, result: WebSearchResult, index: int) -> dict[str, Any]:
        page = self.page_client.fetch(result.url)
        source_text = " ".join(
            part
            for part in [
                result.title,
                result.snippet,
                page.title,
                page.description,
                page.text,
            ]
            if part
        )
        listing_id = _stable_listing_id(result.url, prefix="web")
        rent = _extract_rent_yen(source_text)
        management_fee = _extract_management_fee_yen(source_text)
        walk_min = _extract_walk_min(source_text)
        area_m2 = _extract_area_m2(source_text)
        layout = _extract_layout(source_text)
        city, ward = _extract_area_labels(source_text)
        station = _extract_station(source_text)
        building_age = _extract_building_age(source_text)
        floor = _extract_floor(source_text)
        title = _clean_title(page.title or result.title or result.source)
        metadata_fields = {
            "rent_yen": rent,
            "management_fee": management_fee,
            "layout": layout,
            "area_m2": area_m2,
            "walk_min": walk_min,
            "nearest_station": station,
            "building_age": building_age,
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
            "floor": floor,
            "walk_min": walk_min,
            "distance_to_station_min": walk_min,
            "nearest_station": station,
            "station": station,
            "source_url": result.url,
            "source_name": result.source,
            "source_snippet": page.description or result.snippet,
            "source_kind": _source_kind(result.url, metadata_fields),
            "metadata_fields_found": sorted(key for key, value in metadata_fields.items() if value is not None),
            "metadata_error": page.error,
            "extraction_confidence": _estimate_listing_confidence(result, metadata_fields),
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
                {
                    "title": item.title,
                    "url": item.url,
                    "snippet": item.snippet,
                    "source": item.source,
                }
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
        query = {
            "appId": self.config.estat_app_id,
            "statsDataId": stats_data_id,
            "lang": params.pop("lang", "J"),
            **params,
        }
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


def _jp(value: str) -> str:
    return value


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
    if _is_collection_url(url):
        return "search_result"
    return "search_result"


def _is_collection_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    source = _source_name(url)
    markers = (
        "/list",
        "/area/",
        "/ensen/",
        "/city/",
        "-mcity",
        "-locate",
        "/locate/",
        "/sapporo/",
        "/hokkaido/sapporo",
    )
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


def _stable_listing_id(value: str, *, prefix: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _extract_tag_text(markup: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", markup, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _clean_text(match.group(1))


def _extract_meta_content(markup: str, name: str) -> str | None:
    pattern = rf"<meta[^>]+(?:name|property)=[\"'](?:{re.escape(name)}|og:{re.escape(name)})[\"'][^>]+content=[\"']([^\"']+)[\"'][^>]*>"
    match = re.search(pattern, markup, re.IGNORECASE | re.DOTALL)
    if not match:
        pattern = rf"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+(?:name|property)=[\"'](?:{re.escape(name)}|og:{re.escape(name)})[\"'][^>]*>"
        match = re.search(pattern, markup, re.IGNORECASE | re.DOTALL)
    return _clean_text(match.group(1)) if match else None


def _html_to_text(markup: str) -> str:
    cleaned = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", markup, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<br\s*/?>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</(?:p|div|li|tr|h[1-6])>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return _clean_text(cleaned)


def _extract_link_contexts(markup: str, base_url: str) -> dict[str, str]:
    contexts: dict[str, str] = {}
    for match in re.finditer(r"<a\b[^>]+href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", markup, re.IGNORECASE | re.DOTALL):
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


def _clean_text(value: str) -> str:
    unescaped = html.unescape(value)
    return re.sub(r"\s+", " ", unescaped).strip()


def _clean_title(value: str) -> str:
    title = _clean_text(value)
    title = re.sub(r"\s*\|\s*(SUUMO|HOME'S|LIFULL HOME'S|athome|CHINTAI|ABLE|minimini).*$", "", title, flags=re.IGNORECASE)
    return title[:120] or "Rental listing"


def _normalize_phrase(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("đ", "d"))
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
    label_pattern = "|".join(re.escape(label) for label in labels)
    scoped = rf"(?:{label_pattern})\D{{0,12}}" if label_pattern else ""
    man_match = re.search(scoped + r"(\d+(?:\.\d+)?)\s*万(?:円)?", text)
    if man_match:
        return int(float(man_match.group(1)) * 10000)
    yen_match = re.search(scoped + r"(\d{1,3}(?:,\d{3})+|\d{4,7})\s*円", text)
    if yen_match:
        return _parse_int(yen_match.group(1))
    return None


def _extract_rent_yen(text: str) -> int | None:
    rent = _extract_money_yen(text, ("賃料", "家賃", "価格", "rent"))
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
    return _extract_money_yen(text, ("管理費", "共益費", "管理・共益費"))


def _extract_walk_min(text: str) -> int | None:
    patterns = [
        r"徒歩\s*(\d{1,2})\s*分",
        r"歩\s*(\d{1,2})\s*分",
        r"(?:walk|walking)\s*(\d{1,2})\s*(?:min|minutes)?",
        r"(\d{1,2})\s*(?:min|minutes)\s*(?:walk|walking)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _parse_int(match.group(1))
    return None


def _extract_area_m2(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m2|㎡|平米|sqm)", text, re.IGNORECASE)
    if match:
        return _parse_float(match.group(1))
    return None


def _extract_layout(text: str) -> str | None:
    match = re.search(r"\b([1-4]LDK|[1-4]DK|[1-4]K|1R)\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def _extract_station(text: str) -> str | None:
    station_tokens = re.findall(r"([一-龥ぁ-んァ-ンA-Za-z0-9・-]{1,24}駅)", text)
    for token in station_tokens:
        if any(bad in token for bad in ("広さ", "以上", "徒歩", "交通", "丁目駅")):
            continue
        if token.startswith(("・", "-", "ー")):
            continue
        if "線" in token:
            token = token.split("線")[-1]
        if 3 <= len(token) <= 12:
            return token.strip()
    en_match = re.search(r"([A-Za-z0-9\s-]{2,32})(?:station)", text, re.IGNORECASE)
    if en_match:
        return en_match.group(1).strip()
    return None


def _extract_building_age(text: str) -> int | None:
    if "新築" in text:
        return 0
    match = re.search(r"築\s*(\d{1,3})\s*年", text)
    if match:
        return _parse_int(match.group(1))
    return None


def _extract_floor(text: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*階", text)
    if match:
        return _parse_int(match.group(1))
    return None


def _extract_area_labels(text: str) -> tuple[str | None, str | None]:
    normalized = _normalize_text(text)
    city = "Sapporo" if "sapporo" in normalized or "札幌" in text else None
    ward_map = {
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
    }
    ward = next((value for key, value in ward_map.items() if key in text), None)
    ward_match = re.search(r"([A-Za-z]+)\s+(?:ward|ku)", text, re.IGNORECASE)
    if ward_match:
        ward = ward_match.group(1).title()
    return city, ward


def _to_japanese_area_label(filters: dict[str, Any]) -> str | None:
    city = str(filters.get("city") or "")
    if _normalize_text(city) == "sapporo":
        return "札幌"
    return None


def _estimate_listing_confidence(result: WebSearchResult, metadata_fields: dict[str, Any]) -> float:
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
    if metadata_fields.get("building_age") is not None:
        score += 0.03
    return round(min(score, 0.98), 2)
