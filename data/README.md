# Data Directory

This folder stores local datasets and generated exports.

Recommended files for the MVP:

- `rental_listings_demo.csv`
- `ward_hazard_score.csv`
- `housing_context_by_city.csv`
- `station_access_reference.csv`

Current mock package:

- all geographic records are centered on `Sapporo, Hokkaido`
- data is synthetic but intentionally shaped to resemble rental-search inputs
- use it for local development, ranking experiments, and UI demos
- the listing dataset is expanded to `264` total rows

Additional local assets:

- `floor_plan_reference.csv`: maps listing IDs to reusable floor plan assets
- `floor_plans/*.svg`: simple mock floor plan images by layout type
- `chroma/`: local persisted Chroma collections after running the seed script

Generated outputs should be written to `data/exports/`.
