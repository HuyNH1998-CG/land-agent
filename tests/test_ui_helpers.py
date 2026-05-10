from __future__ import annotations

from japan_rental_agent.agent.utils import normalize_listing_payload
from ui.app import (
    build_enrichment_metric_items,
    build_enrichment_note_bits,
    build_search_more_reply,
    effective_message_language,
    listing_summary,
    merge_additional_listings,
)


def test_merge_additional_listings_appends_up_to_five_unique_options() -> None:
    current = [
        {"id": "old_1", "source_url": "https://suumo.jp/chintai/bc_1/"},
        {"id": "old_2", "source_url": "https://suumo.jp/chintai/bc_2/"},
    ]
    incoming = [
        {"id": "duplicate", "source_url": "https://suumo.jp/chintai/bc_2/"},
        *[
            {"id": f"new_{index}", "source_url": f"https://suumo.jp/chintai/bc_10{index}/"}
            for index in range(1, 7)
        ],
    ]

    merged, added = merge_additional_listings(current, incoming, max_new=5)

    assert added == 5
    assert len(merged) == 7
    assert [item["id"] for item in merged[-5:]] == ["new_1", "new_2", "new_3", "new_4", "new_5"]


def test_build_search_more_reply_reports_cumulative_total() -> None:
    reply = build_search_more_reply(added_count=5, total_count=12, language="vi")

    assert "5" in reply
    assert "12" in reply


def test_normalize_listing_payload_preserves_enrichment_fields() -> None:
    listing = normalize_listing_payload(
        {
            "listing_id": "sap_001",
            "title": "Sapporo test listing",
            "overall_safety_score": 8.4,
            "walkability_score": 7.2,
            "shopping_convenience_score": 6.9,
            "winter_transit_reliability_score": 8.1,
            "foreign_resident_support_score": 7.7,
            "city_avg_rent_1ldk_yen": 82000,
            "market_note": "Stable demand near transit.",
            "nearby_facilities": ["convenience_store", "supermarket"],
        },
        index=1,
    )

    assert listing["overall_safety_score"] == 8.4
    assert listing["walkability_score"] == 7.2
    assert listing["shopping_convenience_score"] == 6.9
    assert listing["winter_transit_reliability_score"] == 8.1
    assert listing["foreign_resident_support_score"] == 7.7
    assert listing["city_avg_rent_1ldk_yen"] == 82000
    assert listing["market_note"] == "Stable demand near transit."
    assert listing["nearby_facilities"] == ["convenience_store", "supermarket"]


def test_enrichment_context_labels_are_vietnamese() -> None:
    listing = {
        "overall_safety_score": 8.4,
        "shopping_convenience_score": 6.9,
        "nearby_facilities": ["convenience_store", "supermarket"],
        "context_sources": ["hazard_safety", "regional_indicators"],
        "extraction_confidence": 0.91,
        "market_note": "Central wards are transit-strong; outer wards trade commute time for larger floor area.",
    }

    metric_items = build_enrichment_metric_items(listing, language="vi")
    note_bits = build_enrichment_note_bits(listing, language="vi")

    assert ("An toàn", "8.40") in metric_items
    assert ("Tiện mua sắm", "6.90") in metric_items
    assert any("conbini" in bit and "siêu thị" in bit for bit in note_bits)
    assert any("Nguồn ngữ cảnh" in bit and "rủi ro thiên tai" in bit for bit in note_bits)
    assert any("Độ tin cậy trích xuất: 91.0%" in bit for bit in note_bits)
    assert any("Các quận trung tâm mạnh về giao thông" in bit for bit in note_bits)


def test_vietnamese_message_forces_vietnamese_card_language() -> None:
    message = {"content": "Tôi đã tìm được 9 lựa chọn thuê nhà phù hợp.", "language": "en"}

    assert effective_message_language(message) == "vi"


def test_listing_summary_is_vietnamese_when_language_is_vi() -> None:
    summary = listing_summary(
        {
            "title": "Test home",
            "layout": "1LDK",
            "city": "Sapporo",
            "ward": "Chuo",
            "rent": 46000,
            "area_m2": 35.51,
            "construction_year": 1980,
            "nearest_station": "Odori",
            "distance_to_station_min": 4,
            "source_name": "homes.co.jp",
        },
        language="vi",
    )

    assert "là căn 1LDK" in summary
    assert "với giá thuê 46,000 JPY" in summary
    assert "Nguồn: homes.co.jp." in summary
