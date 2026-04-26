from __future__ import annotations

from typing import Any

from japan_rental_agent.agent.dependencies import AgentDependencies
from japan_rental_agent.agent.state import RentalAgentState
from japan_rental_agent.agent.utils import normalize_listings


def make_response_node(dependencies: AgentDependencies):
    def response_node(state: RentalAgentState) -> RentalAgentState:
        if state.get("response_payload"):
            return {}

        tool_trace = list(state.get("tool_trace", []))
        intent_label = state.get("intent_label", "search")
        raw_listings = state.get("ranked_results") or state.get("search_results") or []
        top_k = state.get("top_k", 5)
        normalized_listings = normalize_listings(raw_listings, top_k=top_k)
        comparison_results: list[dict[str, Any]] = list(state.get("comparison_results", []))
        exported_file = state.get("exported_file")

        if intent_label == "compare":
            selected_listing_ids = state.get("selected_listings", [])
            comparison_payload = dependencies.comparison_tool.execute(selected_listing_ids)
            comparison_results = comparison_payload.get("comparison", [])
            tool_trace.append(dependencies.comparison_tool.name)
            comparison_count = len(comparison_results)
            if comparison_count == 0:
                reply = "Tôi không tìm thấy đủ dữ liệu để so sánh các căn đã chọn. Hãy kiểm tra lại mã căn hộ hoặc chọn lại danh sách cần so sánh."
            elif comparison_count == 1:
                title = comparison_results[0].get("title") or comparison_results[0].get("id")
                reply = f"Tôi chỉ tìm thấy một căn hợp lệ để so sánh: {title}. Hãy chọn thêm ít nhất một căn nữa."
            else:
                labels = [str(item.get("title") or item.get("id")) for item in comparison_results[:3]]
                reply = f"Tôi đã chuẩn bị bảng so sánh cho {comparison_count} căn: {', '.join(labels)}."

            return {
                "tool_trace": tool_trace,
                "comparison_results": comparison_results,
                "exported_file": exported_file,
                "response_payload": {
                    "status": "success",
                    "reply": reply,
                    "data": {
                        "filters_used": {
                            "operation": "compare",
                            "selected_listings": state.get("selected_listings", []),
                        },
                        "listings": [],
                        "comparison": comparison_results,
                        "file": None,
                        "missing_fields": [],
                    },
                    "meta": {
                        "tool_used": tool_trace,
                        "confidence": state.get("llm_confidence"),
                        "processing_time_ms": 0,
                    },
                    "error": None,
                },
            }

        export_format = state.get("selected_output_format", "chat")
        export_candidates = raw_listings[:top_k]
        if export_format != "chat" and export_candidates:
            export_payload = dependencies.export_tool.execute(export_candidates, export_format)
            exported_file = export_payload.get("file_url")
            tool_trace.append(dependencies.export_tool.name)

        draft = dependencies.agent_model.draft_response(
            raw_input=state.get("raw_input", ""),
            filters_used=state.get("filters_used", {}),
            listings=normalized_listings,
            output_format=export_format,
            tool_trace=tool_trace,
        )
        tool_trace.append("llm.response")

        return {
            "tool_trace": tool_trace,
            "comparison_results": comparison_results,
            "exported_file": exported_file,
            "response_payload": {
                "status": "success",
                "reply": draft.reply,
                "data": {
                    "filters_used": state.get("filters_used", {}),
                    "listings": normalized_listings,
                    "comparison": comparison_results,
                    "file": exported_file,
                    "missing_fields": [],
                },
                "meta": {
                    "tool_used": tool_trace,
                    "confidence": draft.confidence or state.get("llm_confidence"),
                    "processing_time_ms": 0,
                },
                "error": None,
            },
        }

    return response_node
