# Code Overview

Tài liệu này giải thích ngắn gọn phần code hiện có trong project skeleton.

## Mục tiêu hiện tại

Project mới chỉ ở mức **base structure**:

- đã có chia lớp `UI -> Agent -> Tools -> Data`
- đã có request/response contract chung
- đã có LangGraph workflow skeleton
- chưa có logic tìm nhà thật, chưa đọc dataset thật, chưa gọi model thật

## Cấu trúc chính

### `ui/app.py`

Đây là entrypoint cho giao diện Streamlit.

Nó hiện đang làm các việc sau:

- tạo giao diện chat đơn giản
- đọc một số cấu hình từ `.env`
- nhận input người dùng
- tạo `AgentRequest`
- gọi `RentalAgentService`
- hiển thị `reply` và danh sách `listings` nếu có

Hiện tại UI đã chạy được ở mức demo skeleton, nhưng kết quả trả về vẫn là placeholder.

## `src/japan_rental_agent/config.py`

File này quản lý cấu hình ứng dụng bằng `pydantic-settings`.

Nó map các biến môi trường như:

- `LLM_API_KEY`
- `LLM_CHAT_MODEL`
- `LLM_BASE_URL`
- `LLM_EMBEDDING_MODEL`

Ngoài ra còn giữ các giá trị mặc định như `default_top_k`, `data_dir`, `export_dir`.

## `src/japan_rental_agent/contracts/api.py`

Đây là lớp định nghĩa contract chung giữa UI và Agent.

Các model chính:

- `AgentRequest`: payload UI gửi vào agent
- `AgentResponse`: payload agent trả về
- `AgentData`: phần dữ liệu kết quả như filters, listings, comparison, file
- `AgentMeta`: metadata như tool đã dùng, confidence, processing time
- `AgentError`: format lỗi chuẩn

Phần này rất quan trọng vì nó giữ cho UI, agent và tools nói chuyện cùng một schema.

## `src/japan_rental_agent/domain/models.py`

File này định nghĩa các model nghiệp vụ cốt lõi:

- `Listing`
- `ListingScoreBreakdown`
- `SearchFilters`
- `ComparisonItem`

Đây là lớp dữ liệu trung tâm cho bài toán tìm nhà.

## `src/japan_rental_agent/agent/`

Thư mục này chứa phần orchestration theo LangGraph.

### `state.py`

Định nghĩa `RentalAgentState`, là state dùng xuyên suốt workflow.

State hiện chứa các trường như:

- input gốc
- parsed constraints
- missing fields
- search results
- ranked results
- error message
- response payload

Ngoài ra có `create_initial_state()` để chuyển từ `AgentRequest` sang state ban đầu.

### `graph.py`

Đây là nơi dựng LangGraph workflow.

Flow hiện tại:

1. `input`
2. `intent_extraction`
3. nếu thiếu thông tin -> `clarification`
4. nếu đủ thông tin -> `listing_search`
5. tiếp theo -> `enrichment_ranking`
6. cuối cùng -> `response`
7. nếu có lỗi -> `error_retry`

### `service.py`

`RentalAgentService` là lớp mà UI gọi vào.

Nó có nhiệm vụ:

- nhận `AgentRequest`
- tạo initial state
- invoke graph
- convert kết quả cuối thành `AgentResponse`

Bạn có thể xem nó như lớp application service bọc bên ngoài workflow.

### `agent/nodes/`

Mỗi file là một node nhỏ trong graph:

- `input_node.py`: ghi nhận input user vào history
- `intent_extraction.py`: gọi parser tool để lấy constraints
- `router.py`: quyết định đi nhánh clarification hay search
- `clarification.py`: tạo response dạng `need_clarification`
- `search.py`: gọi search tool
- `enrichment_ranking.py`: gọi enrichment và ranking tool
- `error_retry.py`: tạo response lỗi chuẩn
- `response.py`: tạo response thành công chuẩn

Điểm cần lưu ý là các node hiện chỉ đang nối flow và trả dữ liệu placeholder đúng schema.

## `src/japan_rental_agent/tools/`

Thư mục này là tool layer mà agent sẽ dùng.

Các tool hiện có:

- `parser.py`
- `search.py`
- `enrichment.py`
- `ranking.py`
- `compare.py`
- `export.py`

Hiện tại tất cả mới là stub:

- nhận input đúng format
- trả output đúng contract cơ bản
- chưa có xử lý business logic thật

Điều này giúp chúng ta có thể phát triển từng phần sau mà không phải sửa lại kiến trúc.

## `src/japan_rental_agent/data/`

Phần này là data access layer sơ khai.

### `repositories.py`

Hiện có:

- `DatasetRegistry`: quản lý đường dẫn các file data chuẩn
- `LocalDatasetRepository`: lớp repository placeholder để sau này đọc CSV hoặc SQLite

Phần này chưa load dữ liệu thật, nhưng đã chốt vị trí và naming cho datasets.

## `data/`

Thư mục này để chứa dataset local và file export.

Hiện có:

- `data/README.md`: mô tả các file data dự kiến
- `data/exports/`: nơi chứa file export sinh ra sau này

## `tests/test_smoke_imports.py`

Đây là smoke test đơn giản nhất hiện có.

Nó xác nhận rằng:

- package import được
- `RentalAgentService` khởi tạo được
- service trả về `AgentResponse` hợp lệ

## Trạng thái thực tế của code lúc này

Hiện project đã sẵn sàng cho giai đoạn implement tiếp theo:

- kiến trúc đã có
- contract đã có
- UI entrypoint đã có
- workflow agent đã có
- tool layer đã có khung

Nhưng chưa có:

- parser thật
- search dataset thật
- ranking thật
- export thật
- tích hợp Gemini model thật

## Nên đọc file nào trước

Nếu muốn nắm tổng quan nhanh, nên đọc theo thứ tự này:

1. `README.md`
2. `docs/smoke-test.md`
3. `ui/app.py`
4. `src/japan_rental_agent/contracts/api.py`
5. `src/japan_rental_agent/agent/service.py`
6. `src/japan_rental_agent/agent/graph.py`
7. `src/japan_rental_agent/tools/*.py`

