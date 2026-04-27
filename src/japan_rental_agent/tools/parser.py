from __future__ import annotations

import re
from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.tools.support import (
    detect_language,
    extract_compare_criteria,
    load_known_locations,
    normalize_phrase,
    normalize_text,
    resolve_listing_identifiers,
    tokenize_text,
)


class QueryParserTool:
    """Heuristic parser for rental-search constraints."""

    name = "parser"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def execute(self, message: str) -> dict[str, Any]:
        text = message.strip()
        lowered = text.lower()
        normalized_text = normalize_text(text)
        intent_hint = "search"
        selected_listing_ids = sorted(set(match.lower() for match in re.findall(r"\bsap_\d{3}\b", lowered)))
        output_format: str | None = None
        compare_targets: list[str] = []
        compare_criteria = extract_compare_criteria(text)
        response_language = detect_language(text)

        if "compare" in lowered or "sosanh" in normalized_text:
            intent_hint = "compare"
        elif "export" in lowered or "download" in lowered:
            intent_hint = "export"

        if intent_hint == "compare" and not selected_listing_ids:
            compare_targets = self._extract_compare_segments(text)
            resolvable_targets = [target for target in compare_targets if self._looks_like_listing_reference(target)]
            if resolvable_targets:
                selected_listing_ids = resolve_listing_identifiers(self.config, resolvable_targets, limit=4)
        elif intent_hint == "compare":
            compare_targets = self._extract_compare_segments(text)

        if " csv" in f" {lowered}" or lowered.endswith("csv"):
            output_format = "csv"
        elif " json" in f" {lowered}" or lowered.endswith("json"):
            output_format = "json"
        elif " pdf" in f" {lowered}" or lowered.endswith("pdf"):
            output_format = "pdf"

        constraints: dict[str, Any] = {
            "query_text": text,
            "notes": [],
        }
        known_locations = load_known_locations(self.config)
        normalized_message = normalize_text(text)

        for city in known_locations["cities"]:
            if normalize_text(city) in normalized_message:
                constraints["city"] = city
                break

        for ward in sorted(known_locations["wards"], key=len, reverse=True):
            if normalize_text(ward) in normalized_message:
                constraints["ward"] = ward
                constraints.setdefault("city", "Sapporo")
                break

        city_norm = normalize_text(str(constraints.get("city", "")))
        for station in sorted(known_locations["stations"], key=len, reverse=True):
            station_norm = normalize_text(station)
            if station_norm == city_norm:
                if f"{station.lower()} station" not in lowered:
                    continue
            if station_norm in normalized_message:
                constraints["nearest_station"] = station
                constraints.setdefault("city", "Sapporo")
                break

        if "sapporo" in lowered:
            constraints["city"] = "Sapporo"
            constraints.setdefault("prefecture", "Hokkaido")
        if "hokkaido" in lowered:
            constraints["prefecture"] = "Hokkaido"

        if "near station" in lowered or ("station" in lowered and any(token in lowered for token in ["near", "close", "walk", "ga", "eki"])):
            constraints["near_station"] = True

        if "pet" in lowered or "dog" in lowered or "cat" in lowered:
            constraints["pet_allowed"] = True
        if "foreigner" in lowered or "international" in lowered:
            constraints["foreigner_friendly"] = True

        budget_patterns = [
            r"under\s+(\d{4,6})\s*(?:yen|jpy)?",
            r"below\s+(\d{4,6})\s*(?:yen|jpy)?",
            r"max(?:imum)?\s+(\d{4,6})\s*(?:yen|jpy)?",
            r"(\d{4,6})\s*(?:yen|jpy)",
        ]
        for pattern in budget_patterns:
            match = re.search(pattern, lowered)
            if match:
                constraints["max_rent"] = int(match.group(1))
                break

        man_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:man)", lowered)
        if man_match:
            constraints["max_rent"] = int(float(man_match.group(1)) * 10000)
        japanese_man_match = re.search(r"(\d+(?:\.\d+)?)\s*万(?:円)?", text)
        if japanese_man_match:
            constraints["max_rent"] = int(float(japanese_man_match.group(1)) * 10000)

        area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m2|sqm|square meters)", lowered)
        if area_match:
            constraints["min_area"] = float(area_match.group(1))

        layout_match = re.search(r"\b([1234]ldk|[1234]dk|[1234]k|1r)\b", lowered)
        if layout_match:
            constraints["preferred_layout"] = layout_match.group(1).upper()

        occupancy_match = re.search(r"(?:for|with)\s+(\d+)\s*(?:people|persons|person)", lowered)
        if occupancy_match:
            constraints["occupancy"] = int(occupancy_match.group(1))
        elif "couple" in lowered:
            constraints["occupancy"] = 2
        elif "family" in lowered:
            constraints["occupancy"] = 3

        for note in ["quiet", "safe", "winter", "commute", "family", "student"]:
            if note in lowered:
                constraints["notes"].append(note)

        missing_fields: list[str] = []
        if not any(key in constraints for key in ["city", "ward", "nearest_station"]) and intent_hint == "search":
            missing_fields.append("city")

        return {
            "message": text,
            "constraints": constraints,
            "missing_fields": missing_fields,
            "intent_hint": intent_hint,
            "selected_listing_ids": selected_listing_ids,
            "compare_targets": compare_targets,
            "compare_criteria": compare_criteria,
            "response_language": response_language,
            "output_format": output_format,
        }

    def _extract_compare_segments(self, text: str) -> list[str]:
        normalized_phrase = normalize_phrase(text)
        cleaned = re.sub(
            r"^\s*(compare|so sanh)\s+",
            "",
            normalized_phrase,
            flags=re.IGNORECASE,
        )
        segments = [
            segment.strip(" ,.;:!?\"'")
            for segment in re.split(r"\b(?:and|vs|versus|with|va|voi)\b", cleaned, flags=re.IGNORECASE)
        ]
        return [segment for segment in segments if segment]

    def _looks_like_listing_reference(self, segment: str) -> bool:
        generic_tokens = {
            "the",
            "listing",
            "listings",
            "same",
            "area",
            "above",
            "from",
            "by",
            "price",
            "rent",
            "location",
            "size",
            "criteria",
            "theo",
            "gia",
            "thue",
            "dien",
            "tich",
            "vi",
            "tri",
            "cung",
            "khu",
            "vuc",
            "vua",
            "list",
            "ra",
            "cac",
            "can",
            "trong",
        }
        tokens = tokenize_text(segment)
        specific_tokens = [token for token in tokens if token not in generic_tokens]
        return len(specific_tokens) >= 2
