# Web học project BB84 Lab

Trang học dành cho người mới mở repo và chưa biết nên đọc từ đâu. Nội dung tiếng Việt dựa trên triển khai hiện có, phân biệt mô phỏng với QKD vật lý và tách kỳ vọng, ví dụ giả định, số liệu backend.

## Khởi động

Chạy tại gốc repository:

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.local --learn
```

Lệnh mở trình duyệt tại `http://127.0.0.1:8765/learn/`. Nếu cổng bận, thêm `--port 8787`. Dashboard cũ vẫn nằm ở `/`. Có thể dùng lệnh `--open` hiện có rồi bấm **Học project từ đầu**. Dừng server bằng `Ctrl+C`.

Trang cần được phục vụ qua server Python này, không mở `index.html` bằng `file://`. Không cần Node.js, dependency frontend hoặc dịch vụ bên ngoài; font và tài nguyên dùng sẵn trên máy. Trình duyệt cần hỗ trợ JavaScript hiện đại và `dialog`.

## Lộ trình

1. Bức tranh lớn: Alice, Bob, Eve; tạo khóa và mã hóa.
2. Bit, qubit, cơ sở Z/X và quy tắc đo.
3. Kiến trúc thư mục và luồng HTTP.
4. BB84 qua 16 tín hiệu công khai.
5. QBER, Wilson và các trạng thái monitor.
6. Parity, Cascade và lookback.
7. Ngân sách thông tin và phép nhân Toeplitz.
8. E91: góc đo, tương quan, CHSH, nhóm khóa và nhiễu.
9. HMAC, SHA-256, HKDF, AEAD, nonce và replay.
10. TCP, truyền tệp theo khối, `.part`, end và receipt.
11. Sáu chế độ Eve và cơ chế phát hiện.
12. Cài đặt, chạy local/network và đọc lỗi.
13. Seed, calibration/evaluation, ghép cặp và self-check.
14. Đọc hiểu đồ thị: trục, đơn vị, SD, Wilson/Bootstrap, năm nhóm hình study, E91 và đối sánh hiệu năng.
15. Tập trình bày và tự giải thích project.

Mỗi bài có mục tiêu, giải thích, ví dụ, câu hỏi có phản hồi và bài tập (32 câu trong 15 bài). Không bắt buộc trả lời đúng hết để đánh dấu đã học; người học tự quyết định khi đã hiểu. Thời lượng là ước lượng đọc, không phải thời gian đo người dùng.

## Tương tác và dữ liệu

- Bộ chọn cơ sở, parity, Wilson và Toeplitz là ví dụ/tính toán phía trình duyệt; được ghi rõ, không tạo khóa ứng dụng.
- Bài BB84 16 tín hiệu gọi `/api/lesson` và không đi vào mã hóa.
- Bài E91 gọi `/api/e91/simulate`, chỉ hiển thị thống kê. Nhiễu trắng dashboard khác lật bit trong demo mạng E91.
- Thử phiên gọi `/api/session`; thử gói gọi `/api/packet` rồi `/api/packet/action`. Không thay thuật toán lõi hoặc tham số mặc định.
- Chỉ nhập thông điệp demo công khai. Token gói/bản rõ không lưu vào localStorage.
- Tiến độ, câu trả lời và ghi chú lưu tại khóa localStorage `bb84-project-learning-v1` trên cùng origin. Đổi cổng/trình duyệt là vùng lưu khác; dữ liệu có thể mất khi xóa dữ liệu trình duyệt. Không đồng bộ hoặc gửi ghi chú lên server. Nếu lưu bị chặn, giao diện thông báo.
- Nút đặt lại tiến độ xóa dấu đã học/câu trả lời sau xác nhận, giữ ghi chú.
- Phím `/` mở tìm kiếm; `Esc` đóng. Tìm không dấu được. Có nút in/lưu PDF qua hộp thoại in của trình duyệt.
- **Từ viết tắt & ký hiệu** có tên đầy đủ, nghĩa tiếng Việt, cách dùng, ví dụ/lưu ý và liên kết bài liên quan. Tìm không dấu, lọc theo nhóm; tìm kiếm toàn trang cũng trả về các mục này. Bấm chữ gạch chấm trong bài để mở hộp giải nghĩa; `Esc` đóng và trả focus về chữ vừa chọn.
- Bài **Đọc hiểu đồ thị** tải `/api/study`, vẽ năm nhóm hình bằng SVG từ số liệu tổng hợp, có bộ lọc, chọn điểm bằng chuột hoặc bàn phím và bảng số liệu. Mỗi lần hiển thị một ô/đại lượng; hình 05 có bốn lựa chọn tương ứng bốn ô gốc. Thanh QBER là mean ± SD giữa phiên; khoảng detection là Wilson 95% của tỷ lệ phiên; chênh lệch ghép cặp dùng bootstrap 95%. Không có dữ liệu thì báo rõ; chỉ vẽ Y_final khi có tổng hợp hậu xử lý hoàn tất phù hợp. Đổi study bằng `--study-dir <thư-mục-study>` khi khởi động server.

## Mã nguồn và bảo trì

Frontend nằm ở `web/simulation/learn/`: `index.html`, `learn.css`, `content.js`, `learn.js`. `content.js` chứa dữ liệu khóa học, từ điển và bản đồ module; không chứa bản sao toàn bộ source.

`bb84_lab/local/learning.py` giữ danh sách tệp công khai cho phép đọc. `/api/learn/sources` trả danh mục; `/api/learn/source/<đường-dẫn-trong-danh-sách>` trả nội dung hiện tại, SHA-256 và vị trí hàm/class phân tích bằng AST, không thực thi file. Không chấp nhận đường dẫn tùy ý, traversal hoặc file outputs/PSK; giữ kiểm tra Host/Origin loopback và CSP chung. Có kiểm tra kích thước và đường dẫn đã resolve.

Liên kết bài học dùng tên hàm, không đóng cứng số dòng. Khi đổi tên/xóa hàm, cập nhật liên kết trong content. Trình xem báo nếu tên không còn tồn tại và cho chọn lại. Nội dung nguồn được cache trong bộ nhớ trang; tải lại trang để đọc thay đổi mới ở editor.

Kiểm tra cơ bản bằng `python -m tests.self_check`; nhóm HTTP kiểm tra tài nguyên, source allowlist, AST và các đường dẫn từ chối. QA trình duyệt nên bao gồm desktop/mobile, điều hướng đủ 15 bài, tìm kiếm không dấu, tra cứu và hộp giải nghĩa, lọc/chọn điểm của năm nhóm đồ thị, trạng thái thiếu study, ghi chú/tiến độ sau tải lại, các công cụ bit/ma trận và ba bước sửa/nhận/phát lại. Playwright nếu dùng cho QA là công cụ ngoài môi trường runtime, không thêm vào requirements.
