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
    floor: int | None = None
    nearest_station: str | None = None
    distance_to_station_min: int | None = None
    commute_time_min: int | None = None
    foreigner_friendly: bool | None = None
    pet_allowed: bool | None = None
    lat: float | None = None
    lng: float | None = None
    floor_plan_asset: str | None = None
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
    area_m2: float | None = None
    walk_min: int | None = None
    overall_safety_score: float | None = None
    floor_plan_asset: str | None = None
