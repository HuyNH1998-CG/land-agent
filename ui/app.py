from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from japan_rental_agent.agent import RentalAgentService
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest, RequestContext, RequestOptions


st.set_page_config(page_title="Japan Rental Agent", layout="wide")


def get_agent_service() -> RentalAgentService:
    return RentalAgentService(config=AppConfig())


def initialize_session() -> None:
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("selected_listings", [])
    st.session_state.setdefault("previous_filters", {})


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


def listing_label(listing: dict[str, Any]) -> str:
    rent = listing.get("rent") or listing.get("rent_yen") or "n/a"
    layout = listing.get("layout") or "layout?"
    station = listing.get("nearest_station") or listing.get("station") or "station?"
    return f"{listing['id']} | {layout} | {rent} JPY | {station}"


def collect_known_listings() -> dict[str, dict[str, Any]]:
    known: dict[str, dict[str, Any]] = {}
    for message in st.session_state["messages"]:
        for listing in message.get("listings", []):
            known[str(listing["id"])] = listing
    return known


def render_floor_plan(listing: dict[str, Any]) -> None:
    floor_plan_asset = resolve_workspace_path(listing.get("floor_plan_asset"))
    if not floor_plan_asset or not floor_plan_asset.exists():
        st.caption("No floor plan available")
        return

    if floor_plan_asset.suffix.lower() == ".svg":
        svg_text = read_svg_text(floor_plan_asset)
        if svg_text:
            st.markdown(svg_text, unsafe_allow_html=True)
            return

    st.image(str(floor_plan_asset), use_container_width=True)


def toggle_listing(selected: bool, listing_id: str) -> None:
    current = set(st.session_state["selected_listings"])
    if selected:
        current.add(listing_id)
    else:
        current.discard(listing_id)
    st.session_state["selected_listings"] = sorted(current)


def render_listing_card(listing: dict[str, Any], message_index: int) -> None:
    header_left, header_right = st.columns([3, 1])
    with header_left:
        station = listing.get("nearest_station") or listing.get("station") or "Unknown station"
        st.markdown(f"**{listing['title']}**")
        st.caption(
            f"{listing.get('city', '')} {listing.get('ward', '')} | "
            f"{listing.get('layout', 'n/a')} | "
            f"{listing.get('rent') or listing.get('rent_yen') or 'n/a'} JPY | "
            f"{station} ({listing.get('distance_to_station_min') or listing.get('walk_min') or 'n/a'} min)"
        )
    with header_right:
        key = f"select_{message_index}_{listing['id']}"
        default_selected = listing["id"] in st.session_state["selected_listings"]
        selected = st.checkbox("Select", value=default_selected, key=key)
        toggle_listing(selected, listing["id"])

    details_col, plan_col = st.columns([1.35, 1], gap="large")
    with details_col:
        metric_cols = st.columns(4)
        metric_cols[0].metric("Rent", f"{listing.get('rent') or listing.get('rent_yen') or 'n/a'}")
        metric_cols[1].metric("Area", f"{listing.get('area_m2') or 'n/a'} m2")
        metric_cols[2].metric("Age", f"{listing.get('building_age') or 'n/a'} yr")
        metric_cols[3].metric("Score", f"{listing.get('score', 'n/a')}")

        traits: list[str] = []
        if listing.get("pet_allowed") is True:
            traits.append("pet allowed")
        if listing.get("foreigner_friendly") is True:
            traits.append("foreigner friendly")
        if listing.get("commute_time_min") is not None:
            traits.append(f"commute {listing['commute_time_min']} min")
        if traits:
            st.caption(" | ".join(traits))

        score_breakdown = listing.get("score_breakdown")
        if isinstance(score_breakdown, dict) and score_breakdown:
            st.json(score_breakdown, expanded=False)

    with plan_col:
        st.caption("Floor plan")
        render_floor_plan(listing)


def render_listings(listings: list[dict[str, Any]], message_index: int) -> None:
    if not listings:
        return
    st.markdown("**Listings**")
    for listing in listings:
        with st.container(border=True):
            render_listing_card(listing, message_index)


def render_comparison(comparison: list[dict[str, Any]]) -> None:
    if not comparison:
        return
    known_listings = collect_known_listings()
    st.markdown("**Comparison**")
    columns = st.columns(len(comparison))
    for column, item in zip(columns, comparison):
        listing = known_listings.get(str(item["id"]), {})
        title = item.get("title") or listing.get("title", "")
        floor_plan_asset = item.get("floor_plan_asset") or listing.get("floor_plan_asset")
        with column:
            st.markdown(f"**{item['id']}**")
            if title:
                st.caption(title)
            if floor_plan_asset:
                render_floor_plan({"floor_plan_asset": floor_plan_asset})
            st.write("Pros")
            for pro in item.get("pros", []):
                st.write(f"- {pro}")
            st.write("Cons")
            for con in item.get("cons", []):
                st.write(f"- {con}")


def render_export_file(file_path: str | None, message_index: int) -> None:
    resolved = resolve_workspace_path(file_path)
    if not resolved or not resolved.exists():
        return

    st.markdown("**Export**")
    with resolved.open("rb") as handle:
        st.download_button(
            label=f"Download {resolved.name}",
            data=handle.read(),
            file_name=resolved.name,
            mime="application/octet-stream",
            key=f"download_{message_index}_{resolved.name}",
        )


def render_message(message: dict[str, Any], message_index: int) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        render_listings(message.get("listings", []), message_index)
        render_comparison(message.get("comparison", []))
        render_export_file(message.get("file"), message_index)
        meta = message.get("meta")
        if meta:
            with st.expander("Meta", expanded=False):
                st.json(meta, expanded=False)


def render_messages() -> None:
    for message_index, message in enumerate(st.session_state["messages"]):
        render_message(message, message_index)


def build_compare_prompt() -> str:
    selected = st.session_state["selected_listings"]
    if len(selected) < 2:
        return ""
    return "Compare " + " and ".join(selected)


def render_sidebar(config: AppConfig) -> tuple[int, str]:
    with st.sidebar:
        st.subheader("Run Options")
        top_k = st.number_input("Top K", min_value=1, max_value=20, value=config.default_top_k)
        output_format = st.selectbox("Output format", options=["chat", "json", "csv", "pdf"], index=0)

        st.divider()
        st.subheader("Selected Listings")
        selected = st.session_state["selected_listings"]
        if selected:
            for listing_id in selected:
                st.code(listing_id)
        else:
            st.caption("No listings selected")

        compare_prompt = build_compare_prompt()
        if st.button("Compare Selected", disabled=not compare_prompt, use_container_width=True):
            st.session_state["pending_chat_input"] = compare_prompt
        if st.button("Clear Selected", disabled=not selected, use_container_width=True):
            st.session_state["selected_listings"] = []
            st.rerun()

        st.divider()
        st.subheader("LLM Config")
        st.text_input("Chat model", value=config.llm_chat_model, disabled=True)
        st.text_input("Base URL", value=config.llm_base_url or "", disabled=True)
        if not config.llm_api_key:
            st.warning("LLM_API_KEY is not loaded. Fallback mode will be used where applicable.")

    return int(top_k), output_format


def append_message(
    *,
    role: str,
    content: str,
    listings: list[dict[str, Any]] | None = None,
    comparison: list[dict[str, Any]] | None = None,
    file: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    st.session_state["messages"].append(
        {
            "role": role,
            "content": content,
            "listings": listings or [],
            "comparison": comparison or [],
            "file": file,
            "meta": meta or {},
        }
    )


def submit_user_message(user_input: str, top_k: int, output_format: str) -> None:
    agent_service = get_agent_service()
    append_message(role="user", content=user_input)

    request = AgentRequest(
        session_id=st.session_state["session_id"],
        message=user_input,
        input_type="text",
        context=RequestContext(
            previous_filters=st.session_state["previous_filters"],
            selected_listings=st.session_state["selected_listings"],
        ),
        options=RequestOptions(top_k=top_k, output_format=output_format),
    )

    response = agent_service.handle_request(request)
    st.session_state["previous_filters"] = response.data.filters_used

    append_message(
        role="assistant",
        content=response.reply,
        listings=[listing.model_dump() for listing in response.data.listings],
        comparison=[item.model_dump() for item in response.data.comparison],
        file=response.data.file,
        meta=response.meta.model_dump(),
    )


def main() -> None:
    initialize_session()
    config = AppConfig()

    st.title("Japan Rental Agent")
    st.caption("Chat-driven rental search UI with listing cards, comparison, export, and floor-plan preview.")

    top_k, output_format = render_sidebar(config)
    render_messages()

    pending_chat_input = st.session_state.pop("pending_chat_input", None)
    user_input = pending_chat_input or st.chat_input(
        "Describe the rental home you want, ask to compare selected listings, or export the results..."
    )
    if not user_input:
        return

    submit_user_message(user_input, top_k=top_k, output_format=output_format)
    st.rerun()


if __name__ == "__main__":
    main()
