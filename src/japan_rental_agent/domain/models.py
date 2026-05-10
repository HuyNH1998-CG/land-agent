from __future__ import annotations

from pydantic import BaseModel, Field


class ListingScoreBreakdown(BaseModel):
    price: float | None = None
    location: float | None = None
    size: float | None = None
    safety: float | None = None


class Listing(BaseModel):
    id: str
    title: str
    city: str | None = None
    ward: str | None = None
    rent: int | None = None
    management_fee: int | None = None
    layout: str | None = None
    area_m2: float | None = None
    building_age: int | None = None
    construction_year: int | None = None
    floor: int | None = None
    nearest_station: str | None = None
    distance_to_station_min: int | None = None
    commute_time_min: int | None = None
    flood_risk_score: float | None = None
    earthquake_risk_score: float | None = None
    overall_safety_score: float | None = None
    walkability_score: float | None = None
    shopping_convenience_score: float | None = None
    winter_transit_reliability_score: float | None = None
    city_population_estimate: int | None = None
    city_renter_household_ratio: float | None = None
    city_avg_rent_1k_yen: int | None = None
    city_avg_rent_1ldk_yen: int | None = None
    foreign_resident_support_score: float | None = None
    winter_livability_score: float | None = None
    market_note: str | None = None
    foreigner_friendly: bool | None = None
    pet_allowed: bool | None = None
    lat: float | None = None
    lng: float | None = None
    floor_plan_asset: str | None = None
    nearby_facilities: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    source_url: str | None = None
    source_name: str | None = None
    source_snippet: str | None = None
    source_kind: str | None = None
    source_validated: bool | None = None
    source_validation_reason: str | None = None
    metadata_fields_found: list[str] = Field(default_factory=list)
    metadata_error: str | None = None
    extraction_confidence: float | None = None
    context_sources: list[str] = Field(default_factory=list)
    score: float | None = None
    score_breakdown: ListingScoreBreakdown | None = None


class SearchFilters(BaseModel):
    city: str | None = None
    ward: str | None = None
    prefecture: str | None = None
    max_rent: int | None = None
    min_area: float | None = None
    near_station: bool | None = None
    occupancy: int | None = None
    preferred_layout: str | None = None
    notes: list[str] = Field(default_factory=list)


class ComparisonItem(BaseModel):
    id: str
    title: str | None = None
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    rent_yen: int | None = None
    management_fee: int | None = None
    area_m2: float | None = None
    walk_min: int | None = None
    overall_safety_score: float | None = None
    construction_year: int | None = None
    floor_plan_asset: str | None = None
    image_urls: list[str] = Field(default_factory=list)
