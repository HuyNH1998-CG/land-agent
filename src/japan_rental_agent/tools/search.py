from __future__ import annotations

from typing import Any


class ListingSearchTool:
    """Placeholder search tool contract."""

    name = "search"

    def execute(self, filters: dict[str, Any]) -> dict[str, Any]:
        return {
            "results": [],
            "total": 0,
            "filters_used": filters,
        }

