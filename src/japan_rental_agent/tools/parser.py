from __future__ import annotations

from typing import Any


class QueryParserTool:
    """Placeholder parser that preserves the incoming message."""

    name = "parser"

    def execute(self, message: str) -> dict[str, Any]:
        return {
            "message": message.strip(),
            "constraints": {},
            "missing_fields": [],
        }

