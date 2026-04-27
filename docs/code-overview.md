# Code Overview

Tài liệu này mô tả ngắn gọn các phần code hiện có của Japan Rental Agent.

## Trạng Thái Hiện Tại

Project đã có luồng agent chạy được từ UI tới LangGraph và tool layer:

- UI chat bằng Streamlit.
- Contract chung giữa UI và agent.
- LangGraph workflow cho search, clarification, enrichment, ranking, compare, export và error handling.
- OpenAI-compatible LLM client.
- Public search provider qua LangChain DDGS cho listing thật.
- Public context provider cho nhóm dữ liệu e-Stat, MLIT, hazard/safety và regional indicators.
- Local CSV/Chroma mode cho test và offline development.

## `ui/app.py`

Entrypoint của Streamlit UI.

Nhiệm vụ chính:

- hiển thị chat interface
- gửi `AgentRequest` vào `RentalAgentService`
- lưu `recent_listings` để các lượt chat sau có thể so sánh kết quả vừa tìm
- hiển thị listing card, link nguồn, sơ đồ nhà, comparison và file export
- chỉ hiển thị metadata khi bật dev mode

## `src/japan_rental_agent/config.py`

Quản lý cấu hình runtime bằng `pydantic-settings`.

Các nhóm cấu hình chính:

- LLM: `LLM_API_KEY`, `LLM_CHAT_MODEL`, `LLM_BASE_URL`, `LLM_EMBEDDING_MODEL`
- Search: `SEARCH_PROVIDER`, `WEB_SEARCH_REGION`, `WEB_SEARCH_MAX_RESULTS`
- Public data: `ESTAT_APP_ID`, `MLIT_API_KEY`, `PUBLIC_CONTEXT_ENABLED`
- Local data: `data_dir`, `export_dir`, Chroma path

## `src/japan_rental_agent/contracts/api.py`

Định nghĩa schema trao đổi giữa UI và agent:

- `AgentRequest`
- `AgentResponse`
- `AgentData`
- `AgentMeta`
- `AgentError`

Đây là contract ổn định để UI, agent và tool layer không phụ thuộc trực tiếp vào implementation nội bộ của nhau.

## `src/japan_rental_agent/domain/models.py`

Chứa các model nghiệp vụ:

- `Listing`
- `ListingScoreBreakdown`
- `SearchFilters`
- `ComparisonItem`

`Listing` hiện hỗ trợ cả dữ liệu local và dữ liệu public search, bao gồm `source_url`, `source_name`, `source_snippet`, `extraction_confidence` và `context_sources`.

## `src/japan_rental_agent/agent/`

Chứa LangGraph orchestration.

Các file chính:

- `state.py`: định nghĩa `RentalAgentState`, bao gồm constraint, kết quả tìm kiếm, kết quả ranking, recent listings và compare state.
- `graph.py`: nối các node thành workflow.
- `service.py`: application service mà UI gọi vào.
- `llm.py`: OpenAI-compatible client wrapper.
- `nodes/`: implementation từng node trong graph.

Luồng chính:

1. input
2. intent extraction
3. clarification nếu thiếu dữ liệu
4. listing search
5. enrichment + ranking
6. response
7. error/retry nếu có lỗi

## `src/japan_rental_agent/tools/`

Tool layer được agent gọi từ các node.

Các tool chính:

- `parser.py`: parse intent, constraint, compare criteria và language.
- `search.py`: tìm listing bằng LangChain DDGS public search hoặc CSV/Chroma khi `SEARCH_PROVIDER=local`.
- `enrichment.py`: bổ sung public context hoặc local context.
- `ranking.py`: chấm điểm và sắp xếp listing.
- `compare.py`: so sánh listing theo nhiều tiêu chí, resolve được từ ID, tên nhà hoặc `recent_listings`.
- `export.py`: export kết quả sang file.
- `support.py`: helper dùng chung cho parsing, normalize, CSV local và Chroma.

## `src/japan_rental_agent/data/`

Data access layer.

Các phần chính:

- `repositories.py`: registry cho local CSV files.
- `vector_store.py`: Chroma vector store cho local mode.
- `public_sources.py`: LangChain DDGS web search, provider public context, wrapper e-Stat API và wrapper MLIT API.

## `tests/`

Các nhóm test hiện có:

- smoke import và service initialization
- agent flow
- data seed
- tool behavior
- public source provider behavior
- compare state/use cases

Test dùng `SEARCH_PROVIDER=local` khi cần dữ liệu deterministic; public provider được test bằng fake search client để không phụ thuộc mạng.

## Tài Liệu Liên Quan

- `README.md`: setup nhanh và trạng thái project.
- `docs/usage-guide.md`: lệnh cài đặt, test, chạy hệ thống và luồng chat mẫu.
- `docs/public-data-integration.md`: chiến lược tích hợp public data, LangChain DDGS, e-Stat và MLIT.
- `docs/compare-state-cases.md`: các case state cho tool so sánh.
