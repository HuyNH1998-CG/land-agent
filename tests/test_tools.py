from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data import seed_all_datasets
from japan_rental_agent.tools import (
    AreaEnrichmentTool,
    ComparisonTool,
    ExportTool,
    ListingSearchTool,
    QueryParserTool,
    RankingTool,
)


def build_test_config() -> AppConfig:
    source_dir = Path("data")
    test_root = Path("tests") / "_tmp" / f"tools_{uuid4().hex}"
    data_dir = test_root / "data"
    shutil.copytree(source_dir, data_dir)
    config = AppConfig(
        llm_api_key=None,
        data_dir=data_dir,
        export_dir=data_dir / "exports",
        chroma_dir=data_dir / "chroma-test",
        floor_plan_dir=data_dir / "floor_plans",
    )
    seed_all_datasets(config, reset=True)
    return config


def cleanup_test_config(config: AppConfig) -> None:
    root = config.data_dir.parent
    shutil.rmtree(root, ignore_errors=True)


def test_parser_extracts_core_constraints() -> None:
    tool = QueryParserTool()
    parsed = tool.execute("Find me a 1LDK in Sapporo under 90000 yen near station for 2 people")

    assert parsed["constraints"]["city"] == "Sapporo"
    assert parsed["constraints"]["max_rent"] == 90000
    assert parsed["constraints"]["preferred_layout"] == "1LDK"
    assert parsed["constraints"]["occupancy"] == 2
    assert parsed["constraints"]["near_station"] is True


def test_search_enrichment_ranking_compare_and_export_flow() -> None:
    config = build_test_config()
    try:
        search_tool = ListingSearchTool(config)
        enrichment_tool = AreaEnrichmentTool(config)
        ranking_tool = RankingTool()
        comparison_tool = ComparisonTool(config)
        export_tool = ExportTool(config)

        search_result = search_tool.execute(
            {
                "city": "Sapporo",
                "max_rent": 80000,
                "min_area": 25,
                "near_station": True,
                "query_text": "quiet 1LDK near station in Sapporo",
            }
        )
        assert search_result["total"] > 0
        assert all(item["city"] == "Sapporo" for item in search_result["results"])

        top_results = search_result["results"][:8]
        enriched = enrichment_tool.execute(top_results, {"city": "Sapporo"})["enriched"]
        assert all("overall_safety_score" in item for item in enriched)
        assert all("floor_plan_asset" in item for item in enriched)

        ranked = ranking_tool.execute(
            enriched,
            {
                "weight_price": 0.45,
                "weight_location": 0.3,
                "weight_size": 0.15,
                "weight_safety": 0.1,
            },
        )["ranked"]
        assert ranked
        assert ranked[0]["score"] >= ranked[-1]["score"]
        assert "score_breakdown" in ranked[0]

        comparison = comparison_tool.execute([ranked[0]["id"], ranked[1]["id"]])["comparison"]
        assert len(comparison) == 2
        assert comparison[0]["pros"]
        assert comparison[0]["cons"]

        export_json = export_tool.execute(ranked[:3], "json")
        export_csv = export_tool.execute(ranked[:3], "csv")
        export_pdf = export_tool.execute(ranked[:3], "pdf")

        assert Path(export_json["file_url"]).exists()
        assert Path(export_csv["file_url"]).exists()
        assert Path(export_pdf["file_url"]).exists()
    finally:
        cleanup_test_config(config)
