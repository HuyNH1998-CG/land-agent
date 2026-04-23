from __future__ import annotations

from typing import Any


class AreaEnrichmentTool:
    """Placeholder enrichment tool contract."""

    name = "enrichment"

    def execute(self, listings: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        return {
            "enriched": listings,
            "context_used": context,
        }

