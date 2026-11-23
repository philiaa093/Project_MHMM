# Giao diện BB84 Lab

## Mục tiêu

Ưu tiên trình diễn một phiên gửi thông điệp: chọn kịch bản, quan sát BB84/QBER,
theo dõi lượng khóa mô hình và kiểm tra dữ liệu sau mã hóa. Các số liệu trên
giao diện lấy từ API hiện có, không dùng dữ liệu mẫu làm kết quả.

## Hướng thiết kế

Bố cục như bàn thí nghiệm, đọc từ trái sang phải; văn bản căn trái. Luồng
Alice–Eve–Bob là điểm nhận diện, các khu vực còn lại giữ đơn giản.

```text
BB84 Lab        Mô phỏng / Thí nghiệm / Giới thiệu        Kết nối
Trao đổi khóa. Theo dõi từng byte.
[ Kênh sạch | Eve toàn phần | Chỉ nhiễu | Can thiệp yếu | Ít mẫu ]
┌──────────────────────┬───────────────────────────────────────┐
│ Văn bản Alice gửi    │ Alice ─── Eve / kênh ─── Bob         │
│ Kích thước UTF-8     │ QBER + Wilson + quyết định giám sát    │
│ Số tín hiệu / f / p  │ Mẫu / bit giữ lại / đầu ra hậu xử lý   │
│ Tham số mở rộng      │ Byte đầu vào / bản mã + tag / phục hồi│
│ Chạy mô phỏng        │ Lý do mã hóa hoặc dừng                 │
└──────────────────────┴───────────────────────────────────────┘
Nhật ký kiểm chứng (mở rộng) / kiểm tra AEAD độc lập / lịch sử
```

## Màu sắc và chữ

- Nền làm việc: `#EDF1F7`; bề mặt nội dung: `#FFFFFF`.
- Chữ chính: `#17263E`; tương tác và Alice: `#3158C8`.
- Hoàn tất: `#14765D`; cảnh báo: `#925A13`; từ chối: `#B53B42`.
- Nhãn và nội dung dùng Segoe UI, dự phòng Arial; tiêu đề dùng Bahnschrift,
  dự phòng Segoe UI. Toàn bộ font lấy từ máy, không gọi CDN.
- Nội dung từ 14–16 px, chú thích tối thiểu 12 px. Số liệu dùng tabular-nums.

## Quy tắc hiển thị

- Phân biệt kết quả giám sát với trạng thái phát hành khóa/mã hóa.
- QBER thấp không được gắn nhãn “an toàn”; lỗi xác thực phải xóa kết quả cũ.
- Hiển thị số byte UTF-8, không lấy số ký tự thay kích thước dữ liệu.
- Số byte bản mã là bản mã cộng tag, chưa gồm nonce/AAD/gói truyền.
- Khôi phục chỉ hiện là thành công khi backend xác nhận. Không dựng bản rõ
  Bob từ ô nhập Alice; không đưa bit thô, khóa, bản rõ hay bản mã vào log.
- Thay đổi đầu vào sau một lần chạy phải được đánh dấu để tránh nhầm kết quả.
- Nhật ký kỹ thuật mở theo nhu cầu; lịch sử và tệp tải chỉ chứa dữ liệu công khai.
- Điều hướng bằng liên kết, biểu mẫu có nhãn, focus rõ, hỗ trợ giảm chuyển động.
- Kiểm tra Chrome ở desktop và điện thoại, năm kịch bản, lỗi xác thực, API
  thất bại, tải dữ liệu và trang thí nghiệm trước khi bàn giao.

## Kiểm chứng lần đổi bố cục ban đầu

- `python -m tests.self_check`: PASS; `node --check web/simulation/app.js`: PASS.
- Chrome headless: năm kịch bản, lỗi transcript, mất kết nối, thay đổi đầu
  vào trong lúc chờ, văn bản tiếng Việt 8.192 byte và chuỗi rỗng đều đạt.
- Các nút tải JSON/CSV hoạt động; dữ liệu tải không chứa thông điệp người dùng.
- Ba trang không tràn ngang toàn tài liệu ở các cỡ 320–1.440 px đã kiểm tra.
  Bảng và biểu đồ rộng cuộn trong vùng riêng, có thể focus bằng bàn phím.
- Kiểm tra tên truy cập của điều khiển, tương phản chữ HTML, cỡ chữ tối thiểu
  12 px, focus khi Tab và chế độ giảm chuyển động đều đạt trong Chrome.
- Bộ lọc thí nghiệm giữ qua tải lại bằng tham số URL. Không sửa backend,
  thuật toán, thư viện hoặc dữ liệu thí nghiệm.

## Mở rộng phần trình diễn thuật toán

Giữ bảng màu, font và cấu trúc các trang hiện có. Bổ sung hai mục điều hướng:

```text
BB84 từng bước
  Kịch bản + seed → 16 tín hiệu → 7 bước mở dần
  Bảng Alice / Eve / Bob → chọn tín hiệu → mạch và xác suất

Mã hóa
  Văn bản + kịch bản → BB84 mới → hậu xử lý đủ điều kiện?
  Khóa: BB84 → hậu xử lý → HKDF ─────────┐
  Dữ liệu: văn bản UTF-8 ────────────────┴→ AEAD → bản mã + tag
  Thử sửa → từ chối; gửi gói gốc → giải mã; phát lại → từ chối
```

Bit được xem trong bài học là 16 tín hiệu công khai, dùng seed miền riêng,
không gọi hậu xử lý hay phát hành khóa. `simulate(..., trace=...)` chỉ cho
phép thu trace ở đúng 16 tín hiệu và không thay chuỗi rút số ngẫu nhiên.
Sơ đồ mạch lấy từ trace; xác suất lý thuyết không được gọi là histogram đã đo.
Biểu đồ đối chiếu Aer đọc log có sẵn và ghi rõ điều kiện lý tưởng, không Eve/nhiễu.

Trang gói hiển thị dữ liệu thử nghiệm theo yêu cầu, chỉ giải mã sau hành động
người dùng. Số liệu và nội dung Bob lấy từ backend. Bản rõ không giữ trong bộ
đệm gói; chỉ giữ hash để đối chiếu. Bộ nhớ có giới hạn, khóa ở RAM, gói có TTL;
không thêm cơ sở dữ liệu, CDN hay dependency. Không xuất dữ liệu trình diễn
vào log thống kê cũ. Các phép thử sửa/phát lại dùng trạng thái nhận thật.

Kiểm chứng: self-check mở rộng kiểm tra trace, mẫu bị loại, API gói, tag lỗi,
phát lại, giới hạn dung lượng/TTL và hủy phiên trước mã hóa. Chrome đã chạy
7 bước, chọn mạch Eve, xem log Aer, thử sửa → giải mã → phát lại, xử lý đầu vào
giống HTML an toàn, dọn kết quả khi lỗi và kiểm tra các cỡ 320–1.440 px.
