from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data.repositories import DatasetRegistry, LocalDatasetRepository
from japan_rental_agent.data.vector_store import ChromaVectorStore, SeedRecord


LISTING_COLLECTION = "rental-listings"
HAZARD_COLLECTION = "ward-hazard"
HOUSING_COLLECTION = "housing-context"
STATION_COLLECTION = "station-context"


@dataclass(slots=True)
class SeedSummary:
    collection_name: str
    record_count: int


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    return None


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        cleaned[key] = value
    return cleaned


def _listing_document(row: dict[str, str]) -> str:
    return (
        f"Rental listing {row['listing_id']} in {row['ward']}, Sapporo, Hokkaido. "
        f"Title: {row['title']}. Layout {row['layout']}, area {row['area_m2']} square meters, "
        f"rent {row['rent_yen']} yen, management fee {row['management_fee']} yen, "
        f"{row['walk_min']} minutes walk to {row['nearest_station']} station. "
        f"Building age {row['building_age']} years, floor {row['floor']}, "
        f"pet allowed {row['pet_allowed']}, foreigner friendly {row['foreigner_friendly']}."
    )


def _hazard_document(row: dict[str, str]) -> str:
    return (
        f"Hazard profile for {row['ward']} ward in Sapporo, Hokkaido. "
        f"Flood risk score {row['flood_risk_score']}, earthquake risk score {row['earthquake_risk_score']}, "
        f"overall safety score {row['overall_safety_score']}."
    )


def _housing_document(row: dict[str, str]) -> str:
    return (
        f"Housing context for {row['city']}, {row['prefecture']}. Population estimate {row['population_estimate']}, "
        f"renter household ratio {row['renter_household_ratio']}, average 1K rent {row['avg_rent_1k_yen']} yen, "
        f"average 1LDK rent {row['avg_rent_1ldk_yen']} yen. "
        f"Foreign resident support score {row['foreign_resident_support_score']}, "
        f"winter livability score {row['winter_livability_score']}. Note: {row['market_note']}"
    )


def _station_document(row: dict[str, str]) -> str:
    return (
        f"Station context for {row['station']} in {row['ward']}, Sapporo, Hokkaido. "
        f"Line group {row['line_group']}, major hub {row['major_hub']}, average commute to Sapporo station "
        f"{row['avg_commute_to_sapporo_min']} minutes, airport access {row['airport_access_min']} minutes, "
        f"walkability score {row['walkability_score']}, shopping convenience score {row['shopping_convenience_score']}, "
        f"winter transit reliability score {row['winter_transit_reliability_score']}."
    )


def _build_listing_records(rows: list[dict[str, str]]) -> list[SeedRecord]:
    records: list[SeedRecord] = []
    for row in rows:
        metadata = _compact_metadata(
            {
                "listing_id": row["listing_id"],
                "prefecture": row["prefecture"],
                "city": row["city"],
                "ward": row["ward"],
                "nearest_station": row["nearest_station"],
                "walk_min": _parse_int(row["walk_min"]),
                "rent_yen": _parse_int(row["rent_yen"]),
                "management_fee": _parse_int(row["management_fee"]),
                "deposit": _parse_int(row["deposit"]),
                "key_money": _parse_int(row["key_money"]),
                "layout": row["layout"],
                "area_m2": _parse_float(row["area_m2"]),
                "building_age": _parse_int(row["building_age"]),
                "floor": _parse_int(row["floor"]),
                "pet_allowed": _parse_bool(row["pet_allowed"]),
                "foreigner_friendly": _parse_bool(row["foreigner_friendly"]),
                "available_from": row["available_from"],
                "lat": _parse_float(row["lat"]),
                "lng": _parse_float(row["lng"]),
            }
        )
        records.append(
            SeedRecord(
                id=row["listing_id"],
                document=_listing_document(row),
                metadata=metadata,
            )
        )
    return records


def _build_hazard_records(rows: list[dict[str, str]]) -> list[SeedRecord]:
    return [
        SeedRecord(
            id=f"hazard_{row['city'].lower()}_{row['ward'].lower()}",
            document=_hazard_document(row),
            metadata=_compact_metadata(
                {
                    "prefecture": row["prefecture"],
                    "city": row["city"],
                    "ward": row["ward"],
                    "flood_risk_score": _parse_float(row["flood_risk_score"]),
                    "earthquake_risk_score": _parse_float(row["earthquake_risk_score"]),
                    "overall_safety_score": _parse_float(row["overall_safety_score"]),
                }
            ),
        )
        for row in rows
    ]


def _build_housing_records(rows: list[dict[str, str]]) -> list[SeedRecord]:
    return [
        SeedRecord(
            id=f"housing_{row['city'].lower()}",
            document=_housing_document(row),
            metadata=_compact_metadata(
                {
                    "prefecture": row["prefecture"],
                    "city": row["city"],
                    "population_estimate": _parse_int(row["population_estimate"]),
                    "renter_household_ratio": _parse_float(row["renter_household_ratio"]),
                    "avg_rent_1k_yen": _parse_int(row["avg_rent_1k_yen"]),
                    "avg_rent_1ldk_yen": _parse_int(row["avg_rent_1ldk_yen"]),
                    "avg_area_m2_1k": _parse_float(row["avg_area_m2_1k"]),
                    "vacancy_rate_pct": _parse_float(row["vacancy_rate_pct"]),
                    "foreign_resident_support_score": _parse_float(row["foreign_resident_support_score"]),
                    "winter_livability_score": _parse_float(row["winter_livability_score"]),
                }
            ),
        )
        for row in rows
    ]


def _build_station_records(rows: list[dict[str, str]]) -> list[SeedRecord]:
    return [
        SeedRecord(
            id=f"station_{row['station'].lower().replace(' ', '_')}",
            document=_station_document(row),
            metadata=_compact_metadata(
                {
                    "station": row["station"],
                    "prefecture": row["prefecture"],
                    "city": row["city"],
                    "ward": row["ward"],
                    "line_group": row["line_group"],
                    "major_hub": _parse_bool(row["major_hub"]),
                    "avg_commute_to_sapporo_min": _parse_int(row["avg_commute_to_sapporo_min"]),
                    "airport_access_min": _parse_int(row["airport_access_min"]),
                    "walkability_score": _parse_float(row["walkability_score"]),
                    "shopping_convenience_score": _parse_float(row["shopping_convenience_score"]),
                    "winter_transit_reliability_score": _parse_float(row["winter_transit_reliability_score"]),
                    "lat": _parse_float(row["lat"]),
                    "lng": _parse_float(row["lng"]),
                }
            ),
        )
        for row in rows
    ]


def seed_all_datasets(config: AppConfig | None = None, *, reset: bool = True) -> list[SeedSummary]:
    app_config = config or AppConfig()
    registry = DatasetRegistry(root_dir=app_config.data_dir)
    repository = LocalDatasetRepository(registry)
    vector_store = ChromaVectorStore(app_config)

    listings = _build_listing_records(repository.read_csv_rows(registry.listings_path))
    hazards = _build_hazard_records(repository.read_csv_rows(registry.hazard_path))
    housing_context = _build_housing_records(repository.read_csv_rows(registry.housing_context_path))
    stations = _build_station_records(repository.read_csv_rows(registry.station_context_path))

    summaries = [
        SeedSummary(
            collection_name=LISTING_COLLECTION,
            record_count=vector_store.upsert_records(
                LISTING_COLLECTION,
                listings,
                reset=reset,
                metadata={"dataset_type": "rental_listings"},
            ),
        ),
        SeedSummary(
            collection_name=HAZARD_COLLECTION,
            record_count=vector_store.upsert_records(
                HAZARD_COLLECTION,
                hazards,
                reset=reset,
                metadata={"dataset_type": "hazard_scores"},
            ),
        ),
        SeedSummary(
            collection_name=HOUSING_COLLECTION,
            record_count=vector_store.upsert_records(
                HOUSING_COLLECTION,
                housing_context,
                reset=reset,
                metadata={"dataset_type": "housing_context"},
            ),
        ),
        SeedSummary(
            collection_name=STATION_COLLECTION,
            record_count=vector_store.upsert_records(
                STATION_COLLECTION,
                stations,
                reset=reset,
                metadata={"dataset_type": "station_context"},
            ),
        ),
    ]
    return summaries
