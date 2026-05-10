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
        "construction_year": item.get("construction_year"),
        "floor": item.get("floor"),
        "nearest_station": item.get("nearest_station") or item.get("station"),
        "distance_to_station_min": item.get("distance_to_station_min") or item.get("walk_min"),
        "commute_time_min": item.get("commute_time_min"),
        "flood_risk_score": item.get("flood_risk_score"),
        "earthquake_risk_score": item.get("earthquake_risk_score"),
        "overall_safety_score": item.get("overall_safety_score"),
        "walkability_score": item.get("walkability_score"),
        "shopping_convenience_score": item.get("shopping_convenience_score"),
        "winter_transit_reliability_score": item.get("winter_transit_reliability_score"),
        "city_population_estimate": item.get("city_population_estimate"),
        "city_renter_household_ratio": item.get("city_renter_household_ratio"),
        "city_avg_rent_1k_yen": item.get("city_avg_rent_1k_yen"),
        "city_avg_rent_1ldk_yen": item.get("city_avg_rent_1ldk_yen"),
        "foreign_resident_support_score": item.get("foreign_resident_support_score"),
        "winter_livability_score": item.get("winter_livability_score"),
        "market_note": item.get("market_note"),
        "foreigner_friendly": item.get("foreigner_friendly"),
        "pet_allowed": item.get("pet_allowed"),
        "lat": item.get("lat"),
        "lng": item.get("lng"),
        "floor_plan_asset": item.get("floor_plan_asset"),
        "nearby_facilities": item.get("nearby_facilities") or [],
        "image_urls": item.get("image_urls") or [],
        "source_url": item.get("source_url"),
        "source_name": item.get("source_name"),
        "source_snippet": item.get("source_snippet"),
        "source_kind": item.get("source_kind"),
        "source_validated": item.get("source_validated"),
        "source_validation_reason": item.get("source_validation_reason"),
        "metadata_fields_found": item.get("metadata_fields_found") or [],
        "metadata_error": item.get("metadata_error"),
        "extraction_confidence": item.get("extraction_confidence"),
        "context_sources": item.get("context_sources") or [],
        "score": item.get("score"),
        "score_breakdown": item.get("score_breakdown"),
    }
    return Listing.model_validate(normalized).model_dump(mode="json")


def normalize_listings(items: list[dict[str, Any]], top_k: int | None = None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    selected_items = items if top_k is None else items[:top_k]
    for index, item in enumerate(selected_items, start=1):
        normalized.append(normalize_listing_payload(item, index=index))
    return normalized
