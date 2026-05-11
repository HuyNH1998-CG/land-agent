from __future__ import annotations

import math
import re
import sys
import uuid
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
PAGE_SIZE = 5

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from japan_rental_agent.agent import RentalAgentService
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest, RequestContext, RequestOptions

st.set_page_config(page_title="Trợ lý thuê nhà Nhật Bản", layout="wide")

SAMPLE_PROMPTS = [
    "Tìm căn 1LDK ở Sapporo dưới 85,000 yên",
    "Tìm căn cho nuôi thú cưng, đi lại thuận tiện ở Tokyo",
    "So sánh các căn đã chọn",
    "Xuất danh sách rút gọn dạng CSV",
]

CUSTOM_CSS = """
<style>
    :root {
        --surface: #ffffff;
        --surface-muted: #f6f8fb;
        --line: rgba(120, 130, 150, 0.35);
        --text-main: #172033;
        --text-muted: #5f6b7a;
        --accent: #1f6feb;
        --accent-soft: #eaf2ff;
        --ok-soft: #eaf7ef;
        --warn-soft: #fff6df;
    }

    .stApp {
        --surface: var(--background-color, #ffffff);
        --surface-muted: var(--secondary-background-color, #f6f8fb);
        --text-main: var(--text-color, #172033);
        --text-muted: color-mix(in srgb, var(--text-color, #172033) 72%, var(--background-color, #ffffff));
        --accent: var(--primary-color, #1f6feb);
        --accent-soft: color-mix(in srgb, var(--primary-color, #1f6feb) 14%, var(--background-color, #ffffff));
        --ok-soft: color-mix(in srgb, #2da44e 16%, var(--background-color, #ffffff));
        --warn-soft: color-mix(in srgb, #bf8700 18%, var(--background-color, #ffffff));
        background: var(--surface);
        color: var(--text-main);
    }

    .stApp[data-theme="dark"],
    [data-theme="dark"] .stApp,
    html[data-theme="dark"] .stApp,
    body[data-theme="dark"] .stApp,
    [data-baseweb-theme="dark"] .stApp {
        --surface: var(--background-color, #0e1117);
        --surface-muted: var(--secondary-background-color, #1a1d24);
        --line: rgba(209, 217, 230, 0.24);
        --text-main: var(--text-color, #f4f6fb);
        --text-muted: color-mix(in srgb, var(--text-color, #f4f6fb) 76%, var(--background-color, #0e1117));
        --accent: var(--primary-color, #7aa2ff);
        --accent-soft: color-mix(in srgb, var(--primary-color, #7aa2ff) 22%, var(--background-color, #0e1117));
        --ok-soft: color-mix(in srgb, #3fb950 22%, var(--background-color, #0e1117));
        --warn-soft: color-mix(in srgb, #d29922 24%, var(--background-color, #0e1117));
    }

    [data-testid="stSidebar"] {
        background: var(--surface-muted);
        border-right: 1px solid var(--line);
    }

    [data-testid="stMainBlockContainer"] {
        max-width: 1120px;
        padding-top: 4.75rem;
        padding-bottom: 8rem;
    }

    h1, h2, h3 {
        letter-spacing: 0;
    }

    .app-hero {
        margin-bottom: 1.25rem;
    }

    .app-eyebrow {
        color: var(--accent);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }

    .app-hero h1 {
        color: var(--text-main);
        font-size: 2.55rem;
        line-height: 1.08;
        margin: 0 0 0.55rem;
    }

    .app-hero p {
        color: var(--text-muted);
        font-size: 1.02rem;
        max-width: 760px;
        margin: 0;
    }

    .empty-panel {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1.1rem 1.2rem;
        margin: 1.25rem 0 0.75rem;
    }

    .empty-panel h3 {
        font-size: 1.05rem;
        margin: 0 0 0.4rem;
    }

    .empty-panel p {
        color: var(--text-muted);
        margin: 0;
    }

    .section-label {
        color: var(--text-muted);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0.4rem 0 0.5rem;
    }

    .listing-heading {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 0.5rem;
    }

    .listing-title {
        font-size: 1.08rem;
        font-weight: 700;
        color: var(--text-main);
        margin-bottom: 0.2rem;
    }

    .listing-subtitle {
        color: var(--text-muted);
        font-size: 0.9rem;
    }

    .listing-price {
        color: var(--text-main);
        font-size: 1.35rem;
        font-weight: 750;
        text-align: right;
        white-space: nowrap;
    }

    .listing-price-caption {
        color: var(--text-muted);
        font-size: 0.8rem;
        text-align: right;
    }

    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin: 0.35rem 0 0.75rem;
    }

    .badge {
        border: 1px solid var(--line);
        border-radius: 999px;
        color: var(--text-main);
        display: inline-flex;
        font-size: 0.78rem;
        font-weight: 650;
        line-height: 1;
        padding: 0.38rem 0.55rem;
        background: var(--surface-muted);
    }

    .badge.good {
        background: var(--ok-soft);
        border-color: color-mix(in srgb, #2da44e 38%, var(--line));
    }

    .badge.info {
        background: var(--accent-soft);
        border-color: color-mix(in srgb, var(--accent) 38%, var(--line));
    }

    .badge.warn {
        background: var(--warn-soft);
        border-color: color-mix(in srgb, #bf8700 42%, var(--line));
    }

    .compact-note {
        color: var(--text-muted);
        font-size: 0.86rem;
        line-height: 1.5;
    }

    [data-testid="stMetric"] {
        background: var(--surface-muted);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.7rem 0.75rem;
    }

    [data-testid="stMetricLabel"] {
        color: var(--text-muted);
    }

    [data-testid="stMetricValue"] {
        color: var(--text-main);
        font-size: 1.1rem;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--line);
        box-shadow: 0 1px 2px rgba(17, 24, 39, 0.08);
    }

    [data-testid="stChatInput"] textarea {
        font-size: 0.95rem;
    }

    @media (prefers-color-scheme: dark) {
        .stApp {
            --surface: var(--background-color, #0e1117);
            --surface-muted: var(--secondary-background-color, #1a1d24);
            --line: rgba(209, 217, 230, 0.24);
            --text-main: var(--text-color, #f4f6fb);
            --text-muted: color-mix(in srgb, var(--text-color, #f4f6fb) 76%, var(--background-color, #0e1117));
            --accent: var(--primary-color, #7aa2ff);
            --accent-soft: color-mix(in srgb, var(--primary-color, #7aa2ff) 22%, var(--background-color, #0e1117));
            --ok-soft: color-mix(in srgb, #3fb950 22%, var(--background-color, #0e1117));
            --warn-soft: color-mix(in srgb, #d29922 24%, var(--background-color, #0e1117));
        }
    }

    @media (max-width: 720px) {
        [data-testid="stMainBlockContainer"] {
            padding-top: 1.8rem;
            padding-left: 1rem;
            padding-right: 1rem;
            padding-bottom: 5.5rem;
        }

        .app-hero {
            margin-bottom: 0.75rem;
        }

        .app-hero h1 {
            font-size: 1.8rem;
            margin-bottom: 0;
        }

        .app-hero p {
            display: none;
        }

        .empty-panel {
            margin-top: 0.85rem;
            padding: 0.85rem 0.9rem;
        }

        .empty-panel h3 {
            font-size: 0.98rem;
        }

        .empty-panel p {
            font-size: 0.88rem;
            line-height: 1.45;
        }

        .listing-heading {
            display: block;
        }

        .listing-price,
        .listing-price-caption {
            text-align: left;
            margin-top: 0.4rem;
        }
    }
</style>
"""


@st.cache_resource
def get_agent_service() -> RentalAgentService:
    return RentalAgentService(config=AppConfig())


def inject_custom_css() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_app_header() -> None:
    st.markdown(
        """
        <div class="app-hero">
            <div class="app-eyebrow">Không gian chọn nhà thuê</div>
            <h1>Trợ lý thuê nhà Nhật Bản</h1>
            <p>Tìm nhà thuê, so sánh điểm đánh đổi và xuất danh sách rút gọn ngay trong luồng chat.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="empty-panel">
            <h3>Bắt đầu bằng nhu cầu thuê nhà cụ thể</h3>
            <p>Hãy nhập ngân sách, thành phố, loại phòng, ga muốn ở gần, thời gian đi lại, hoặc yêu cầu so sánh các căn đã lưu.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-label">Gợi ý nhanh</div>', unsafe_allow_html=True)
    columns = st.columns(2)
    for index, prompt in enumerate(SAMPLE_PROMPTS):
        with columns[index % 2]:
            if st.button(prompt, key=f"sample_prompt_{index}", use_container_width=True):
                st.session_state["pending_chat_input"] = prompt
                st.rerun()


def initialize_session() -> None:
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("selected_listings", [])
    st.session_state.setdefault("previous_filters", {})
    st.session_state.setdefault("recent_listings", [])
    st.session_state.setdefault("pending_request", None)


def resolve_workspace_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def read_svg_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def resize_svg_markup(svg_text: str, *, max_width_px: int) -> str:
    responsive_svg = re.sub(r"<svg\b", "<svg style=\"width:100%;height:auto;display:block;\"", svg_text, count=1)
    return (
        f"<div style=\"max-width:{max_width_px}px;width:100%;overflow:hidden;margin:0 auto;\">"
        f"{responsive_svg}"
        "</div>"
    )


def format_currency(value: int | None) -> str:
    return f"{value:,} yên" if isinstance(value, int) else "chưa rõ"


def format_area(value: float | None) -> str:
    return f"{value:.2f} m²" if isinstance(value, (float, int)) else "chưa rõ"


def format_year(value: int | None) -> str:
    return str(value) if isinstance(value, int) else "chưa rõ"


def format_minutes(value: int | None) -> str:
    return f"{value} phút" if isinstance(value, int) else "chưa rõ"


def format_integer(value: int | None) -> str:
    return f"{value:,}" if isinstance(value, int) else "chưa rõ"


def format_percent(value: float | None) -> str:
    return f"{value:.1%}" if isinstance(value, (float, int)) else "chưa rõ"


def format_score(value: float | None) -> str:
    return f"{value:.4f}" if isinstance(value, (float, int)) else "chưa rõ"


def format_compact_score(value: float | None) -> str:
    return f"{value:.2f}" if isinstance(value, (float, int)) else "chưa rõ"



def collect_known_listings() -> dict[str, dict[str, Any]]:
    known: dict[str, dict[str, Any]] = {}
    for message in st.session_state["messages"]:
        for listing in message.get("listings", []):
            known[str(listing["id"])] = listing
    return known


def listing_identity(listing: dict[str, Any]) -> str:
    source_url = str(listing.get("source_url") or "").strip()
    if source_url:
        return f"url:{source_url}"
    return f"id:{listing.get('id') or listing.get('listing_id') or listing.get('title')}"


def merge_additional_listings(
    current_listings: list[dict[str, Any]],
    new_listings: list[dict[str, Any]],
    *,
    max_new: int = 5,
) -> tuple[list[dict[str, Any]], int]:
    merged = list(current_listings)
    seen = {listing_identity(listing) for listing in merged}
    added = 0
    for listing in new_listings:
        identity = listing_identity(listing)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(listing)
        added += 1
        if added >= max_new:
            break
    return merged, added



def listing_summary(listing: dict[str, Any], *, language: str) -> str:
    title = str(listing.get("title") or "căn hộ").strip()
    location = " ".join(str(part) for part in [listing.get("city"), listing.get("ward")] if part)
    station = listing.get("nearest_station") or listing.get("station")
    rent = format_currency(listing.get("rent") or listing.get("rent_yen"))
    area = format_area(listing.get("area_m2"))
    layout = listing.get("layout") or "chưa rõ"
    walk = format_minutes(listing.get("distance_to_station_min") or listing.get("walk_min"))
    year = format_year(listing.get("construction_year"))
    source = listing.get("source_name") or "nguồn"

    pieces = [f"{title} là căn {layout}"]
    if location:
        pieces.append(f"ở {location}")
    pieces.append(
        f"với giá thuê {rent}, diện tích {area}, năm xây {year}, cách ga {station or 'gần nhất'} {walk}."
    )
    pieces.append(f"Nguồn: {source}.")
    return " ".join(pieces)


def build_search_more_reply(*, added_count: int, total_count: int, language: str) -> str:
    if added_count:
        return f"Tôi đã bổ sung {added_count} lựa chọn mới vào danh sách hiện tại. Danh sách hiện có {total_count} lựa chọn."
    return "Tôi chưa tìm được lựa chọn mới ngoài danh sách hiện tại."


def build_conversation_history(limit: int = 8) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for message in st.session_state["messages"][-limit:]:
        history.append({"role": message["role"], "content": message["content"]})
    return history


def build_gallery_items(listing: dict[str, Any], *, language: str = "vi") -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    if listing.get("source_validated") is True:
        for index, url in enumerate(listing.get("image_urls") or [], start=1):
            candidate = str(url).strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            label = f"Ảnh {index}"
            items.append({"kind": "remote", "value": candidate, "label": label})

    floor_plan_asset = resolve_workspace_path(listing.get("floor_plan_asset"))
    if floor_plan_asset and floor_plan_asset.exists():
        candidate = str(floor_plan_asset)
        if candidate not in seen:
            seen.add(candidate)
            label = "Mặt bằng"
            items.append({"kind": "asset", "value": candidate, "label": label})

    return items


def render_gallery_item(item: dict[str, str], *, max_width_px: int) -> None:
    if item["kind"] == "asset":
        asset_path = Path(item["value"])
        if asset_path.suffix.lower() == ".svg":
            svg_text = read_svg_text(asset_path)
            if svg_text:
                st.markdown(resize_svg_markup(svg_text, max_width_px=max_width_px), unsafe_allow_html=True)
                return
        st.image(item["value"], width=max_width_px)
        return

    st.image(item["value"], width=max_width_px)


def render_image_gallery(listing: dict[str, Any], *, gallery_key: str, max_width_px: int = 320, language: str = "vi") -> None:
    gallery_items = build_gallery_items(listing, language=language)
    if not gallery_items:
        st.caption("Chưa có hình ảnh")
        return

    index_key = f"gallery_index_{gallery_key}"
    current_index = min(max(int(st.session_state.get(index_key, 0)), 0), len(gallery_items) - 1)
    st.session_state[index_key] = current_index

    nav_left, nav_center, nav_right = st.columns([1, 2, 1])
    with nav_left:
        prev_label = "Trước"
        if st.button(prev_label, key=f"{gallery_key}_prev", disabled=current_index == 0, use_container_width=True):
            st.session_state[index_key] = current_index - 1
            st.rerun()
    with nav_center:
        st.caption(f"{gallery_items[current_index]['label']} ({current_index + 1}/{len(gallery_items)})")
    with nav_right:
        next_label = "Tiếp"
        if st.button(
            next_label,
            key=f"{gallery_key}_next",
            disabled=current_index >= len(gallery_items) - 1,
            use_container_width=True,
        ):
            st.session_state[index_key] = current_index + 1
            st.rerun()

    render_gallery_item(gallery_items[current_index], max_width_px=max_width_px)


def render_metric_grid(items: list[tuple[str, str]], *, columns_per_row: int = 2) -> None:
    for index in range(0, len(items), columns_per_row):
        columns = st.columns(columns_per_row)
        for column, item in zip(columns, items[index : index + columns_per_row]):
            label, value = item
            column.metric(label, value)


def render_badges(items: list[tuple[str, str]]) -> None:
    if not items:
        return
    markup = "".join(
        f'<span class="badge {escape(kind)}">{escape(label)}</span>'
        for label, kind in items
    )
    st.markdown(f'<div class="badge-row">{markup}</div>', unsafe_allow_html=True)


def effective_message_language(message: dict[str, Any]) -> str:
    return "vi"


def toggle_listing(selected: bool, listing_id: str) -> None:
    current = set(st.session_state["selected_listings"])
    if selected:
        current.add(listing_id)
    else:
        current.discard(listing_id)
    st.session_state["selected_listings"] = sorted(current)


def clear_selected_listings() -> None:
    st.session_state["selected_listings"] = []
    for key in list(st.session_state.keys()):
        if key.startswith("select_"):
            st.session_state[key] = False


def context_source_label(source: str, *, language: str) -> str:
    labels = {
        "housing_land_survey": "khảo sát nhà ở và đất đai",
        "mlit_real_estate": "ngữ cảnh thị trường MLIT",
        "hazard_safety": "rủi ro thiên tai và an toàn",
        "regional_indicators": "chỉ số khu vực",
    }
    return labels.get(source, source.replace("_", " "))


def nearby_facility_label(facility: str, *, language: str) -> str:
    labels = {
        "convenience_store": "conbini / cửa hàng tiện lợi",
        "supermarket": "siêu thị",
        "drugstore": "drugstore / nhà thuốc",
        "park": "công viên",
        "hospital": "bệnh viện hoặc phòng khám",
        "school": "trường học",
        "shopping_mall": "trung tâm mua sắm",
    }
    return labels.get(facility, facility.replace("_", " "))


def localized_market_note(note: str, *, language: str) -> str:
    known_notes = {
        "Central wards are transit-strong; outer wards trade commute time for larger floor area.": (
            "Các quận trung tâm mạnh về giao thông; các quận xa trung tâm hơn thường đổi thời gian đi lại lấy diện tích lớn hơn."
        ),
    }
    return known_notes.get(note, note)


def build_nearby_facility_note(listing: dict[str, Any], *, language: str) -> str | None:
    facilities = list(dict.fromkeys(str(item) for item in listing.get("nearby_facilities", []) if str(item).strip()))
    if facilities:
        labels = ", ".join(nearby_facility_label(item, language=language) for item in facilities)
        return f"Tiện ích quanh nhà: có nhắc tới {labels}"
    if listing.get("shopping_convenience_score") is not None:
        return "Tiện ích quanh nhà: chưa có tên conbini/siêu thị cụ thể; hiện chỉ có điểm tiện mua sắm theo khu vực ga"
    return None


def build_enrichment_metric_items(listing: dict[str, Any], *, language: str) -> list[tuple[str, str]]:
    labels = {
        "safety": "An toàn",
        "commute": "Tới trung tâm",
        "walkability": "Đi bộ",
        "shopping": "Tiện mua sắm",
        "winter_transit": "Giao thông mùa đông",
        "foreign_support": "Hỗ trợ người nước ngoài",
    }
    candidates = [
        (labels["safety"], format_compact_score(listing.get("overall_safety_score")), listing.get("overall_safety_score")),
        (labels["commute"], format_minutes(listing.get("commute_time_min")), listing.get("commute_time_min")),
        (labels["walkability"], format_compact_score(listing.get("walkability_score")), listing.get("walkability_score")),
        (
            labels["shopping"],
            format_compact_score(listing.get("shopping_convenience_score")),
            listing.get("shopping_convenience_score"),
        ),
        (
            labels["winter_transit"],
            format_compact_score(listing.get("winter_transit_reliability_score")),
            listing.get("winter_transit_reliability_score"),
        ),
        (
            labels["foreign_support"],
            format_compact_score(listing.get("foreign_resident_support_score")),
            listing.get("foreign_resident_support_score"),
        ),
    ]
    return [(label, value) for label, value, raw_value in candidates if raw_value is not None]


def build_enrichment_note_bits(listing: dict[str, Any], *, language: str) -> list[str]:
    bits: list[str] = []
    nearby_note = build_nearby_facility_note(listing, language=language)
    if nearby_note:
        bits.append(nearby_note)
    if listing.get("flood_risk_score") is not None:
        bits.append(f"Rủi ro ngập: {format_compact_score(listing.get('flood_risk_score'))}")
    if listing.get("earthquake_risk_score") is not None:
        bits.append(f"Rủi ro động đất: {format_compact_score(listing.get('earthquake_risk_score'))}")
    if listing.get("winter_livability_score") is not None:
        bits.append(f"Mức sống mùa đông: {format_compact_score(listing.get('winter_livability_score'))}")
    if listing.get("city_renter_household_ratio") is not None:
        bits.append(f"Tỷ lệ hộ thuê: {format_percent(listing.get('city_renter_household_ratio'))}")
    if listing.get("city_avg_rent_1k_yen") is not None:
        bits.append(f"Giá thuê TB 1K khu vực: {format_currency(listing.get('city_avg_rent_1k_yen'))}")
    if listing.get("city_avg_rent_1ldk_yen") is not None:
        bits.append(f"Giá thuê TB 1LDK khu vực: {format_currency(listing.get('city_avg_rent_1ldk_yen'))}")
    if listing.get("city_population_estimate") is not None:
        bits.append(f"Dân số ước tính: {format_integer(listing.get('city_population_estimate'))}")
    if listing.get("context_sources"):
        sources = ", ".join(context_source_label(str(source), language=language) for source in listing.get("context_sources", [])[:3])
        bits.append(f"Nguồn ngữ cảnh: {sources}")
    if listing.get("extraction_confidence") is not None:
        bits.append(f"Độ tin cậy trích xuất: {format_percent(listing.get('extraction_confidence'))}")
    if listing.get("market_note"):
        bits.append(f"Ghi chú thị trường: {localized_market_note(str(listing.get('market_note')), language=language)}")
    return bits


def render_listing_card(listing: dict[str, Any], message_index: int, *, language: str) -> None:
    station = listing.get("nearest_station") or listing.get("station") or "Chưa rõ ga"
    walk_minutes = listing.get("distance_to_station_min") or listing.get("walk_min")
    rent = format_currency(listing.get("rent") or listing.get("rent_yen"))
    title = escape(str(listing.get("title") or "Chưa có tiêu đề"))
    location = escape(" ".join(str(part) for part in [listing.get("city"), listing.get("ward")] if part) or "Chưa rõ khu vực")
    layout = escape(str(listing.get("layout") or "chưa rõ"))
    station_label = escape(str(station))
    walk_label = escape(format_minutes(walk_minutes))
    monthly_caption = "tiền thuê hàng tháng"

    st.markdown(
        f"""
        <div class="listing-heading">
            <div>
                <div class="listing-title">{title}</div>
                <div class="listing-subtitle">{location} · {layout} · {station_label} ({walk_label})</div>
            </div>
            <div>
                <div class="listing-price">{escape(rent)}</div>
                <div class="listing-price-caption">{escape(monthly_caption)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    badge_items: list[tuple[str, str]] = []
    if listing.get("source_validated") is True:
        badge_items.append(("Nguồn đã xác thực", "info"))
    if listing.get("foreigner_friendly") is True:
        badge_items.append(("Hỗ trợ người nước ngoài", "good"))
    if listing.get("pet_allowed") is True:
        badge_items.append(("Cho nuôi thú cưng", "good"))
    if listing.get("overall_safety_score") is not None:
        badge_items.append((f"An toàn {format_compact_score(listing.get('overall_safety_score'))}", "warn"))
    if listing.get("commute_time_min") is not None:
        badge_items.append((f"Tới trung tâm {format_minutes(listing.get('commute_time_min'))}", "info"))
    if listing.get("winter_transit_reliability_score") is not None:
        badge_items.append((f"Giao thông mùa đông {format_compact_score(listing.get('winter_transit_reliability_score'))}", "info"))
    if listing.get("foreign_resident_support_score") is not None:
        badge_items.append((f"Hỗ trợ người nước ngoài {format_compact_score(listing.get('foreign_resident_support_score'))}", "good"))
    render_badges(badge_items)

    key = f"select_{message_index}_{listing['id']}"
    if key not in st.session_state:
        st.session_state[key] = listing["id"] in st.session_state["selected_listings"]
    selected = st.checkbox("Thêm vào so sánh", key=key)
    toggle_listing(selected, listing["id"])

    details_col, gallery_col = st.columns([1.35, 1], gap="large")
    with details_col:
        render_metric_grid(
            [
                ("Giá thuê", rent),
                ("Diện tích", format_area(listing.get("area_m2"))),
                ("Năm xây", format_year(listing.get("construction_year"))),
                ("Đi bộ tới ga", format_minutes(walk_minutes)),
            ]
        )
        enrichment_metrics = build_enrichment_metric_items(listing, language=language)
        if enrichment_metrics:
            section_label = "Ngữ cảnh khu vực"
            st.markdown(f'<div class="section-label">{escape(section_label)}</div>', unsafe_allow_html=True)
            render_metric_grid(enrichment_metrics, columns_per_row=3)

        metadata_bits: list[str] = []
        if listing.get("management_fee") is not None:
            metadata_bits.append(f"Phí quản lý: {format_currency(listing.get('management_fee'))}")
        if listing.get("floor") is not None:
            metadata_bits.append(f"Tầng: {listing['floor']}")
        if listing.get("pet_allowed") is True:
            metadata_bits.append("Cho nuôi thú cưng")
        if listing.get("foreigner_friendly") is True:
            metadata_bits.append("Hỗ trợ người nước ngoài")
        metadata_bits.extend(build_enrichment_note_bits(listing, language=language))
        if metadata_bits:
            st.markdown(
                f'<div class="compact-note">{" · ".join(escape(bit) for bit in metadata_bits)}</div>',
                unsafe_allow_html=True,
            )

        if listing.get("source_validated") is True and listing.get("source_url"):
            source_name = listing.get("source_name") or "nguồn"
            link_label = f"Mở nguồn {source_name}"
            st.link_button(link_label, listing["source_url"])
        st.markdown(
            f'<div class="compact-note">{escape(listing_summary(listing, language=language))}</div>',
            unsafe_allow_html=True,
        )

    with gallery_col:
        gallery_label = "Hình ảnh"
        st.markdown(f'<div class="section-label">{escape(gallery_label)}</div>', unsafe_allow_html=True)
        render_image_gallery(
            listing,
            gallery_key=f"listing_{message_index}_{listing['id']}",
            max_width_px=320,
            language=language,
        )


def render_pagination_controls(total_items: int, message_index: int, *, language: str) -> tuple[int, int]:
    total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
    page_key = f"page_{message_index}"
    current_page = min(max(int(st.session_state.get(page_key, 1)), 1), total_pages)
    st.session_state[page_key] = current_page

    start = (current_page - 1) * PAGE_SIZE
    end = min(start + PAGE_SIZE, total_items)

    nav_left, nav_center, nav_right = st.columns([1, 2, 1])
    with nav_left:
        previous_label = "5 kết quả trước"
        if st.button(
            previous_label,
            key=f"page_prev_{message_index}",
            disabled=current_page == 1,
            use_container_width=True,
        ):
            st.session_state[page_key] = current_page - 1
            st.rerun()
    with nav_center:
        st.caption(f"Đang hiển thị {start + 1}-{end} trong {total_items} kết quả | Trang {current_page}/{total_pages}")
    with nav_right:
        next_label = "5 kết quả tiếp"
        if st.button(
            next_label,
            key=f"page_next_{message_index}",
            disabled=current_page == total_pages,
            use_container_width=True,
        ):
            st.session_state[page_key] = current_page + 1
            st.rerun()

    return start, end


def render_listings(listings: list[dict[str, Any]], message_index: int, *, language: str) -> None:
    if not listings:
        return
    section_label = "Danh sách đã xếp hạng"
    st.markdown(f'<div class="section-label">{escape(section_label)}</div>', unsafe_allow_html=True)
    start, end = render_pagination_controls(len(listings), message_index, language=language)
    for listing in listings[start:end]:
        with st.container(border=True):
            render_listing_card(listing, message_index, language=language)


def render_selected_listing_list() -> None:
    known_listings = collect_known_listings()
    selected_ids = st.session_state["selected_listings"]
    st.subheader("Căn đã chọn")
    if not selected_ids:
        st.caption("Chọn ít nhất hai căn để so sánh.")
        return

    for listing_id in selected_ids:
        listing = known_listings.get(listing_id, {})
        title = listing.get("title") or listing_id
        summary_parts = [
            format_currency(listing.get("rent") or listing.get("rent_yen")),
            format_area(listing.get("area_m2")),
            format_year(listing.get("construction_year")),
        ]
        st.markdown(f"**{escape(str(title))}**")
        st.caption(f"{listing_id} · " + " · ".join(summary_parts))


def render_comparison(comparison: list[dict[str, Any]]) -> None:
    if not comparison:
        return
    known_listings = collect_known_listings()
    st.markdown("**So sánh**")
    columns = st.columns(len(comparison))
    for column, item in zip(columns, comparison):
        listing = known_listings.get(str(item["id"]), {})
        title = item.get("title") or listing.get("title", "")
        comparison_listing = {**listing, **item}
        with column:
            with st.container(border=True):
                st.markdown(f"**{item['id']}**")
                if title:
                    st.caption(title)

                render_metric_grid(
                    [
                        ("Giá thuê", format_currency(item.get("rent_yen"))),
                        ("Phí quản lý", format_currency(item.get("management_fee"))),
                        ("Diện tích", format_area(item.get("area_m2"))),
                        ("Đi bộ tới ga", format_minutes(item.get("walk_min"))),
                        ("Năm xây", format_year(item.get("construction_year"))),
                        ("An toàn", format_score(item.get("overall_safety_score"))),
                    ]
                )

                render_image_gallery(comparison_listing, gallery_key=f"compare_{item['id']}", max_width_px=220, language="vi")

                st.write("Điểm mạnh")
                for pro in item.get("pros", []):
                    st.write(f"- {pro}")
                st.write("Điểm cần cân nhắc")
                for con in item.get("cons", []):
                    st.write(f"- {con}")


def render_export_file(file_path: str | None, message_index: int) -> None:
    resolved = resolve_workspace_path(file_path)
    if not resolved or not resolved.exists():
        return

    st.markdown("**Tệp xuất**")
    with resolved.open("rb") as handle:
        st.download_button(
            label=f"Tải xuống {resolved.name}",
            data=handle.read(),
            file_name=resolved.name,
            mime="application/octet-stream",
            key=f"download_{message_index}_{resolved.name}",
        )


def render_message(message: dict[str, Any], message_index: int, *, show_meta: bool) -> None:
    with st.chat_message(message["role"]):
        language = "vi"
        st.markdown(message["content"])
        render_listings(message.get("listings", []), message_index, language=language)
        render_comparison(message.get("comparison", []))
        render_export_file(message.get("file"), message_index)
        meta = message.get("meta")
        if show_meta and meta:
            with st.expander("Thông tin kỹ thuật", expanded=False):
                st.json(meta, expanded=False)


def render_messages(*, show_meta: bool) -> None:
    for message_index, message in enumerate(st.session_state["messages"]):
        render_message(message, message_index, show_meta=show_meta)


def build_compare_prompt() -> str:
    selected = st.session_state["selected_listings"]
    if len(selected) < 2:
        return ""
    return "So sánh " + " và ".join(selected)


def render_sidebar(config: AppConfig) -> tuple[int, str]:
    with st.sidebar:
        st.subheader("Tùy chọn tìm kiếm")
        top_k = st.number_input("Số kết quả tối đa", min_value=1, max_value=20, value=config.default_top_k)
        output_format = st.selectbox("Định dạng phản hồi", options=["chat", "json", "csv", "pdf"], index=0)

        st.divider()
        render_selected_listing_list()

        compare_prompt = build_compare_prompt()
        if st.button("So sánh các căn đã chọn", disabled=not compare_prompt, use_container_width=True):
            st.session_state["pending_chat_input"] = compare_prompt
        if st.button("Bỏ chọn tất cả", disabled=not st.session_state["selected_listings"], use_container_width=True):
            clear_selected_listings()
            st.rerun()

        st.divider()
        with st.expander("Thông tin chạy", expanded=config.app_dev_mode):
            st.text_input("Model chat", value=config.llm_chat_model, disabled=True)
            st.text_input("URL nền", value=config.llm_base_url or "", disabled=True)
            st.text_input("Nguồn tìm kiếm", value=config.search_provider, disabled=True)
            if not config.llm_api_key:
                st.warning("Chưa tải LLM_API_KEY. Ứng dụng sẽ dùng chế độ dự phòng khi phù hợp.")

    return int(top_k), output_format


def append_message(
    *,
    role: str,
    content: str,
    listings: list[dict[str, Any]] | None = None,
    comparison: list[dict[str, Any]] | None = None,
    file: str | None = None,
    meta: dict[str, Any] | None = None,
    language: str = "vi",
) -> None:
    st.session_state["messages"].append(
        {
            "role": role,
            "content": content,
            "listings": listings or [],
            "comparison": comparison or [],
            "file": file,
            "meta": meta or {},
            "language": language,
        }
    )


def submit_user_message(user_input: str, top_k: int, output_format: str) -> None:
    agent_service = get_agent_service()

    request = AgentRequest(
        session_id=st.session_state["session_id"],
        message=user_input,
        input_type="text",
        context=RequestContext(
            previous_filters=st.session_state["previous_filters"],
            selected_listings=st.session_state["selected_listings"],
            conversation_history=build_conversation_history(),
            recent_listings=st.session_state["recent_listings"],
        ),
        options=RequestOptions(top_k=top_k, output_format=output_format),
    )

    response = agent_service.handle_request(request)
    st.session_state["previous_filters"] = response.data.filters_used
    response_listings = [listing.model_dump() for listing in response.data.listings]
    response_language = "vi"
    response_meta = response.meta.model_dump()
    display_listings = response_listings
    response_content = response.reply
    if response.data.filters_used.get("search_more"):
        if response_listings:
            merged_listings, added_count = merge_additional_listings(
                st.session_state["recent_listings"],
                response_listings,
                max_new=5,
            )
            st.session_state["recent_listings"] = merged_listings
            response_meta["added_listings"] = added_count
            response_meta["total_displayed_listings"] = len(merged_listings)
            response_content = build_search_more_reply(
                added_count=added_count,
                total_count=len(merged_listings),
                language=response_language,
            )
            display_listings = merged_listings
        else:
            response_meta["added_listings"] = 0
            response_meta["total_displayed_listings"] = len(st.session_state["recent_listings"])
            response_content = build_search_more_reply(
                added_count=0,
                total_count=len(st.session_state["recent_listings"]),
                language=response_language,
            )
            display_listings = st.session_state["recent_listings"]
    elif response_listings:
        st.session_state["recent_listings"] = response_listings
    if response.data.comparison:
        st.session_state["selected_listings"] = sorted({item.id for item in response.data.comparison})
        for key in list(st.session_state.keys()):
            if key.startswith("select_"):
                del st.session_state[key]

    append_message(
        role="assistant",
        content=response_content,
        listings=display_listings,
        comparison=[item.model_dump() for item in response.data.comparison],
        file=response.data.file,
        meta=response_meta,
        language=response_language,
    )
    if response.data.filters_used.get("search_more") and display_listings:
        message_index = len(st.session_state["messages"]) - 1
        st.session_state[f"page_{message_index}"] = max(1, math.ceil(len(display_listings) / PAGE_SIZE))


def queue_user_message(user_input: str, top_k: int, output_format: str) -> None:
    append_message(role="user", content=user_input)
    st.session_state["pending_request"] = {
        "user_input": user_input,
        "top_k": top_k,
        "output_format": output_format,
    }


def process_pending_request() -> None:
    pending_request = st.session_state.get("pending_request")
    if not pending_request:
        return
    with st.chat_message("assistant"):
        with st.status("Đang tìm và xếp hạng nhà thuê...", expanded=True) as status:
            st.write("Đang đọc điều kiện thuê nhà")
            st.write("Đang tìm trong các nguồn hiện có")
            st.write("Đang xếp hạng kết quả và chuẩn bị phản hồi")
            submit_user_message(
                pending_request["user_input"],
                top_k=int(pending_request["top_k"]),
                output_format=str(pending_request["output_format"]),
            )
            status.update(label="Đã tìm xong", state="complete", expanded=False)
    st.session_state["pending_request"] = None
    st.rerun()


def main() -> None:
    initialize_session()
    config = AppConfig()
    inject_custom_css()

    render_app_header()

    top_k, output_format = render_sidebar(config)
    render_messages(show_meta=config.app_dev_mode)
    if not st.session_state["messages"] and not st.session_state.get("pending_request"):
        render_empty_state()
    process_pending_request()

    pending_chat_input = st.session_state.pop("pending_chat_input", None)
    user_input = pending_chat_input or st.chat_input(
        "Nhập nhu cầu thuê nhà, yêu cầu so sánh căn đã chọn, hoặc xuất kết quả..."
    )
    if not user_input:
        return

    queue_user_message(user_input, top_k=top_k, output_format=output_format)
    st.rerun()


if __name__ == "__main__":
    main()
