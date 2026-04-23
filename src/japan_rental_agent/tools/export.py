from __future__ import annotations

from typing import Any


class ExportTool:
    """Placeholder export tool contract."""

    name = "export"

    def execute(self, listings: list[dict[str, Any]], output_format: str) -> dict[str, Any]:
        return {
            "file_url": None,
            "file_type": output_format,
            "count": len(listings),
        }

