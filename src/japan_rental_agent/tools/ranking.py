from __future__ import annotations

from typing import Any

from japan_rental_agent.tools.support import parse_bool, parse_float, parse_int


class RankingTool:
    """Ranks listings with a simple weighted scoring model."""

    name = "ranking"

    @staticmethod
    def _normalize_higher_better(value: float, min_value: float, max_value: float) -> float:
        if max_value <= min_value:
            return 1.0
        return max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))

    @staticmethod
    def _normalize_lower_better(value: float, min_value: float, max_value: float) -> float:
        if max_value <= min_value:
            return 1.0
        return max(0.0, min(1.0, (max_value - value) / (max_value - min_value)))

    def execute(self, listings: list[dict[str, Any]], preferences: dict[str, Any]) -> dict[str, Any]:
        if not listings:
            return {
                "ranked": [],
                "preferences_used": preferences,
            }

        price_weight = float(preferences.get("weight_price", 0.4))
        location_weight = float(preferences.get("weight_location", 0.3))
        size_weight = float(preferences.get("weight_size", 0.2))
        safety_weight = float(preferences.get("weight_safety", 0.1))
        weight_total = price_weight + location_weight + size_weight + safety_weight or 1.0

        known_rents = [float(value) for item in listings if (value := parse_int(item.get("rent_yen") or item.get("rent"))) is not None]
        known_walks = [
            float(value)
            for item in listings
            if (value := parse_int(item.get("walk_min") or item.get("distance_to_station_min"))) is not None
        ]
        missing_rent_penalty = (max(known_rents) + 10000.0) if known_rents else 999999.0
        missing_walk_penalty = (max(known_walks) + 15.0) if known_walks else 99.0
        rents = [
            float(value) if (value := parse_int(item.get("rent_yen") or item.get("rent"))) is not None else missing_rent_penalty
            for item in listings
        ]
        walks = [
            float(value)
            if (value := parse_int(item.get("walk_min") or item.get("distance_to_station_min"))) is not None
            else missing_walk_penalty
            for item in listings
        ]
        commute_times = [float(parse_int(item.get("commute_time_min")) or 0) for item in listings]
        areas = [float(parse_float(item.get("area_m2")) or 0) for item in listings]
        safety_scores = [float(parse_float(item.get("overall_safety_score")) or 0) for item in listings]
        winter_scores = [float(parse_float(item.get("winter_transit_reliability_score")) or 0) for item in listings]

        ranked_listings: list[dict[str, Any]] = []
        for listing in listings:
            rent_value = parse_int(listing.get("rent_yen") or listing.get("rent"))
            walk_value = parse_int(listing.get("walk_min") or listing.get("distance_to_station_min"))
            rent = float(rent_value) if rent_value is not None else missing_rent_penalty
            walk = float(walk_value) if walk_value is not None else missing_walk_penalty
            commute = float(parse_int(listing.get("commute_time_min")) or 0)
            area = float(parse_float(listing.get("area_m2")) or 0)
            safety = float(parse_float(listing.get("overall_safety_score")) or 0)
            winter = float(parse_float(listing.get("winter_transit_reliability_score")) or 0)
            walkability = float(parse_float(listing.get("walkability_score")) or 0)
            shopping = float(parse_float(listing.get("shopping_convenience_score")) or 0)

            price_score = self._normalize_lower_better(rent, min(rents), max(rents))
            walk_score = self._normalize_lower_better(walk, min(walks), max(walks))
            commute_score = self._normalize_lower_better(commute, min(commute_times), max(commute_times))
            area_score = self._normalize_higher_better(area, min(areas), max(areas))
            safety_score = self._normalize_higher_better(safety, min(safety_scores), max(safety_scores))
            winter_score = self._normalize_higher_better(winter, min(winter_scores), max(winter_scores))
            location_score = min(1.0, (walk_score * 0.45) + (commute_score * 0.35) + ((walkability + shopping) / 20.0 * 0.20))
            safety_blend = min(1.0, (safety_score * 0.7) + (winter_score * 0.3))

            bonus = 0.0
            if parse_bool(listing.get("foreigner_friendly")):
                bonus += 0.015
            if parse_bool(listing.get("pet_allowed")):
                bonus += 0.01

            final_score = (
                price_score * price_weight
                + location_score * location_weight
                + area_score * size_weight
                + safety_blend * safety_weight
            ) / weight_total
            final_score = round(min(1.0, final_score + bonus), 4)

            ranked_listing = dict(listing)
            ranked_listing["score"] = final_score
            ranked_listing["score_breakdown"] = {
                "price": round(price_score, 4),
                "location": round(location_score, 4),
                "size": round(area_score, 4),
                "safety": round(safety_blend, 4),
            }
            ranked_listings.append(ranked_listing)

        ranked_listings.sort(
            key=lambda item: (
                -(parse_float(item.get("score")) or 0.0),
                parse_int(item.get("rent_yen") or item.get("rent")) or 0,
                parse_int(item.get("walk_min") or item.get("distance_to_station_min")) or 99,
            )
        )
        return {
            "ranked": ranked_listings,
            "preferences_used": preferences,
        }
