from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data import ChromaVectorStore, seed_all_datasets
from japan_rental_agent.data.seed import (
    HAZARD_COLLECTION,
    HOUSING_COLLECTION,
    LISTING_COLLECTION,
    STATION_COLLECTION,
)


def test_seed_all_datasets_populates_chroma() -> None:
    source_dir = Path("data")
    test_root = Path("tests") / "_tmp" / f"seed_{uuid4().hex}"
    data_dir = test_root / "data"
    try:
        shutil.copytree(source_dir, data_dir)

        config = AppConfig(
            llm_api_key=None,
            data_dir=data_dir,
            chroma_dir=data_dir / "chroma-test",
        )
        summaries = seed_all_datasets(config, reset=True)
        counts = {summary.collection_name: summary.record_count for summary in summaries}

        assert counts == {
            LISTING_COLLECTION: 264,
            HAZARD_COLLECTION: 10,
            HOUSING_COLLECTION: 1,
            STATION_COLLECTION: 17,
        }

        store = ChromaVectorStore(config)
        assert store.get_or_create_collection(LISTING_COLLECTION).count() == 264
        assert store.get_or_create_collection(HAZARD_COLLECTION).count() == 10
        assert store.get_or_create_collection(HOUSING_COLLECTION).count() == 1
        assert store.get_or_create_collection(STATION_COLLECTION).count() == 17
    finally:
        shutil.rmtree(test_root, ignore_errors=True)
