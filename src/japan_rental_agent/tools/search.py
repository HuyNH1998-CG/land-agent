from __future__ import annotations

from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data.seed import LISTING_COLLECTION
from japan_rental_agent.tools.support import (
    build_listing_document,
    create_vector_store,
    listing_capacity,
    load_floor_plan_map,
    load_listings,
    normalize_text,
    parse_bool,
    parse_float,
    parse_int,
)


class ListingSearchTool:
    """Searches local mock listings with structured filters and Chroma reranking."""

    name = "search"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def _apply_structured_filters(
        self,
        listing: dict[str, str],
        filters: dict[str, Any],
    ) -> bool:
        city = filters.get("city")
        if city and normalize_text(str(city)) != normalize_text(listing["city"]):
            return False

        prefecture = filters.get("prefecture")
        if prefecture and normalize_text(str(prefecture)) != normalize_text(listing["prefecture"]):
            return False

        ward = filters.get("ward")
        if ward and normalize_text(str(ward)) != normalize_text(listing["ward"]):
            return False

        station = filters.get("nearest_station") or filters.get("station")
        if station and normalize_text(str(station)) != normalize_text(listing["nearest_station"]):
            return False

        max_rent = parse_int(filters.get("max_rent"))
        if max_rent is not None and parse_int(listing["rent_yen"]) > max_rent:
            return False

        min_area = parse_float(filters.get("min_area"))
        if min_area is not None and parse_float(listing["area_m2"]) < min_area:
            return False

        if parse_bool(filters.get("near_station")) and parse_int(listing["walk_min"]) > 10:
            return False

        preferred_layout = filters.get("preferred_layout")
        if preferred_layout and str(preferred_layout).upper() != listing["layout"].upper():
            return False

        occupancy = parse_int(filters.get("occupancy"))
        if occupancy is not None and listing_capacity(listing["layout"]) < occupancy:
            return False

        pet_allowed = parse_bool(filters.get("pet_allowed"))
        if pet_allowed is True and parse_bool(listing["pet_allowed"]) is not True:
            return False

        foreigner_friendly = parse_bool(filters.get("foreigner_friendly"))
        if foreigner_friendly is True and parse_bool(listing["foreigner_friendly"]) is not True:
            return False

        return True

    def _build_semantic_query(self, filters: dict[str, Any]) -> str:
        parts: list[str] = []
        for key in ["query_text", "city", "ward", "nearest_station", "preferred_layout"]:
            value = filters.get(key)
            if value:
                parts.append(str(value))
        if filters.get("max_rent"):
            parts.append(f"budget {filters['max_rent']} yen")
        if filters.get("min_area"):
            parts.append(f"minimum area {filters['min_area']} sqm")
        if parse_bool(filters.get("pet_allowed")):
            parts.append("pet allowed")
        if parse_bool(filters.get("foreigner_friendly")):
            parts.append("foreigner friendly")
        if parse_bool(filters.get("near_station")):
            parts.append("near station")
        parts.extend(filters.get("notes", []))
        return ". ".join(parts).strip()

    def _semantic_order(self, filters: dict[str, Any], candidate_ids: set[str]) -> dict[str, float]:
        query_text = self._build_semantic_query(filters)
        if not query_text:
            return {}

        try:
            store = create_vector_store(self.config)
            results = store.similarity_search(
                collection_name=LISTING_COLLECTION,
                query_text=query_text,
                n_results=min(max(len(candidate_ids), 12), 80),
            )
        except Exception:
            return {}

        scored: dict[str, float] = {}
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for listing_id, distance in zip(ids, distances):
            if listing_id in candidate_ids:
                scored[listing_id] = float(distance)
        return scored

    def _to_result_payload(self, row: dict[str, str], floor_plan_map: dict[str, str]) -> dict[str, Any]:
        return {
            "listing_id": row["listing_id"],
            "id": row["listing_id"],
            "title": row["title"],
            "prefecture": row["prefecture"],
            "city": row["city"],
            "ward": row["ward"],
            "station": row["nearest_station"],
            "nearest_station": row["nearest_station"],
            "walk_min": parse_int(row["walk_min"]),
            "distance_to_station_min": parse_int(row["walk_min"]),
            "rent_yen": parse_int(row["rent_yen"]),
            "rent": parse_int(row["rent_yen"]),
            "management_fee": parse_int(row["management_fee"]),
            "deposit": parse_int(row["deposit"]),
            "key_money": parse_int(row["key_money"]),
            "layout": row["layout"],
            "area_m2": parse_float(row["area_m2"]),
            "building_age": parse_int(row["building_age"]),
            "floor": parse_int(row["floor"]),
            "pet_allowed": parse_bool(row["pet_allowed"]),
            "foreigner_friendly": parse_bool(row["foreigner_friendly"]),
            "available_from": row["available_from"],
            "lat": parse_float(row["lat"]),
            "lng": parse_float(row["lng"]),
            "floor_plan_asset": floor_plan_map.get(row["listing_id"]),
            "document": build_listing_document(row),
        }

    def execute(self, filters: dict[str, Any]) -> dict[str, Any]:
        listings = load_listings(self.config)
        floor_plan_map = load_floor_plan_map(self.config)
        filtered_rows = [row for row in listings if self._apply_structured_filters(row, filters)]
        candidate_ids = {row["listing_id"] for row in filtered_rows}
        semantic_scores = self._semantic_order(filters, candidate_ids)

        filtered_rows.sort(
            key=lambda row: (
                semantic_scores.get(row["listing_id"], 9999.0),
                parse_int(row["rent_yen"]) or 0,
                parse_int(row["walk_min"]) or 99,
                -(parse_float(row["area_m2"]) or 0.0),
            )
        )
        results = [self._to_result_payload(row, floor_plan_map) for row in filtered_rows]

        return {
            "results": results,
            "total": len(results),
            "filters_used": filters,
        }
