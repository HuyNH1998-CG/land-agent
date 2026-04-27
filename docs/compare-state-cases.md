# Compare State Cases

Tài liệu này mô tả các trạng thái chính của flow `compare` và các trường hợp hệ thống sẽ yêu cầu người dùng nhập lại dữ liệu.

## Thành công ngay

Điều kiện:
- `intent_label = "compare"`
- `selected_listings` có từ 2 căn trở lên
- `compare_criteria` có thể rỗng hoặc có nhiều tiêu chí theo đúng thứ tự người dùng nêu

Hành vi:
- đi thẳng vào `response` node
- gọi `ComparisonTool`
- trả kết quả so sánh
- `pros/cons` được sắp theo `compare_criteria` từ trái qua phải
- ngôn ngữ mô tả bám theo `response_language`

Ví dụ:
- `Compare sap_045 and sap_091`
- `so sánh Miyanosawa Smart 1R Residence và Kita 24 Jo Quiet 1R House`
- `so sánh sap_045 và sap_091 theo vị trí, giá thuê rồi diện tích`

## Cần nhập lại vì chưa có căn nào

Điều kiện:
- `intent_label = "compare"`
- `selected_listings = []`

Hành vi:
- đi vào `clarification` node
- trả `missing_fields = ["selected_listings"]`
- yêu cầu người dùng cung cấp tên đầy đủ hoặc mã listing của 2 căn

Ví dụ:
- `Compare by rent`
- `so sánh theo giá thuê`

## Cần nhập lại vì mới có 1 căn

Điều kiện:
- `intent_label = "compare"`
- `selected_listings` chỉ có 1 căn

Hành vi:
- đi vào `clarification` node
- giữ lại căn đã nhận diện được
- yêu cầu người dùng nhập thêm 1 căn nữa

Ví dụ:
- `Compare sap_045`
- `so sánh sap_045`

## Cần nhập lại vì tên nhà chưa resolve được

Điều kiện:
- `intent_label = "compare"`
- parser phát hiện ý định so sánh
- `compare_targets` có dữ liệu, nhưng không resolve được sang `selected_listings`

Hành vi:
- đi vào `clarification` node
- yêu cầu người dùng gửi lại tên đầy đủ hoặc mã listing

Ví dụ:
- `Compare Green Court and Blue Plaza`
- `so sánh Green Court và Blue Plaza`

## Follow-up theo tiêu chí

Điều kiện:
- turn trước đã có `selected_listings`
- turn sau chỉ nói tiêu chí như giá thuê, diện tích, vị trí

Hành vi:
- dùng lại `selected_listings` từ context
- không hỏi lại “so sánh căn nào”
- cập nhật `compare_criteria` theo đúng thứ tự mới trong turn hiện tại
- mô tả so sánh dùng ngôn ngữ của turn đó

Ví dụ:
1. `so sánh Miyanosawa Smart 1R Residence và Kita 24 Jo Quiet 1R House`
2. `so sánh theo giá thuê`
