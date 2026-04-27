from __future__ import annotations

from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data.public_sources import PublicContextProvider
from japan_rental_agent.tools.support import (
    load_city_context_map,
    load_floor_plan_map,
    load_hazard_map,
    load_station_map,
    normalize_text,
    parse_float,
    parse_int,
)


class AreaEnrichmentTool:
    """Joins listing results with hazard, station, city, and floor-plan context."""

    name = "enrichment"

    def __init__(self, config: AppConfig | None = None, public_context_provider: PublicContextProvider | None = None) -> None:
        self.config = config or AppConfig()
        self.public_context_provider = public_context_provider or PublicContextProvider(self.config)

    def execute(self, listings: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        if self.config.search_provider.lower() not in {"local", "mock", "csv"}:
            return self._execute_public_context(listings, context)

        hazard_map = load_hazard_map(self.config)
        station_map = load_station_map(self.config)
        city_context_map = load_city_context_map(self.config)
        floor_plan_map = load_floor_plan_map(self.config)

        enriched: list[dict[str, Any]] = []
        for listing in listings:
            enriched_listing = dict(listing)
            ward_key = normalize_text(str(listing.get("ward", "")))
            station_key = normalize_text(str(listing.get("nearest_station") or listing.get("station") or ""))
            city_key = normalize_text(str(listing.get("city", "")))

            hazard = hazard_map.get(ward_key, {})
            station = station_map.get(station_key, {})
            city_context = city_context_map.get(city_key, {})

            safety_score = parse_float(hazard.get("overall_safety_score"))
            commute_time = parse_int(station.get("avg_commute_to_sapporo_min"))
            walkability = parse_float(station.get("walkability_score"))
            shopping = parse_float(station.get("shopping_convenience_score"))
            winter_reliability = parse_float(station.get("winter_transit_reliability_score"))
            market_support = parse_float(city_context.get("foreign_resident_support_score"))

            enriched_listing.update(
                {
                    "floor_plan_asset": enriched_listing.get("floor_plan_asset")
                    or floor_plan_map.get(str(listing.get("listing_id") or listing.get("id"))),
                    "flood_risk_score": parse_float(hazard.get("flood_risk_score")),
                    "earthquake_risk_score": parse_float(hazard.get("earthquake_risk_score")),
                    "overall_safety_score": safety_score,
                    "commute_time_min": commute_time,
                    "walkability_score": walkability,
                    "shopping_convenience_score": shopping,
                    "winter_transit_reliability_score": winter_reliability,
                    "city_population_estimate": parse_int(city_context.get("population_estimate")),
                    "city_renter_household_ratio": parse_float(city_context.get("renter_household_ratio")),
                    "city_avg_rent_1k_yen": parse_int(city_context.get("avg_rent_1k_yen")),
                    "city_avg_rent_1ldk_yen": parse_int(city_context.get("avg_rent_1ldk_yen")),
                    "foreign_resident_support_score": market_support,
                    "winter_livability_score": parse_float(city_context.get("winter_livability_score")),
                    "market_note": city_context.get("market_note"),
                }
            )
            enriched.append(enriched_listing)

        return {
            "enriched": enriched,
            "context_used": context,
        }

    def _execute_public_context(self, listings: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        enriched: list[dict[str, Any]] = []
        area_context = self.public_context_provider.get_context(context)
        for listing in listings:
            enriched_listing = dict(listing)
            enriched_listing.update(
                {
                    "public_context": area_context,
                    "context_sources": sorted(area_context.get("datasets", {}).keys()),
                    "overall_safety_score": listing.get("overall_safety_score"),
                    "source_url": listing.get("source_url"),
                    "source_name": listing.get("source_name"),
                    "extraction_confidence": listing.get("extraction_confidence"),
                }
            )
            enriched.append(enriched_listing)

        return {
            "enriched": enriched,
            "context_used": {
                **context,
                "context_provider": "public",
                "datasets": ["housing_land_survey", "mlit_real_estate", "hazard_safety", "regional_indicators"],
            },
        }
