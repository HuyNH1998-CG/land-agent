from __future__ import annotations

from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.tools.enrichment import AreaEnrichmentTool
from japan_rental_agent.tools.support import load_floor_plan_map, load_listings, parse_float, parse_int


class ComparisonTool:
    """Builds side-by-side pros and cons for selected listings."""

    name = "compare"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def execute(self, listing_ids: list[str]) -> dict[str, list[dict[str, object]]]:
        listing_id_set = set(listing_ids)
        listings = load_listings(self.config)
        floor_plan_map = load_floor_plan_map(self.config)
        selected = [
            {
                **row,
                "floor_plan_asset": floor_plan_map.get(row["listing_id"]),
                "listing_id": row["listing_id"],
                "id": row["listing_id"],
                "station": row["nearest_station"],
                "rent": parse_int(row["rent_yen"]),
                "rent_yen": parse_int(row["rent_yen"]),
                "walk_min": parse_int(row["walk_min"]),
                "area_m2": parse_float(row["area_m2"]),
                "building_age": parse_int(row["building_age"]),
            }
            for row in listings
            if row["listing_id"] in listing_id_set
        ]
        enriched = AreaEnrichmentTool(self.config).execute(selected, {})["enriched"]
        if not enriched:
            return {"comparison": []}

        min_rent = min(parse_int(item.get("rent_yen") or item.get("rent")) or 0 for item in enriched)
        max_area = max(parse_float(item.get("area_m2")) or 0.0 for item in enriched)
        min_walk = min(parse_int(item.get("walk_min")) or 0 for item in enriched)
        max_safety = max(parse_float(item.get("overall_safety_score")) or 0.0 for item in enriched)

        return {
            "comparison": [
                self._build_comparison_item(
                    listing=item,
                    min_rent=min_rent,
                    max_area=max_area,
                    min_walk=min_walk,
                    max_safety=max_safety,
                )
                for item in enriched
            ]
        }

    def _build_comparison_item(
        self,
        *,
        listing: dict[str, Any],
        min_rent: int,
        max_area: float,
        min_walk: int,
        max_safety: float,
    ) -> dict[str, object]:
        pros: list[str] = []
        cons: list[str] = []

        rent = parse_int(listing.get("rent_yen") or listing.get("rent")) or 0
        area = parse_float(listing.get("area_m2")) or 0.0
        walk = parse_int(listing.get("walk_min")) or 0
        safety = parse_float(listing.get("overall_safety_score")) or 0.0

        if rent == min_rent:
            pros.append("lowest rent among selected listings")
        elif rent >= min_rent + 15000:
            cons.append("notably more expensive than the cheapest option")

        if area == max_area:
            pros.append("largest floor area in the comparison")
        elif area < max_area - 10:
            cons.append("smaller floor area than the largest option")

        if walk == min_walk:
            pros.append("closest walk to the station")
        elif walk >= min_walk + 3:
            cons.append("longer walk to the station")

        if safety == max_safety:
            pros.append("strongest safety profile in the comparison")
        elif safety and safety <= max_safety - 0.6:
            cons.append("weaker safety score than the safest option")

        if listing.get("foreigner_friendly") is True:
            pros.append("foreigner-friendly listing")
        if listing.get("pet_allowed") is True:
            pros.append("pets are allowed")
        if not pros:
            pros.append("balanced overall option")
        if not cons:
            cons.append("no major downside among the selected options")

        return {
            "id": listing.get("listing_id") or listing.get("id"),
            "title": listing.get("title"),
            "pros": pros,
            "cons": cons,
            "rent_yen": rent,
            "area_m2": area,
            "walk_min": walk,
            "overall_safety_score": safety,
            "floor_plan_asset": listing.get("floor_plan_asset"),
        }
