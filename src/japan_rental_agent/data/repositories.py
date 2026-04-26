from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DatasetRegistry:
    root_dir: Path

    @property
    def listings_path(self) -> Path:
        return self.root_dir / "rental_listings_demo.csv"

    @property
    def hazard_path(self) -> Path:
        return self.root_dir / "ward_hazard_score.csv"

    @property
    def housing_context_path(self) -> Path:
        return self.root_dir / "housing_context_by_city.csv"

    @property
    def station_context_path(self) -> Path:
        return self.root_dir / "station_access_reference.csv"


class LocalDatasetRepository:
    """Thin data-access layer placeholder for CSV or SQLite-backed datasets."""

    def __init__(self, registry: DatasetRegistry) -> None:
        self.registry = registry

    def list_available_datasets(self) -> dict[str, Path]:
        return {
            "listings": self.registry.listings_path,
            "hazard": self.registry.hazard_path,
            "housing_context": self.registry.housing_context_path,
            "station_context": self.registry.station_context_path,
        }

    def read_csv_rows(self, path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
