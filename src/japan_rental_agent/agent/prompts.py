from __future__ import annotations

import json
from typing import Any


def _to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, indent=2, default=str)


def build_intent_extraction_prompt(
    *,
    message: str,
    previous_filters: dict[str, Any],
    selected_listings: list[str],
    output_format: str,
    parser_hints: dict[str, Any],
) -> str:
    return f"""Extract rental-search intent and constraints for a Japan housing assistant.

Rules:
- Prefer explicit user constraints from the current message.
- Use previous filters only when the user does not override them.
- Keep missing_fields limited to information genuinely needed before search.
- Output search-ready constraints only. Do not invent values.
- If the user asks to compare or export, set intent accordingly.
- The user-facing language preference is Vietnamese. This affects downstream replies, not the extracted fields.

Current user message:
{message}

Previous filters:
{_to_json(previous_filters)}

Selected listings:
{_to_json(selected_listings)}

Requested output format:
{output_format}

Parser hints:
{_to_json(parser_hints)}
"""


def build_clarification_prompt(
    *,
    raw_input: str,
    parsed_constraints: dict[str, Any],
    missing_fields: list[str],
    conversation_history: list[dict[str, str]],
) -> str:
    return f"""Write one short clarification question for a rental search assistant.

Rules:
- Ask only for the missing information.
- Keep it concise and natural.
- Preserve the user's existing constraints.
- Write the reply in Vietnamese unless the user explicitly requested another language.

User request:
{raw_input}

Parsed constraints:
{_to_json(parsed_constraints)}

Missing fields:
{_to_json(missing_fields)}

Conversation history:
{_to_json(conversation_history[-6:])}
"""


def build_ranking_plan_prompt(
    *,
    raw_input: str,
    parsed_constraints: dict[str, Any],
    search_results: list[dict[str, Any]],
    current_preferences: dict[str, Any],
) -> str:
    compact_results = search_results[:5]
    return f"""Choose ranking weights for rental listings.

Rules:
- Weights should reflect user priorities from the request.
- Return balanced defaults if the request is vague.
- Do not assume facts not present in the request or listings.
- The user-facing language preference is Vietnamese, but the output schema remains unchanged.

User request:
{raw_input}

Parsed constraints:
{_to_json(parsed_constraints)}

Current ranking preferences:
{_to_json(current_preferences)}

Top search results preview:
{_to_json(compact_results)}
"""


def build_response_prompt(
    *,
    raw_input: str,
    filters_used: dict[str, Any],
    listings: list[dict[str, Any]],
    output_format: str,
    tool_trace: list[str],
) -> str:
    compact_results = listings[:5]
    return f"""Write the assistant response for a rental search result.

Rules:
- Mention how many strong matches were found.
- Summarize the most important constraints used.
- If there are no results, say that clearly and suggest refining filters.
- Do not claim data that is not present.
- Keep the answer suitable for chat output.
- Write the reply in Vietnamese unless the user explicitly requested another language.

Original request:
{raw_input}

Filters used:
{_to_json(filters_used)}

Output format:
{output_format}

Tool trace:
{_to_json(tool_trace)}

Listing preview:
{_to_json(compact_results)}
"""


def build_error_prompt(
    *,
    raw_input: str,
    error_message: str,
    retry_count: int,
    last_failed_node: str | None,
) -> str:
    return f"""Write a short, user-friendly error message for a rental search assistant.

Rules:
- Be transparent that the request could not be completed.
- Suggest one practical next step.
- Avoid technical jargon unless needed.
- Write the reply in Vietnamese unless the user explicitly requested another language.

Original request:
{raw_input}

Error:
{error_message}

Retry count:
{retry_count}

Failed node:
{last_failed_node}
"""
