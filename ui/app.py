from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from japan_rental_agent.agent import RentalAgentService
from japan_rental_agent.config import AppConfig
from japan_rental_agent.contracts import AgentRequest, RequestContext, RequestOptions


st.set_page_config(
    page_title="Japan Rental Agent",
    layout="wide",
)


def get_agent_service() -> RentalAgentService:
    return RentalAgentService(config=AppConfig())


def initialize_session() -> None:
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("selected_listings", [])
    st.session_state.setdefault("previous_filters", {})


def render_messages() -> None:
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            listings = message.get("listings")
            if listings:
                st.dataframe(listings, use_container_width=True)


def main() -> None:
    initialize_session()
    config = AppConfig()
    agent_service = get_agent_service()

    st.title("Japan Rental Agent")
    st.caption("Base project skeleton. Agent logic and real data access are not implemented yet.")

    with st.sidebar:
        st.subheader("Run Options")
        top_k = st.number_input("Top K", min_value=1, max_value=20, value=config.default_top_k)
        output_format = st.selectbox("Output format", options=["chat", "json", "csv", "pdf"], index=0)
        st.divider()
        st.subheader("LLM Config")
        st.text_input("Chat model", value=config.llm_chat_model, disabled=True)
        st.text_input("Base URL", value=config.llm_base_url or "", disabled=True)
        if not config.llm_api_key:
            st.warning("`LLM_API_KEY` is not loaded. This is fine for the current skeleton.")

    render_messages()

    user_input = st.chat_input("Describe the rental home you want to find...")
    if not user_input:
        return

    st.session_state["messages"].append({"role": "user", "content": user_input})

    request = AgentRequest(
        session_id=st.session_state["session_id"],
        message=user_input,
        input_type="text",
        context=RequestContext(
            previous_filters=st.session_state["previous_filters"],
            selected_listings=st.session_state["selected_listings"],
        ),
        options=RequestOptions(
            top_k=int(top_k),
            output_format=output_format,
        ),
    )

    response = agent_service.handle_request(request)
    st.session_state["previous_filters"] = response.data.filters_used

    assistant_message = {
        "role": "assistant",
        "content": response.reply,
        "listings": [listing.model_dump() for listing in response.data.listings],
    }
    st.session_state["messages"].append(assistant_message)
    st.rerun()


if __name__ == "__main__":
    main()
