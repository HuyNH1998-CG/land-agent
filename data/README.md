# Data Directory

This folder stores local development datasets, Chroma indexes, floor-plan assets, and generated exports.

The production-oriented default path is public search:

```powershell
$env:SEARCH_PROVIDER="web"
```

Local files in this directory are still useful for tests and offline development:

- `rental_listings_demo.csv`: synthetic Sapporo rental listings
- `ward_hazard_score.csv`: local hazard/safety reference data
- `housing_context_by_city.csv`: local city context reference data
- `station_access_reference.csv`: local station/access reference data
- `floor_plan_reference.csv`: listing-to-floor-plan mapping
- `floor_plans/*.svg`: generated demo floor-plan images
- `chroma/`: persisted local Chroma collections after running the seed script
- `exports/`: generated export files

Use local data explicitly with:

```powershell
$env:SEARCH_PROVIDER="local"
python .\scripts\generate_sapporo_mock_data.py
python .\scripts\seed_chroma.py
```
