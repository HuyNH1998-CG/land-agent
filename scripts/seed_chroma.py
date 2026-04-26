from __future__ import annotations

from japan_rental_agent.config import AppConfig
from japan_rental_agent.data import seed_all_datasets


def main() -> None:
    summaries = seed_all_datasets(AppConfig(), reset=True)
    for summary in summaries:
        print(f"{summary.collection_name}: {summary.record_count} records")


if __name__ == "__main__":
    main()
