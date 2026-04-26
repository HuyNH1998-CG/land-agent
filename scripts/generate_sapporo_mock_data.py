from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
LISTINGS_PATH = DATA_DIR / "rental_listings_demo.csv"
STATIONS_PATH = DATA_DIR / "station_access_reference.csv"
FLOOR_PLAN_REFERENCE_PATH = DATA_DIR / "floor_plan_reference.csv"

TARGET_TOTAL = 264
RANDOM_SEED = 20260426


LAYOUT_OPTIONS = [
    ("1R", (18.0, 24.0)),
    ("1K", (21.0, 28.0)),
    ("1DK", (26.0, 33.0)),
    ("1LDK", (34.0, 42.0)),
    ("2LDK", (46.0, 58.0)),
]
ADJECTIVES = [
    "Cozy",
    "Bright",
    "Practical",
    "Modern",
    "Quiet",
    "Flexible",
    "Sunny",
    "Smart",
    "Comfort",
    "Urban",
]
SUFFIXES = [
    "Residence",
    "Heights",
    "Court",
    "Terrace",
    "Plaza",
    "House",
    "Place",
    "Mansion",
    "Square",
    "Garden",
]
FLOOR_PLAN_BY_LAYOUT = {
    "1R": "data/floor_plans/layout_1r.svg",
    "1K": "data/floor_plans/layout_1k.svg",
    "1DK": "data/floor_plans/layout_1dk.svg",
    "1LDK": "data/floor_plans/layout_1ldk.svg",
    "2LDK": "data/floor_plans/layout_2ldk.svg",
}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"No rows provided for {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def choose_layout(rng: random.Random) -> tuple[str, tuple[float, float]]:
    roll = rng.random()
    if roll < 0.16:
        return LAYOUT_OPTIONS[0]
    if roll < 0.41:
        return LAYOUT_OPTIONS[1]
    if roll < 0.67:
        return LAYOUT_OPTIONS[2]
    if roll < 0.90:
        return LAYOUT_OPTIONS[3]
    return LAYOUT_OPTIONS[4]


def derive_rent(
    *,
    layout: str,
    area_m2: float,
    walk_min: int,
    station_score: float,
    major_hub: bool,
    building_age: int,
    rng: random.Random,
) -> int:
    base_by_layout = {
        "1R": 47000,
        "1K": 53000,
        "1DK": 61000,
        "1LDK": 76000,
        "2LDK": 92000,
    }
    rent = base_by_layout[layout]
    rent += int((area_m2 - 20.0) * 1200)
    rent += int((station_score - 7.0) * 2200)
    rent += 3500 if major_hub else 0
    rent -= max(0, walk_min - 4) * 1100
    rent -= building_age * 350
    rent += rng.randint(-3500, 3500)
    return max(42000, int(round(rent / 1000.0) * 1000))


def generate_rows() -> None:
    rng = random.Random(RANDOM_SEED)
    existing_rows = load_csv(LISTINGS_PATH)
    station_rows = load_csv(STATIONS_PATH)
    existing_ids = {row["listing_id"] for row in existing_rows}

    next_index = len(existing_rows) + 1
    base_date = date(2026, 5, 1)
    generated_rows: list[dict[str, str]] = []

    while len(existing_rows) + len(generated_rows) < TARGET_TOTAL:
        station = station_rows[(len(generated_rows) + next_index) % len(station_rows)]
        layout, area_range = choose_layout(rng)
        area_m2 = round(rng.uniform(*area_range), 1)
        walk_min = rng.randint(3, 10)
        building_age = rng.randint(1, 28)
        major_hub = station["major_hub"].strip().lower() == "true"
        station_score = float(station["walkability_score"])
        rent_yen = derive_rent(
            layout=layout,
            area_m2=area_m2,
            walk_min=walk_min,
            station_score=station_score,
            major_hub=major_hub,
            building_age=building_age,
            rng=rng,
        )
        management_fee = rng.choice([2000, 2500, 3000, 3500, 4000, 5000, 6000])
        deposit = rng.choice([0, rent_yen // 2, rent_yen])
        key_money = rng.choice([0, 0, rent_yen // 2, rent_yen])
        floor = rng.randint(1, 12)
        pet_allowed = rng.random() < 0.22
        foreigner_friendly = rng.random() < 0.78
        lat = round(float(station["lat"]) + rng.uniform(-0.0065, 0.0065), 6)
        lng = round(float(station["lng"]) + rng.uniform(-0.0065, 0.0065), 6)
        available_from = (base_date + timedelta(days=rng.randint(0, 120))).isoformat()

        listing_id = f"sap_{next_index:03d}"
        if listing_id in existing_ids:
            next_index += 1
            continue

        title = f"{station['station']} {rng.choice(ADJECTIVES)} {layout} {rng.choice(SUFFIXES)}"
        row = {
            "listing_id": listing_id,
            "title": title,
            "prefecture": station["prefecture"],
            "city": station["city"],
            "ward": station["ward"],
            "nearest_station": station["station"],
            "walk_min": str(walk_min),
            "rent_yen": str(rent_yen),
            "management_fee": str(management_fee),
            "deposit": str(deposit),
            "key_money": str(key_money),
            "layout": layout,
            "area_m2": f"{area_m2:.1f}",
            "building_age": str(building_age),
            "floor": str(floor),
            "pet_allowed": str(pet_allowed).lower(),
            "foreigner_friendly": str(foreigner_friendly).lower(),
            "available_from": available_from,
            "lat": f"{lat:.6f}",
            "lng": f"{lng:.6f}",
        }
        generated_rows.append(row)
        existing_ids.add(listing_id)
        next_index += 1

    all_rows = sorted(existing_rows + generated_rows, key=lambda item: item["listing_id"])
    write_csv(LISTINGS_PATH, all_rows)

    floor_plan_rows = [
        {
            "listing_id": row["listing_id"],
            "layout": row["layout"],
            "floor_plan_asset": FLOOR_PLAN_BY_LAYOUT.get(row["layout"], FLOOR_PLAN_BY_LAYOUT["1K"]),
        }
        for row in all_rows
    ]
    write_csv(FLOOR_PLAN_REFERENCE_PATH, floor_plan_rows)

    print(f"Generated {len(generated_rows)} additional listings.")
    print(f"Total listings: {len(all_rows)}")


if __name__ == "__main__":
    generate_rows()
