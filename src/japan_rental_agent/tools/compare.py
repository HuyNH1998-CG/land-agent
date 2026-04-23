from __future__ import annotations


class ComparisonTool:
    """Placeholder comparison tool contract."""

    name = "compare"

    def execute(self, listing_ids: list[str]) -> dict[str, list[dict[str, object]]]:
        return {
            "comparison": [
                {
                    "id": listing_id,
                    "pros": [],
                    "cons": [],
                }
                for listing_id in listing_ids
            ]
        }

