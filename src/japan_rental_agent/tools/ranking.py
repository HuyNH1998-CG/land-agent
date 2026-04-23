from __future__ import annotations

from typing import Any


class RankingTool:
    """Placeholder ranking tool contract."""

    name = "ranking"

    def execute(self, listings: list[dict[str, Any]], preferences: dict[str, Any]) -> dict[str, Any]:
        return {
            "ranked": listings,
            "preferences_used": preferences,
        }

