from __future__ import annotations

from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.tools.enrichment import AreaEnrichmentTool
from japan_rental_agent.tools.support import (
    DEFAULT_COMPARE_CRITERIA,
    criterion_label,
    derive_construction_year,
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
                "management_fee": parse_int(row["management_fee"]),
                "walk_min": parse_int(row["walk_min"]),
                "area_m2": parse_float(row["area_m2"]),
                "building_age": parse_int(row["building_age"]),
                "construction_year": derive_construction_year(row["building_age"]),
                "image_urls": [],
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
        newest_year = max(parse_int(item.get("construction_year")) or 0 for item in enriched)

        return {
            "comparison": [
                self._build_comparison_item(
                    listing=item,
                    min_rent=min_rent,
                    max_area=max_area,
                    min_walk=min_walk,
                    max_safety=max_safety,
                    newest_year=newest_year,
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
            listing["management_fee"] = parse_int(listing.get("management_fee"))
            listing["walk_min"] = parse_int(listing.get("walk_min") or listing.get("distance_to_station_min"))
            listing["area_m2"] = parse_float(listing.get("area_m2"))
            listing["building_age"] = parse_int(listing.get("building_age"))
            listing["construction_year"] = parse_int(listing.get("construction_year")) or derive_construction_year(
                listing.get("building_age")
            )
            listing["image_urls"] = list(listing.get("image_urls") or [])
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
        newest_year: int,
        criteria_order: list[str],
        language: str,
    ) -> dict[str, object]:
        criterion_notes: dict[str, dict[str, str]] = {}
        pros: list[str] = []
        cons: list[str] = []

        rent = parse_int(listing.get("rent_yen") or listing.get("rent")) or 0
        management_fee = parse_int(listing.get("management_fee"))
        area = parse_float(listing.get("area_m2")) or 0.0
        walk = parse_int(listing.get("walk_min")) or 0
        safety = parse_float(listing.get("overall_safety_score")) or 0.0
        construction_year = parse_int(listing.get("construction_year")) or 0

        if rent == min_rent:
            criterion_notes["price"] = {
                "kind": "pro",
                "text": self._message(language, "lowest_rent", rent=rent),
            }
        elif rent >= min_rent + 15000:
            criterion_notes["price"] = {
                "kind": "con",
                "text": self._message(language, "expensive", rent=rent, baseline=min_rent),
            }

        if area == max_area:
            criterion_notes["size"] = {
                "kind": "pro",
                "text": self._message(language, "largest_area", area=area),
            }
        elif area < max_area - 10:
            criterion_notes["size"] = {
                "kind": "con",
                "text": self._message(language, "smaller_area", area=area, baseline=max_area),
            }

        if walk == min_walk:
            criterion_notes["location"] = {
                "kind": "pro",
                "text": self._message(language, "closest_station", walk=walk),
            }
        elif walk >= min_walk + 3:
            criterion_notes["location"] = {
                "kind": "con",
                "text": self._message(language, "longer_walk", walk=walk, baseline=min_walk),
            }

        if safety == max_safety:
            criterion_notes["safety"] = {
                "kind": "pro",
                "text": self._message(language, "best_safety", safety=safety),
            }
        elif safety and safety <= max_safety - 0.6:
            criterion_notes["safety"] = {
                "kind": "con",
                "text": self._message(language, "weaker_safety", safety=safety, baseline=max_safety),
            }

        if construction_year == newest_year and construction_year:
            criterion_notes["age"] = {
                "kind": "pro",
                "text": self._message(language, "newest_building", construction_year=construction_year),
            }

        if listing.get("pet_allowed") is True:
            criterion_notes["pet_allowed"] = {"kind": "pro", "text": self._message(language, "pets_allowed")}
        if listing.get("foreigner_friendly") is True:
            criterion_notes["foreigner_friendly"] = {
                "kind": "pro",
                "text": self._message(language, "foreigner_friendly"),
            }

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
            "management_fee": management_fee,
            "area_m2": area,
            "walk_min": walk,
            "overall_safety_score": safety,
            "construction_year": construction_year or None,
            "floor_plan_asset": listing.get("floor_plan_asset"),
            "image_urls": list(listing.get("image_urls") or []),
        }

    def _format_with_criterion(self, criterion: str, text: str, language: str) -> str:
        return f"{criterion_label(criterion, language)}: {text}"

    def _message(self, language: str, key: str, **values: Any) -> str:
        if language == "vi":
            return self._message_vi(key, **values)
        return self._message_en(key, **values)

    def _message_en(self, key: str, **values: Any) -> str:
        if key == "lowest_rent":
            return f"{values['rent']:,} JPY/month, the cheapest option"
        if key == "expensive":
            return f"{values['rent']:,} JPY/month, notably above the cheapest {values['baseline']:,} JPY"
        if key == "largest_area":
            return f"{values['area']:.2f} m2, the largest floor area"
        if key == "smaller_area":
            return f"{values['area']:.2f} m2, smaller than the widest {values['baseline']:.2f} m2 option"
        if key == "closest_station":
            return f"{values['walk']} min walk to the station, shortest in this group"
        if key == "longer_walk":
            return f"{values['walk']} min walk, longer than the best {values['baseline']} min option"
        if key == "best_safety":
            return f"safety score {values['safety']:.2f}, strongest in this group"
        if key == "weaker_safety":
            return f"safety score {values['safety']:.2f}, below the best {values['baseline']:.2f}"
        if key == "newest_building":
            return f"built in {values['construction_year']}, the newest building here"
        if key == "pets_allowed":
            return "pets allowed"
        if key == "foreigner_friendly":
            return "foreigner-friendly listing"
        if key == "balanced_option":
            return "balanced overall option"
        if key == "no_major_downside":
            return "no major downside among the selected options"
        raise KeyError(key)

    def _message_vi(self, key: str, **values: Any) -> str:
        if key == "lowest_rent":
            return f"{values['rent']:,} JPY/tháng, mức giá thuê thấp nhất"
        if key == "expensive":
            return f"{values['rent']:,} JPY/tháng, cao hơn rõ so với mức thấp nhất {values['baseline']:,} JPY"
        if key == "largest_area":
            return f"{values['area']:.2f} m2, diện tích rộng nhất"
        if key == "smaller_area":
            return f"{values['area']:.2f} m2, nhỏ hơn căn rộng nhất {values['baseline']:.2f} m2"
        if key == "closest_station":
            return f"đi bộ {values['walk']} phút ra ga, ngắn nhất nhóm"
        if key == "longer_walk":
            return f"đi bộ {values['walk']} phút, lâu hơn mức tốt nhất {values['baseline']} phút"
        if key == "best_safety":
            return f"điểm an toàn {values['safety']:.2f}, tốt nhất nhóm"
        if key == "weaker_safety":
            return f"điểm an toàn {values['safety']:.2f}, thấp hơn mức cao nhất {values['baseline']:.2f}"
        if key == "newest_building":
            return f"khởi xây năm {values['construction_year']}, mới nhất trong nhóm"
        if key == "pets_allowed":
            return "cho phép nuôi thú cưng"
        if key == "foreigner_friendly":
            return "phù hợp cho người nước ngoài"
        if key == "balanced_option":
            return "lựa chọn cân bằng tổng thể"
        if key == "no_major_downside":
            return "không có điểm trừ lớn trong nhóm đã chọn"
        raise KeyError(key)
