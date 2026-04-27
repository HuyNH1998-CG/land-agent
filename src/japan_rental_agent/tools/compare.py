from __future__ import annotations

from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.tools.enrichment import AreaEnrichmentTool
from japan_rental_agent.tools.support import (
    DEFAULT_COMPARE_CRITERIA,
    criterion_label,
    load_floor_plan_map,
    load_listings,
    parse_float,
    parse_int,
    resolve_listing_identifiers,
)


class ComparisonTool:
    """Builds side-by-side pros and cons for selected listings."""

    name = "compare"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def execute(
        self,
        listing_ids: list[str],
        compare_criteria: list[str] | None = None,
        language: str = "vi",
        listing_context: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        context_listings = self._resolve_from_context(listing_ids, listing_context or [])
        try:
            listing_id_set = set(resolve_listing_identifiers(self.config, listing_ids))
        except Exception:
            listing_id_set = set(listing_ids)
        criteria_order = compare_criteria or list(DEFAULT_COMPARE_CRITERIA)
        try:
            listings = load_listings(self.config)
            floor_plan_map = load_floor_plan_map(self.config)
        except Exception:
            listings = []
            floor_plan_map = {}
        context_ids = {item.get("id") for item in context_listings}
        selected = context_listings + [
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
            if row["listing_id"] in listing_id_set and row["listing_id"] not in context_ids
        ]
        enriched = AreaEnrichmentTool(self.config).execute(selected, {})["enriched"]
        if not enriched:
            return {"comparison": [], "criteria_order": criteria_order, "language": language}

        min_rent = min(parse_int(item.get("rent_yen") or item.get("rent")) or 0 for item in enriched)
        max_area = max(parse_float(item.get("area_m2")) or 0.0 for item in enriched)
        min_walk = min(parse_int(item.get("walk_min")) or 0 for item in enriched)
        max_safety = max(parse_float(item.get("overall_safety_score")) or 0.0 for item in enriched)
        min_age = min(parse_int(item.get("building_age")) or 0 for item in enriched)

        return {
            "comparison": [
                self._build_comparison_item(
                    listing=item,
                    min_rent=min_rent,
                    max_area=max_area,
                    min_walk=min_walk,
                    max_safety=max_safety,
                    min_age=min_age,
                    criteria_order=criteria_order,
                    language=language,
                )
                for item in enriched
            ],
            "criteria_order": criteria_order,
            "language": language,
        }

    def _resolve_from_context(self, listing_ids: list[str], listing_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
        requested = set(listing_ids)
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in listing_context:
            item_id = str(item.get("id") or item.get("listing_id") or "")
            if not item_id or item_id not in requested or item_id in seen:
                continue
            listing = dict(item)
            listing["id"] = item_id
            listing["listing_id"] = item_id
            listing["rent_yen"] = parse_int(listing.get("rent_yen") or listing.get("rent"))
            listing["rent"] = parse_int(listing.get("rent_yen") or listing.get("rent"))
            listing["walk_min"] = parse_int(listing.get("walk_min") or listing.get("distance_to_station_min"))
            listing["area_m2"] = parse_float(listing.get("area_m2"))
            listing["building_age"] = parse_int(listing.get("building_age"))
            selected.append(listing)
            seen.add(item_id)
        return selected

    def _build_comparison_item(
        self,
        *,
        listing: dict[str, Any],
        min_rent: int,
        max_area: float,
        min_walk: int,
        max_safety: float,
        min_age: int,
        criteria_order: list[str],
        language: str,
    ) -> dict[str, object]:
        criterion_notes: dict[str, dict[str, str]] = {}
        pros: list[str] = []
        cons: list[str] = []

        rent = parse_int(listing.get("rent_yen") or listing.get("rent")) or 0
        area = parse_float(listing.get("area_m2")) or 0.0
        walk = parse_int(listing.get("walk_min")) or 0
        safety = parse_float(listing.get("overall_safety_score")) or 0.0
        age = parse_int(listing.get("building_age")) or 0

        if rent == min_rent:
            criterion_notes["price"] = {"kind": "pro", "text": self._message(language, "lowest_rent")}
        elif rent >= min_rent + 15000:
            criterion_notes["price"] = {"kind": "con", "text": self._message(language, "expensive")}

        if area == max_area:
            criterion_notes["size"] = {"kind": "pro", "text": self._message(language, "largest_area")}
        elif area < max_area - 10:
            criterion_notes["size"] = {"kind": "con", "text": self._message(language, "smaller_area")}

        if walk == min_walk:
            criterion_notes["location"] = {"kind": "pro", "text": self._message(language, "closest_station")}
        elif walk >= min_walk + 3:
            criterion_notes["location"] = {"kind": "con", "text": self._message(language, "longer_walk")}

        if safety == max_safety:
            criterion_notes["safety"] = {"kind": "pro", "text": self._message(language, "best_safety")}
        elif safety and safety <= max_safety - 0.6:
            criterion_notes["safety"] = {"kind": "con", "text": self._message(language, "weaker_safety")}

        if age == min_age:
            criterion_notes["age"] = {"kind": "pro", "text": self._message(language, "newest_building")}

        if listing.get("pet_allowed") is True:
            criterion_notes["pet_allowed"] = {"kind": "pro", "text": self._message(language, "pets_allowed")}
        if listing.get("foreigner_friendly") is True:
            criterion_notes["foreigner_friendly"] = {"kind": "pro", "text": self._message(language, "foreigner_friendly")}

        ordered_criteria = list(dict.fromkeys(criteria_order + list(criterion_notes.keys())))
        for criterion in ordered_criteria:
            note = criterion_notes.get(criterion)
            if not note:
                continue
            text = self._format_with_criterion(criterion, note["text"], language)
            if note["kind"] == "pro":
                pros.append(text)
            else:
                cons.append(text)

        if not pros:
            pros.append(self._message(language, "balanced_option"))
        if not cons:
            cons.append(self._message(language, "no_major_downside"))

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

    def _format_with_criterion(self, criterion: str, text: str, language: str) -> str:
        label = criterion_label(criterion, language)
        if language == "en":
            return f"{label}: {text}"
        return f"{label}: {text}"

    def _message(self, language: str, key: str) -> str:
        messages = {
            "lowest_rent": {
                "en": "lowest rent among the selected listings",
                "vi": "mức giá thuê thấp nhất trong nhóm đang so sánh",
            },
            "expensive": {
                "en": "notably more expensive than the cheapest option",
                "vi": "giá cao hơn rõ rệt so với lựa chọn rẻ nhất",
            },
            "largest_area": {
                "en": "largest floor area in the comparison",
                "vi": "diện tích rộng nhất trong nhóm so sánh",
            },
            "smaller_area": {
                "en": "smaller floor area than the largest option",
                "vi": "diện tích nhỏ hơn lựa chọn rộng nhất",
            },
            "closest_station": {
                "en": "shortest walk to the station",
                "vi": "đi bộ ra ga ngắn nhất",
            },
            "longer_walk": {
                "en": "longer walk to the station",
                "vi": "thời gian đi bộ ra ga dài hơn",
            },
            "best_safety": {
                "en": "strongest safety profile in the comparison",
                "vi": "mức độ an toàn tốt nhất trong nhóm so sánh",
            },
            "weaker_safety": {
                "en": "weaker safety score than the safest option",
                "vi": "độ an toàn thấp hơn lựa chọn an toàn nhất",
            },
            "newest_building": {
                "en": "newest building among the compared options",
                "vi": "tòa nhà mới hơn so với các lựa chọn còn lại",
            },
            "pets_allowed": {
                "en": "pets are allowed",
                "vi": "cho phép nuôi thú cưng",
            },
            "foreigner_friendly": {
                "en": "foreigner-friendly listing",
                "vi": "phù hợp với người nước ngoài",
            },
            "balanced_option": {
                "en": "balanced overall option",
                "vi": "lựa chọn cân bằng tổng thể",
            },
            "no_major_downside": {
                "en": "no major downside among the selected options",
                "vi": "không có điểm trừ lớn trong nhóm đang so sánh",
            },
        }
        return messages[key].get(language, messages[key]["en"])
