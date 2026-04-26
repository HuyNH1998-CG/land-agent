from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data import ChromaVectorStore, DatasetRegistry


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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
