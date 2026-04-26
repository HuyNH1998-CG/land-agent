# Japan Rental Agent

Base structure for a chat agent that helps users find rental housing in Japan.

## Current status

This repository currently provides:

- project layout for `ui`, `agent`, `tools`, and `data`
- shared request/response contracts
- LangGraph workflow skeleton
- local Chroma vector store integration and seeding utilities
- Streamlit demo entrypoint
- placeholder tool implementations that follow the expected interfaces

Business logic is intentionally not implemented yet.

## Project layout

```text
.
|-- data/
|   |-- exports/
|   `-- README.md
|-- src/japan_rental_agent/
|   |-- agent/
|   |-- contracts/
|   |-- data/
|   |-- domain/
|   `-- tools/
|-- tests/
`-- ui/app.py
```

## Environment variables

Expected keys:

- `LLM_API_KEY`
- `LLM_CHAT_MODEL`
- `LLM_BASE_URL`
- `LLM_EMBEDDING_MODEL`

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## Run Streamlit UI

```bash
streamlit run ui/app.py
```

## Generate local mock data

```bash
python scripts/generate_sapporo_mock_data.py
```

This produces:

- `data/rental_listings_demo.csv` with 264 Sapporo listings
- `data/floor_plan_reference.csv`
- shared SVG floor plans under `data/floor_plans/`

## Seed Chroma locally

```bash
python scripts/seed_chroma.py
```

Seeded collections are stored under `data/chroma/`.

## Next implementation steps

1. Implement real query parsing and clarification rules.
2. Connect local CSV or SQLite datasets.
3. Implement search, enrichment, ranking, compare, and export logic.
4. Wire the chosen Gemini-compatible model client into the agent flow.
