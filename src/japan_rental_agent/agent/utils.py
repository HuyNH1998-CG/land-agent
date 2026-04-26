from __future__ import annotations

from typing import Any

from japan_rental_agent.domain import Listing


def merge_constraints(*sources: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in sources:
        for key, value in source.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, list) and not value:
                continue
            merged[key] = value
    return merged


def normalize_listing_payload(item: dict[str, Any], index: int) -> dict[str, Any]:
    normalized = {
        "id": item.get("id") or item.get("listing_id") or f"listing_{index}",
        "title": item.get("title") or item.get("name") or f"Listing {index}",
        "city": item.get("city"),
        "ward": item.get("ward"),
        "rent": item.get("rent") or item.get("rent_yen"),
        "management_fee": item.get("management_fee"),
        "layout": item.get("layout"),
        "area_m2": item.get("area_m2"),
        "building_age": item.get("building_age"),
        "floor": item.get("floor"),
        "nearest_station": item.get("nearest_station") or item.get("station"),
        "distance_to_station_min": item.get("distance_to_station_min") or item.get("walk_min"),
        "commute_time_min": item.get("commute_time_min"),
        "foreigner_friendly": item.get("foreigner_friendly"),
        "pet_allowed": item.get("pet_allowed"),
        "lat": item.get("lat"),
        "lng": item.get("lng"),
        "floor_plan_asset": item.get("floor_plan_asset"),
        "score": item.get("score"),
        "score_breakdown": item.get("score_breakdown"),
    }
    return Listing.model_validate(normalized).model_dump(mode="json")


def normalize_listings(items: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items[:top_k], start=1):
        normalized.append(normalize_listing_payload(item, index=index))
    return normalized
