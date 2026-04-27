# Public Data Integration

This project now treats real public search as the default listing source.

## Listing Search

Default mode:

```powershell
$env:SEARCH_PROVIDER="web"
```

`ListingSearchTool` uses LangChain's `DuckDuckGoSearchResults(output_format="list")` integration over DDGS to search public real-estate pages across major Japanese portals:

- `suumo.jp`
- `homes.co.jp`
- `athome.co.jp`
- `chintai.net`
- `able.co.jp`
- `minimini.jp`

The tool normalizes search results into the existing listing schema:

- `id`
- `title`
- `rent_yen`
- `layout`
- `area_m2`
- `walk_min`
- `nearest_station`
- `source_url`
- `source_name`
- `source_snippet`
- `extraction_confidence`

Important: this is public search result aggregation, not scraping portal detail pages. Queries are sent per portal domain instead of one large `OR` query because DDGS is more reliable with focused `site:` searches.

## Local Dataset Mode

Local mock data is no longer the default path. It remains available for tests and offline development:

```powershell
$env:SEARCH_PROVIDER="local"
```

## Dataset 2: Housing and Land Survey

Provider:
- e-Stat Housing and Land Survey

Config:

```powershell
$env:ESTAT_APP_ID="<your e-Stat app id>"
```

Current integration:
- Adds provider metadata to enrichment context
- Collects public web-search context for the target area
- Provides an `EStatApiClient.get_stats_data()` wrapper for keyed API use

## Dataset 3: MLIT Real Estate / Land Context

Provider:
- MLIT Real Estate Information Library

Config:

```powershell
$env:MLIT_API_KEY="<your MLIT API key>"
```

Current integration:
- Adds MLIT market context to enrichment
- Provides wrappers for transaction price and land price point APIs
- Falls back to public search context when no key is configured

## Dataset 4: Hazard / Safety Context

Provider:
- MLIT and public hazard-map sources

Current integration:
- Uses the same LangChain DDGS integration to gather public hazard/safety references by area
- Keeps the old local hazard CSV only in `SEARCH_PROVIDER=local`

## Dataset 5: Regional Indicators

Provider:
- e-Stat Statistics Dashboard API / public regional indicators

Current integration:
- Adds regional indicator search context to enrichment
- Kept separate from ranking so missing data does not block search results

## Notes On Real Estate Company APIs

Most major Japanese rental portals do not expose open, unauthenticated listing APIs for general public use. The current implementation uses search discovery over public pages and keeps provider boundaries isolated so official partner APIs can be added later without changing the agent graph.
