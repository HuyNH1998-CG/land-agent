# Hướng Dẫn Sử Dụng

Tài liệu này tổng hợp các lệnh cần thiết để cài môi trường, chạy test, chạy hệ thống và kiểm tra luồng chat chính.

## 1. Cài Đặt Ban Đầu

### Cài Python Trên Windows

```powershell
winget install -e --id Python.Python.3.12
```

Kiểm tra Python và pip:

```powershell
python --version
python -m pip --version
```

Tạo virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Cài dependency của project:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## 2. Cấu Hình Runtime

Mặc định hệ thống dùng public web search qua LangChain `DuckDuckGoSearchResults`/DDGS để tìm kết quả thật:

```powershell
$env:SEARCH_PROVIDER="web"
$env:WEB_SEARCH_REGION="jp-jp"
$env:WEB_SEARCH_MAX_RESULTS="20"
```

Cấu hình model OpenAI-compatible:

```powershell
$env:LLM_API_KEY="<api-key>"
$env:LLM_CHAT_MODEL="<model-name>"
$env:LLM_BASE_URL="<openai-compatible-base-url>"
```

Cấu hình dữ liệu công khai bổ sung nếu có key:

```powershell
$env:ESTAT_APP_ID="<e-Stat-app-id>"
$env:MLIT_API_KEY="<mlit-api-key>"
$env:PUBLIC_CONTEXT_ENABLED="true"
```

Nếu cần chạy offline bằng dữ liệu local/demo:

```powershell
$env:SEARCH_PROVIDER="local"
python .\scripts\generate_sapporo_mock_data.py
python .\scripts\seed_chroma.py
```

## 3. Chạy Test

Chạy nhóm test chính:

```powershell
python -m pytest tests/test_smoke_imports.py tests/test_agent_flow.py tests/test_data_seed.py tests/test_tools.py tests/test_public_sources.py -q
```

Chạy smoke test nhanh:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

## 4. Chạy Hệ Thống

Chạy UI bằng Streamlit:

```powershell
python -m streamlit run ui/app.py
```

Nếu `streamlit` đã có trong PATH, có thể dùng:

```powershell
streamlit run ui/app.py
```

## 5. Luồng Chat Mẫu

### Tìm Nhà

Ví dụ:

```text
Tìm cho tôi căn 1LDK ở Sapporo dưới 85,000 yên, gần ga, cho 2 người.
```

Luồng xử lý:

1. UI gửi `AgentRequest` vào agent.
2. Agent trích xuất intent và constraint.
3. `ListingSearchTool` dùng LangChain DDGS search để tìm trên các trang bất động sản công khai của Nhật.
4. `AreaEnrichmentTool` bổ sung ngữ cảnh public từ e-Stat, MLIT, hazard/safety và regional indicators.
5. Ranking node sắp xếp kết quả theo constraint.
6. Response node trả lời ưu tiên tiếng Việt nếu input ban đầu là tiếng Việt.
7. UI hiển thị listing card, nguồn gốc kết quả và sơ đồ nhà nếu có.

### So Sánh Nhà

Ví dụ sau khi đã có kết quả tìm kiếm:

```text
So sánh các căn cùng khu vực trong danh sách vừa rồi theo giá thuê, diện tích và vị trí.
```

Hoặc chỉ định theo tên:

```text
So sánh Miyanosawa Smart 1R Residence và Kita 24 Jo Quiet 1R House theo giá thuê rồi vị trí.
```

Luồng xử lý:

1. Agent dùng state `recent_listings` từ lượt tìm kiếm trước.
2. Nếu người dùng nói "cùng khu vực", agent chọn nhóm listing cùng ward hoặc cùng station trong kết quả gần nhất.
3. Nếu người dùng nhập tên nhà, agent resolve tên sang listing tương ứng.
4. Nếu thiếu tiêu chí hoặc thiếu listing, agent hỏi lại đúng phần còn thiếu.
5. Kết quả so sánh giữ thứ tự tiêu chí từ trái sang phải theo input của người dùng.

### Export Kết Quả

Ví dụ:

```text
Tìm căn 1LDK ở Sapporo dưới 85,000 yên và export JSON.
```

Luồng xử lý:

1. Agent chạy search như bình thường.
2. Nếu `output_format` không phải `chat`, response node gọi `ExportTool`.
3. File export được ghi vào `data/exports/`.
4. UI hiển thị nút download trong message của agent.

## 6. Ghi Chú Vận Hành

- `SEARCH_PROVIDER=web` là đường chạy chính cho dữ liệu thật.
- `SEARCH_PROVIDER=local` chỉ dùng cho test, demo offline hoặc kiểm thử ranking bằng CSV/Chroma.
- DDGS là public search aggregation qua LangChain tool, không phải API chính thức của SUUMO/HOME'S/AtHome.
- Khi có partner API chính thức từ công ty quản lý bất động sản, nên thêm provider riêng sau interface hiện tại thay vì sửa LangGraph.
