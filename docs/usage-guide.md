# Hướng Dẫn Sử Dụng

Tài liệu này tổng hợp các lệnh cần thiết để dựng môi trường, chạy test, seed dữ liệu và chạy hệ thống thực.

## 1. Cài đặt ban đầu

Lưu ý:

- Không có lệnh `python` nào để tự cài chính Python nếu máy chưa có Python.
- Trên Windows, nên cài Python 3.12 trước bằng `winget` hoặc từ [python.org](https://www.python.org/downloads/).

### Cài Python trên Windows

```powershell
winget install -e --id Python.Python.3.12
```

### Kiểm tra Python và pip

```powershell
python --version
python -m pip --version
```

### Tạo virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### Cài dependency của project

```powershell
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## 2. Chuẩn bị dữ liệu local

### Sinh lại mock dataset Sapporo

```powershell
python .\scripts\generate_sapporo_mock_data.py
```

Kết quả:

- `data/rental_listings_demo.csv`
- `data/floor_plan_reference.csv`
- `data/floor_plans/*.svg`

### Seed dữ liệu vào Chroma

```powershell
python .\scripts\seed_chroma.py
```

Hoặc dùng PowerShell wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\seed_chroma.ps1
```

## 3. Chạy test

### Chạy toàn bộ test hiện có

```powershell
python -m pytest tests/test_smoke_imports.py tests/test_agent_flow.py tests/test_data_seed.py tests/test_tools.py -q
```

### Chạy smoke test nhanh

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

## 4. Chạy hệ thống thực

### Chạy UI bằng Streamlit

```powershell
streamlit run ui/app.py
```

Nếu `streamlit` chưa nằm trong PATH, dùng:

```powershell
python -m streamlit run ui/app.py
```

### Luồng chạy tối thiểu trước khi demo

```powershell
.\.venv\Scripts\activate
python -m pip install -e .[dev]
python .\scripts\generate_sapporo_mock_data.py
python .\scripts\seed_chroma.py
python -m pytest tests/test_smoke_imports.py tests/test_agent_flow.py tests/test_data_seed.py tests/test_tools.py -q
python -m streamlit run ui/app.py
```

## 5. Luồng chat mẫu

### Tìm nhà

Ví dụ câu hỏi:

```text
Tìm cho tôi căn 1LDK ở Sapporo dưới 85,000 yên, gần ga, cho 2 người.
```

Luồng hệ thống:

1. UI gửi `AgentRequest` vào agent.
2. Agent gọi `QueryParserTool` để trích constraint ban đầu.
3. Agent dùng node intent extraction để xác định đây là yêu cầu `search`.
4. `ListingSearchTool` lọc từ CSV mock và rerank bằng Chroma.
5. `AreaEnrichmentTool` bổ sung hazard score, station context, city context, floor-plan asset.
6. `RankingTool` chấm điểm và sắp xếp kết quả.
7. Response node tạo câu trả lời tiếng Việt và trả listings về UI.
8. UI hiển thị listing card và sơ đồ nhà tương ứng.

### So sánh nhà

Luồng thao tác:

1. Người dùng tick chọn 2 hoặc nhiều listing trên UI.
2. Bấm `Compare Selected`.
3. UI gửi một message kiểu:

```text
Compare sap_001 and sap_002
```

4. Agent nhận intent `compare`.
5. Response node gọi `ComparisonTool`.
6. UI hiển thị `pros` / `cons` cho từng căn và vẫn có thể xem sơ đồ nhà.

### Export kết quả

Ví dụ câu hỏi:

```text
Tìm cho tôi căn 1LDK ở Sapporo dưới 85,000 yên và export JSON.
```

Luồng hệ thống:

1. Agent chạy search như bình thường.
2. Vì `output_format != chat`, response node gọi `ExportTool`.
3. File export được ghi vào `data/exports/`.
4. UI hiển thị nút download ngay trong message của agent.

## 6. Ghi chú vận hành

- UI hiện ưu tiên tiếng Việt cho câu trả lời của agent.
- Nếu endpoint Gemini/OpenAI-compatible không truy cập được, hệ thống sẽ tự rơi về fallback logic thay vì dừng hẳn.
- `data/chroma/` là persistent local store. Nếu cần seed lại sạch, chỉ cần chạy lại `python .\scripts\seed_chroma.py`.
