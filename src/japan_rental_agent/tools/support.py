from __future__ import annotations

import csv
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data import ChromaVectorStore, DatasetRegistry

COMPARE_CRITERIA_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("price", ("rent", "price", "cost", "budget", "gia", "thue", "giathue")),
    ("size", ("area", "size", "space", "sqm", "m2", "dien tich")),
    ("location", ("location", "station", "distance", "walk", "vi tri", "ga")),
    ("safety", ("safety", "hazard", "safe", "an toan")),
    ("age", ("age", "building age", "newer", "older", "tuoi toa nha")),
    ("pet_allowed", ("pet", "pets", "dog", "cat", "thu cung", "pet friendly")),
    ("foreigner_friendly", ("foreigner", "foreigners", "international", "nguoi nuoc ngoai")),
]

CRITERION_LABELS: dict[str, dict[str, str]] = {
    "price": {"en": "price", "vi": "giá thuê"},
    "size": {"en": "size", "vi": "diện tích"},
    "location": {"en": "location", "vi": "vị trí"},
    "safety": {"en": "safety", "vi": "độ an toàn"},
    "age": {"en": "building age", "vi": "tuổi tòa nhà"},
    "pet_allowed": {"en": "pet policy", "vi": "chính sách thú cưng"},
    "foreigner_friendly": {"en": "foreigner-friendly policy", "vi": "mức độ phù hợp cho người nước ngoài"},
}

DEFAULT_COMPARE_CRITERIA = ["price", "size", "location", "safety"]


def normalize_phrase(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().replace("\u0111", "d"))
    ascii_like = "".join(character for character in normalized if not unicodedata.combining(character))
    compact = re.sub(r"[^a-z0-9]+", " ", ascii_like)
    return re.sub(r"\s+", " ", compact).strip()


def normalize_text(value: str) -> str:
    return normalize_phrase(value).replace(" ", "")


def tokenize_text(value: str) -> list[str]:
    ascii_value = normalize_phrase(value)
    return [token for token in re.findall(r"[a-z0-9]+", ascii_value) if len(token) >= 2]


def detect_language(value: str) -> str:
    normalized = normalize_text(value)
    if any(token in normalized for token in ["sosanh", "giathue", "dientich", "vitri", "antoan", "canho"]):
        return "vi"
    return "en"


def extract_compare_criteria(value: str) -> list[str]:
    normalized = normalize_phrase(value)
    matches: list[tuple[int, str]] = []
    seen: set[str] = set()

    for criterion, keywords in COMPARE_CRITERIA_KEYWORDS:
        positions: list[int] = []
        for keyword in keywords:
            keyword_norm = normalize_phrase(keyword)
            if not keyword_norm:
                continue
            if criterion == "size" and keyword_norm == "area" and "same area" in normalized:
                continue
            match = re.search(rf"(?<![a-z0-9]){re.escape(keyword_norm)}(?![a-z0-9])", normalized)
            if match:
                positions.append(match.start())
        if positions and criterion not in seen:
            matches.append((min(positions), criterion))
            seen.add(criterion)

    matches.sort(key=lambda item: item[0])
    return [criterion for _, criterion in matches]


def criterion_label(criterion: str, language: str) -> str:
    labels = CRITERION_LABELS.get(criterion)
    if not labels:
        return criterion
    return labels.get(language, labels["en"])


def resolve_recent_listing_candidates(
    *,
    message: str,
    recent_listings: list[dict[str, Any]],
    parsed_constraints: dict[str, Any],
    max_results: int = 4,
) -> list[str]:
    if len(recent_listings) < 2:
        return []

    normalized_message = normalize_text(message)
    area_reference = any(
        token in normalized_message
        for token in [
            "samearea",
            "sameward",
            "samestation",
            "sameplace",
            "cungkhuvuc",
            "cungkhu",
            "cungphuong",
            "cungga",
            "cungvitri",
        ]
    )
    list_reference = any(
        token in normalized_message
        for token in [
            "listedabove",
            "listabove",
            "abovelisted",
            "ketquavualistra",
            "vualistra",
            "vualietke",
            "caccanvualistra",
            "cacnhavualistra",
        ]
    )

    if parsed_constraints.get("ward"):
        matches = [
            item for item in recent_listings
            if normalize_text(str(item.get("ward", ""))) == normalize_text(str(parsed_constraints["ward"]))
        ]
        if len(matches) >= 2:
            return [str(item["id"]) for item in matches[:max_results]]

    station_value = parsed_constraints.get("nearest_station") or parsed_constraints.get("station")
    if station_value:
        matches = [
            item for item in recent_listings
            if normalize_text(str(item.get("nearest_station") or item.get("station") or "")) == normalize_text(str(station_value))
        ]
        if len(matches) >= 2:
            return [str(item["id"]) for item in matches[:max_results]]

    if area_reference:
        ward_candidates = _dominant_group(recent_listings, key="ward")
        if len(ward_candidates) >= 2:
            return ward_candidates[:max_results]
        station_candidates = _dominant_group(recent_listings, key="nearest_station")
        if len(station_candidates) >= 2:
            return station_candidates[:max_results]
        return []

    if list_reference and 2 <= len(recent_listings) <= max_results:
        return [str(item["id"]) for item in recent_listings]

    return []


def _dominant_group(items: list[dict[str, Any]], *, key: str) -> list[str]:
    grouped: dict[str, list[str]] = {}
    for item in items:
        if key == "nearest_station":
            raw_value = item.get("nearest_station") or item.get("station")
        else:
            raw_value = item.get(key)
        normalized_value = normalize_text(str(raw_value or ""))
        if not normalized_value:
            continue
        grouped.setdefault(normalized_value, []).append(str(item["id"]))

    if not grouped:
        return []

    sorted_groups = sorted(grouped.values(), key=lambda ids: (-len(ids), ids))
    top_group = sorted_groups[0]
    if len(top_group) < 2:
        return []
    if len(sorted_groups) > 1 and len(sorted_groups[1]) == len(top_group):
        return []
    return top_group


def parse_bool(value: str | bool | None) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    lowered = value.strip().lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    return None


def parse_int(value: str | int | float | None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    return int(float(value))


def parse_float(value: str | int | float | None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    return float(value)


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        cleaned[key] = value
    return cleaned


def listing_capacity(layout: str | None) -> int:
    if not layout:
        return 1
    mapping = {
        "1R": 1,
        "1K": 1,
        "1DK": 2,
        "1LDK": 2,
        "2LDK": 4,
        "3LDK": 5,
    }
    return mapping.get(layout.upper(), 2)


@lru_cache(maxsize=8)
def _load_csv(path_str: str) -> list[dict[str, str]]:
    path = Path(path_str)
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@lru_cache(maxsize=8)
def _load_floor_plans(path_str: str) -> dict[str, str]:
    rows = _load_csv(path_str)
    return {row["listing_id"]: row["floor_plan_asset"] for row in rows}


def load_listings(config: AppConfig) -> list[dict[str, str]]:
    registry = DatasetRegistry(config.data_dir)
    return list(_load_csv(str(registry.listings_path.resolve())))


def load_hazard_map(config: AppConfig) -> dict[str, dict[str, str]]:
    registry = DatasetRegistry(config.data_dir)
    rows = _load_csv(str(registry.hazard_path.resolve()))
    return {normalize_text(row["ward"]): row for row in rows}


def load_station_map(config: AppConfig) -> dict[str, dict[str, str]]:
    registry = DatasetRegistry(config.data_dir)
    rows = _load_csv(str(registry.station_context_path.resolve()))
    return {normalize_text(row["station"]): row for row in rows}


def load_city_context_map(config: AppConfig) -> dict[str, dict[str, str]]:
    registry = DatasetRegistry(config.data_dir)
    rows = _load_csv(str(registry.housing_context_path.resolve()))
    return {normalize_text(row["city"]): row for row in rows}


def load_floor_plan_map(config: AppConfig) -> dict[str, str]:
    path = (config.data_dir / "floor_plan_reference.csv").resolve()
    return _load_floor_plans(str(path))


def load_known_locations(config: AppConfig) -> dict[str, set[str]]:
    listings = load_listings(config)
    stations = load_station_map(config)
    return {
        "cities": {row["city"] for row in listings},
        "wards": {row["ward"] for row in listings},
        "stations": {station["station"] for station in stations.values()},
    }


def resolve_listing_identifiers(config: AppConfig, identifiers: list[str], *, limit: int | None = None) -> list[str]:
    listings = load_listings(config)
    listing_id_map = {row["listing_id"].lower(): row["listing_id"] for row in listings}
    title_index = [
        {
            "listing_id": row["listing_id"],
            "title_norm": normalize_text(row["title"]),
            "title_tokens": set(tokenize_text(row["title"])),
        }
        for row in listings
    ]

    resolved: list[str] = []
    seen: set[str] = set()

    for identifier in identifiers:
        raw_identifier = identifier.strip()
        if not raw_identifier:
            continue

        direct_match = listing_id_map.get(raw_identifier.lower())
        if direct_match and direct_match not in seen:
            resolved.append(direct_match)
            seen.add(direct_match)
            if limit is not None and len(resolved) >= limit:
                break
            continue

        identifier_norm = normalize_text(raw_identifier)
        if not identifier_norm:
            continue

        exact_matches = sorted(
            entry["listing_id"]
            for entry in title_index
            if entry["title_norm"] == identifier_norm
        )
        if exact_matches:
            match = exact_matches[0]
            if match not in seen:
                resolved.append(match)
                seen.add(match)
                if limit is not None and len(resolved) >= limit:
                    return resolved
            continue

        substring_matches = sorted(
            entry["listing_id"]
            for entry in title_index
            if identifier_norm in entry["title_norm"]
        )
        if substring_matches:
            match = substring_matches[0]
            if match not in seen:
                resolved.append(match)
                seen.add(match)
                if limit is not None and len(resolved) >= limit:
                    return resolved
            continue

        identifier_tokens = set(tokenize_text(raw_identifier))
        if not identifier_tokens:
            continue

        scored_matches: list[tuple[int, float, str]] = []
        for entry in title_index:
            overlap = len(identifier_tokens & entry["title_tokens"])
            if overlap == 0:
                continue
            coverage = overlap / max(1, len(identifier_tokens))
            if overlap >= 2 or coverage >= 0.75:
                scored_matches.append((overlap, coverage, entry["listing_id"]))

        if not scored_matches:
            continue

        scored_matches.sort(key=lambda item: (-item[0], -item[1], item[2]))
        best_match = scored_matches[0][2]
        if best_match not in seen:
            resolved.append(best_match)
            seen.add(best_match)
            if limit is not None and len(resolved) >= limit:
                return resolved

    return resolved


def build_listing_document(listing: dict[str, Any]) -> str:
    parts = [
        f"{listing.get('title', 'Rental listing')}",
        f"{listing.get('layout', 'unknown layout')}",
        f"{listing.get('city', '')} {listing.get('ward', '')}",
        f"rent {listing.get('rent_yen') or listing.get('rent') or 'unknown'} yen",
        f"walk {listing.get('walk_min') or listing.get('distance_to_station_min') or 'unknown'} minutes",
        f"station {listing.get('nearest_station') or listing.get('station') or 'unknown'}",
        f"area {listing.get('area_m2') or 'unknown'} sqm",
    ]
    return ". ".join(part for part in parts if part and part != ".")


def create_vector_store(config: AppConfig) -> ChromaVectorStore:
    return ChromaVectorStore(config)


def to_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=True, indent=2).encode("utf-8")
