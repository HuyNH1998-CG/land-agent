# Japan Rental Agent — Sample Architecture & Sample Datasets

## 1) Mục tiêu
Xây dựng một **AI Agent hỗ trợ tìm nhà cho thuê tại Nhật Bản qua hội thoại** trong phạm vi MVP 2 tuần, phù hợp cho **team 3 người làm part-time**.

---

# Part A — Architecture tổng quan

## A.1. Nguyên tắc thiết kế
- **1 agent chính** để giảm độ phức tạp và rủi ro integration
- Dùng **LangGraph StateGraph** để đáp ứng yêu cầu agentic workflow
- Phân tách rõ: **UI → Agent → Tools → Data Layer**
- Ưu tiên **dataset demo/local + open data chính thức** thay vì scraping real-time
- Mọi tool cần có **input/output contract ổn định**

## A.2. Kiến trúc tổng thể

```text
Frontend (Streamlit)
   ↓
Agent Orchestrator (LangGraph)
   ├── Intent / Constraint Extraction Node
   ├── Clarification Node
   ├── Search Node
   ├── Enrichment + Ranking Node
   ├── Response Node
   └── Error / Retry Node
   ↓
Tool Layer
   ├── Query Parser Tool
   ├── Listing Search Tool
   ├── Area Enrichment Tool
   ├── Ranking Tool
   ├── Comparison Tool
   └── Export Tool
   ↓
Data Layer
   ├── Local rental listings dataset (CSV / SQLite)
   ├── Regional statistics dataset
   ├── Hazard / safety dataset
   └── Optional transit / POI dataset
```

## A.3. Luồng xử lý chính
1. User nhập yêu cầu bằng chat hoặc upload file.
2. Agent phân tích ý định và trích xuất điều kiện.
3. Nếu thiếu thông tin quan trọng, agent hỏi lại.
4. Khi đủ điều kiện, agent gọi tool tìm listing.
5. Agent enrich thêm dữ liệu khu vực, hazard, tiện ích, commute.
6. Agent chấm điểm và xếp hạng.
7. Kết quả được hiển thị trên UI và có thể export CSV / JSON / PDF.

## A.4. LangGraph workflow mẫu

### Nodes đề xuất
1. **Input Node**
2. **Intent Extraction Node**
3. **Need Clarification Router**
4. **Clarification Node**
5. **Listing Search Node**
6. **Area Enrichment + Ranking Node**
7. **Response / Export Node**
8. **Error / Retry Node**

### Flow logic

```text
Input
  ↓
Intent Extraction
  ↓
Need Clarification?
  ├─ Yes → Clarification → quay lại Extraction
  └─ No  → Listing Search
              ├─ Fail → Error / Retry
              └─ Success → Enrichment + Ranking
                               ↓
                         Response / Export
```

## A.5. State mẫu

```python
RentalAgentState = {
    "raw_input": str,
    "input_type": str,                # text / file / url
    "parsed_constraints": dict,
    "missing_fields": list,
    "search_results": list,
    "enriched_results": list,
    "ranked_results": list,
    "selected_output_format": str,   # chat / csv / json / pdf
    "retry_count": int,
    "error_message": str,
    "conversation_history": list,
}
```

## A.6. Tool contract mẫu

### Query Parser Tool
**Input**
```json
{
  "message": "Tìm nhà dưới 8 man gần ga ở Tokyo cho 2 người"
}
```

**Output**
```json
{
  "city": "Tokyo",
  "max_rent": 80000,
  "near_station": true,
  "occupancy": 2
}
```

### Listing Search Tool
**Input**
```json
{
  "city": "Tokyo",
  "max_rent": 80000,
  "near_station": true
}
```

**Output**
```json
[
  {
    "listing_id": "tokyo_001",
    "title": "1K apartment near station",
    "rent_yen": 76000,
    "station": "Ikebukuro",
    "walk_min": 6,
    "area_m2": 24.5,
    "building_age": 12
  }
]
```

---

# Part B — Architecture chia nhỏ theo từng role

## B.1. Role A — Agent / LangGraph Engineer

### Mục tiêu
Xây phần “não” của hệ thống: reasoning, routing, retry, clarification.

### Scope chịu trách nhiệm
- `agent/state.py`
- `agent/graph.py`
- `agent/nodes/*.py`
- logic quyết định gọi tool nào
- error handling / fallback / retry

### Deliverables
- StateGraph chạy được
- Có conditional routing
- Có loop clarification
- Có retry / fallback cơ bản
- End-to-end chat flow hoạt động

### Interface phụ thuộc
- Nhận tool functions ổn định từ Role B
- Trả JSON response chuẩn cho Role C

### Output ví dụ
```json
{
  "reply": "Tôi tìm được 5 căn phù hợp nhất.",
  "results": [...],
  "can_export": true
}
```

---

## B.2. Role B — Data & Tool Engineer

### Mục tiêu
Xây data foundation và tất cả tools để agent gọi được.

### Scope chịu trách nhiệm
- `data/` (CSV / SQLite)
- `tools/parser.py`
- `tools/search.py`
- `tools/enrichment.py`
- `tools/ranking.py`
- `tools/compare.py`
- `tools/export.py`

### Deliverables
- Dataset sạch, schema rõ
- Search tool chạy ổn định
- Ranking tool có trọng số rõ ràng
- Enrichment tool đọc được dữ liệu khu vực / hazard / stats
- Export CSV / JSON hoạt động

### Interface cần chốt sớm
- schema listing
- input/output format của từng tool
- ranking fields bắt buộc

### Ví dụ schema listing
```csv
listing_id,title,prefecture,city,ward,station,walk_min,rent_yen,management_fee,layout,area_m2,building_age,floor,pet_allowed,foreigner_friendly,lat,lng
```

---

## B.3. Role C — UI & Integration Engineer

### Mục tiêu
Xây demo UI để nhập input, xem kết quả, compare, export.

### Scope chịu trách nhiệm
- `ui/app.py`
- phần hiển thị chat
- upload input file
- render results table
- download CSV / JSON / PDF
- integration gọi agent backend/function

### Deliverables
- Chat UI hoạt động
- Kết quả hiển thị dạng bảng
- Có compare view đơn giản
- Có nút download output
- Có trạng thái loading / error cơ bản

### Contract cần thống nhất với Role A
- request payload
- response payload
- format export

### UI modules đề xuất
- Chat Panel
- Filters Summary Panel
- Results Table
- Comparison Panel
- Download Panel

---

## B.4. Dependency map giữa các role

```text
Role B (Data/Tools)
      ↓
Role A (Agent/LangGraph)
      ↓
Role C (UI/Integration)
```

### Ý nghĩa
- Role B phải chốt schema và tool sớm
- Role A tích hợp lên graph sau khi tool đã ổn
- Role C tích hợp UI khi response contract đã chốt

---

# Part C — Sample datasets đề xuất

## C.1. Dataset 1 — Rental Listings Demo Dataset (bắt buộc)

### Mục đích
Là bộ dữ liệu chính để demo chức năng “tìm nhà”.

### Khuyến nghị
Tạo hoặc chuẩn hóa một dataset cỡ **300–1000 listings** cho 1–2 khu vực như Tokyo / Osaka.

### Nguồn
- CSV nội bộ do team dựng từ dữ liệu mẫu công khai
- dữ liệu demo tự tạo có cấu trúc giống listing thật
- có thể kết hợp một phần dữ liệu public và dữ liệu mock hợp lệ

### Cột nên có
- `listing_id`
- `title`
- `prefecture`
- `city`
- `ward`
- `nearest_station`
- `walk_min`
- `rent_yen`
- `management_fee`
- `deposit`
- `key_money`
- `layout`
- `area_m2`
- `building_age`
- `floor`
- `pet_allowed`
- `foreigner_friendly`
- `available_from`
- `lat`
- `lng`

### Vai trò trong hệ thống
- Search tool dùng trực tiếp
- Ranking tool dùng để chấm điểm
- Compare tool dùng để so sánh căn

---

## C.2. Dataset 2 — Housing and Land Survey (e-Stat)

### Nguồn
Japan e-Stat có **Housing and Land Survey** với dữ liệu ở mức Nhật / tỉnh / thành phố / quận, có thể truy cập dưới dạng DB/API. Bộ 2023 hiện có dữ liệu tabulation theo nhiều cấp địa lý và nhiều chỉ số về tenure, loại nhà, năm xây dựng, diện tích, v.v. ([e-Stat Housing and Land Survey](https://www.e-stat.go.jp/en/stat-search/files?toukei=00200522), [dataset browser/API entry](https://www.e-stat.go.jp/index.php/en/stat-search/database?layout=dataset&page=1&tclass1=000001207808&toukei=00200522&tstat=000001207800))

### Dùng để làm gì
- bổ sung **bối cảnh khu vực**
- làm feature cho ranking:
  - tỷ lệ nhà thuê
  - phân bố diện tích nhà
  - tuổi nhà phổ biến
  - mật độ household / dwelling

### Khuyến nghị cho MVP
Không cần kéo toàn bộ survey. Chỉ chọn **một vài bảng** cho khu vực demo.

---

## C.3. Dataset 3 — Real Estate / Land-related Open Data (MLIT)

### Nguồn
MLIT vận hành **Real Estate Information Library** và nhiều báo cáo/thông tin về đất đai – bất động sản, là nguồn chính thức hữu ích để enrich bối cảnh giá và thông tin thị trường. ([MLIT Real Estate Information Library](https://www.reinfolib.mlit.go.jp/), [MLIT land trends report](https://www.mlit.go.jp/totikensangyo/content/001908011.pdf))

### Dùng để làm gì
- bổ trợ market context
- làm metadata cho khu vực
- giải thích cho user theo kiểu “khu này mặt bằng bất động sản ra sao”

### Lưu ý
Nguồn này phù hợp để **enrichment / explanation**, nhưng MVP không nên phụ thuộc hoàn toàn vào nó cho search chính.

---

## C.4. Dataset 4 — Hazard / Flood / Safety Data

### Nguồn
MLIT và các cổng hazard map của Nhật công bố dữ liệu và hướng dẫn liên quan đến **flood damage hazard maps** và thông tin rủi ro thiên tai. Đây là hướng tốt để thêm tính năng “tránh khu dễ ngập”. ([MLIT White Paper excerpt on hazard maps](https://www.mlit.go.jp/common/001269905.pdf))

### Dùng để làm gì
- enrich theo safety score
- hỗ trợ query kiểu:
  - “tránh khu dễ ngập”
  - “ưu tiên khu an toàn hơn”

### MVP suggestion
- dùng score ở mức area/ward thay vì geospatial phân tích quá chi tiết
- có thể mock/seed trước 1 bảng `ward_hazard_score.csv`

Ví dụ schema:
```csv
prefecture,city,ward,flood_risk_score,earthquake_risk_score,overall_safety_score
```

---

## C.5. Dataset 5 — Optional Regional Indicators (e-Stat Dashboard API)

### Nguồn
**Statistics Dashboard API** của e-Stat cung cấp chỉ số thống kê tổng hợp của chính phủ và khu vực. ([e-Stat Dashboard API](https://dashboard.e-stat.go.jp/en/static/api))

### Dùng để làm gì
- thêm chỉ số khu vực gọn nhẹ
- có thể enrich một vài metric như dân số, household indicators, regional context

### Có nên dùng không?
- **Có**, nếu team còn thời gian
- **Không bắt buộc** cho MVP

---

# Part D — Dataset package đề xuất cho demo 2 tuần

## Gói dataset tối thiểu nên dùng

### Bắt buộc
1. **rental_listings_demo.csv**
2. **ward_hazard_score.csv**

### Nên có thêm
3. **housing_context_by_city.csv** (trích từ e-Stat)

### Optional
4. **poi_or_station_context.csv**
5. **market_context_notes.json**

---

## D.1. Ví dụ package thư mục data

```text
data/
 ├── rental_listings_demo.csv
 ├── ward_hazard_score.csv
 ├── housing_context_by_city.csv
 ├── station_access_reference.csv
 └── exports/
```

---

# Part E — Khuyến nghị triển khai thực tế

## Nên làm
- Chốt **1 city trước** (ví dụ Tokyo)
- Dùng **CSV/SQLite local** cho search chính
- Dùng **open data official** cho enrichment
- Giữ **1 agent chính**
- Chốt schema và contract sớm

## Không nên làm trong MVP
- scraping site bất động sản real-time
- geospatial pipeline phức tạp
- multi-agent architecture
- sync nhiều API ngoài cùng lúc

---

# Part F — Kết luận

Với team 3 người part-time, architecture hợp lý nhất là:
- **UI đơn giản bằng Streamlit**
- **1 LangGraph agent** làm orchestration
- **tool layer tách riêng**
- **search chính dùng dataset local/demo**
- **open data chính thức của Nhật dùng để enrich**

Cách này vừa đáp ứng yêu cầu nghiệm thu, vừa giảm rủi ro kỹ thuật, vừa đủ mạnh để demo use case “chat để tìm nhà cho thuê tại Nhật”.


# 📦 Contract chung (Agent ↔ UI ↔ Tools)

Tài liệu này định nghĩa **payload chuẩn** để tất cả role (A/B/C) dùng chung, tránh mismatch khi integration.

---

# 1. API Contract (UI ↔ Agent)

## 1.1. Request Payload

```json
{
  "session_id": "string",
  "message": "string",
  "input_type": "text | file | url",
  "context": {
    "previous_filters": {},
    "selected_listings": []
  },
  "options": {
    "top_k": 5,
    "output_format": "chat | json | csv | pdf"
  }
}
```

### Field giải thích

| Field                     | Type   | Required | Description          |
| ------------------------- | ------ | -------- | -------------------- |
| session_id                | string | ✔        | ID session           |
| message                   | string | ✔        | user input           |
| input_type                | string | ✔        | text/file/url        |
| context.previous_filters  | object | ✖        | filter từ lượt trước |
| context.selected_listings | array  | ✖        | dùng cho compare     |
| options.top_k             | number | ✖        | số kết quả           |
| options.output_format     | string | ✖        | kiểu output          |

---

## 1.2. Response Payload

```json
{
  "status": "success | need_clarification | error",
  "reply": "string",
  "data": {
    "filters_used": {},
    "listings": [],
    "comparison": [],
    "file": null
  },
  "meta": {
    "tool_used": ["search", "ranking"],
    "confidence": 0.92,
    "processing_time_ms": 320
  },
  "error": null
}
```

---

## 1.3. Response trạng thái

### SUCCESS

```json
{
  "status": "success",
  "reply": "Tôi đã tìm được 5 căn phù hợp...",
  "data": {
    "filters_used": {
      "city": "Tokyo",
      "max_rent": 80000
    },
    "listings": [...]
  }
}
```

---

### NEED CLARIFICATION

```json
{
  "status": "need_clarification",
  "reply": "Bạn muốn ở khu nào tại Tokyo?",
  "data": {
    "missing_fields": ["area"]
  }
}
```

---

### ERROR

```json
{
  "status": "error",
  "reply": "Không thể tìm dữ liệu lúc này",
  "error": {
    "code": "SEARCH_FAIL",
    "message": "timeout"
  }
}
```

---

# 2. Listing Data Schema (Tool ↔ Agent)

## 2.1. Listing object

```json
{
  "id": "apt_001",
  "title": "1K Apartment near Shinjuku",
  "city": "Tokyo",
  "ward": "Shinjuku",
  "rent": 75000,
  "management_fee": 5000,
  "layout": "1K",
  "area_m2": 25,
  "building_age": 10,
  "floor": 3,
  "nearest_station": "Shinjuku",
  "distance_to_station_min": 5,
  "commute_time_min": 30,
  "foreigner_friendly": true,
  "pet_allowed": false,
  "lat": 35.6895,
  "lng": 139.6917,
  "score": 0.87,
  "score_breakdown": {
    "price": 0.9,
    "location": 0.8,
    "size": 0.7
  }
}
```

---

# 3. Tool Contract (Agent ↔ Tools)

## 3.1. Search Tool

### Input

```json
{
  "city": "Tokyo",
  "max_rent": 80000,
  "min_area": 20,
  "near_station": true
}
```

### Output

```json
{
  "results": [ ...listing objects... ],
  "total": 120
}
```

---

## 3.2. Ranking Tool

### Input

```json
{
  "listings": [...],
  "preferences": {
    "weight_price": 0.4,
    "weight_location": 0.3,
    "weight_size": 0.3
  }
}
```

### Output

```json
{
  "ranked": [...sorted listings...]
}
```

---

## 3.3. Comparison Tool

### Input

```json
{
  "listing_ids": ["apt_001", "apt_002"]
}
```

### Output

```json
{
  "comparison": [
    {
      "id": "apt_001",
      "pros": ["cheap", "near station"],
      "cons": ["small"]
    }
  ]
}
```

---

## 3.4. Export Tool

### Input

```json
{
  "listings": [...],
  "format": "csv"
}
```

### Output

```json
{
  "file_url": "/download/result.csv",
  "file_type": "csv"
}
```

---

# 4. Export Format chuẩn

## 4.1. CSV

```csv
id,title,city,rent,area_m2,station,distance_min,score
apt_001,1K near Shinjuku,Tokyo,75000,25,Shinjuku,5,0.87
```

---

## 4.2. JSON

```json
{
  "results": [
    {
      "id": "apt_001",
      "rent": 75000,
      "score": 0.87
    }
  ]
}
```

---

## 4.3. PDF (structure)

```text
Rental Report
-------------
Top 5 Listings:
1. apt_001 - 75,000 JPY - Score: 0.87
2. apt_002 - 80,000 JPY - Score: 0.85

Summary:
- Best value: apt_001
- Closest to station: apt_003
```

---

# 5. End-to-End Example

## Request

```json
{
  "session_id": "abc123",
  "message": "Tìm nhà dưới 8 man ở Tokyo gần ga",
  "input_type": "text"
}
```

## Response

```json
{
  "status": "success",
  "reply": "Tôi tìm được 5 căn phù hợp",
  "data": {
    "filters_used": {
      "city": "Tokyo",
      "max_rent": 80000
    },
    "listings": [
      {
        "id": "apt_001",
        "rent": 75000,
        "score": 0.87
      }
    ]
  },
  "meta": {
    "tool_used": ["parser", "search", "ranking"]
  }
}
```

---

# 6. Rule bắt buộc cho team

* Không thay đổi schema giữa chừng
* Nếu cần thay → update doc + notify team
* Tool phải return đúng format
* Agent không được parse output thủ công

---

# 7. Checklist integration

* [ ] UI gửi đúng request format
* [ ] Agent trả đúng status
* [ ] Tool output đúng schema
* [ ] Export download được
* [ ] Error có format chuẩn

---

👉 File này dùng làm **single source of truth** cho toàn bộ team.
