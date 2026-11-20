# Kịch bản demo BB84 Lab — 5–7 phút

## Chuẩn bị

```powershell
cd E:\Project_MHMM
.\.venv\Scripts\python.exe -m tests.self_check
.\.venv\Scripts\python.exe -m bb84_lab.app --open
```

Mở `http://127.0.0.1:8765`. Giữ seed **2026**, tỷ lệ mẫu **25%**, ngưỡng **5%**,
mẫu tối thiểu **100**. Bộ `outputs/study/` đã có kết quả; trang **Thí nghiệm** đọc
bộ này, không tự chạy 3.300 phiên khi bấm xem. Muốn tái tạo, dùng lệnh trong README.

Thông điệp mở đầu: “Đây là mô phỏng cổ điển để học BB84 và đo giám sát QBER.
Seed nghiên cứu là công khai; khóa mô hình không bảo vệ dữ liệu thật.”

## Trình bày

### 0:00–1:15 — Kênh sạch và luồng đầy đủ

Chọn **Kênh sạch**, bấm **Chạy mô phỏng**. Chỉ vào Alice/Bob chọn cơ sở, sàng lọc,
loại mẫu rồi đến QBER và khoảng Wilson. Với mặc định đã kiểm tra:

- QBER 0%, 2.056 bit sàng lọc; công khai và loại 514 bit mẫu, còn 1.542 bit.
- Giám sát cho phép tiếp tục; Cascade tiết lộ 52 bit parity, xác nhận tính 257 bit.
- Ngân sách mô hình cho 1.064 bit Toeplitz; hai khóa khớp và AEAD khôi phục đúng.

Nhấn mạnh `continue` chỉ cho phép hậu xử lý. Chỉ khi hậu xử lý `ready` mới mã hóa.
ID phiên, thời gian và khóa thay đổi giữa các lần chạy; khóa không hiển thị.

Cuộn xuống **Nhật ký kiểm chứng thực thi**. Chỉ vào các dòng `BB84-01` đến
`AEAD-02`: tên hàm backend, phép tính sàng lọc/lấy mẫu, QBER, Wilson, ngân sách
Toeplitz và lời gọi `cryptography...ChaCha20Poly1305.encrypt/decrypt`. Bấm **Tải
log JSON** để lưu dấu vết công khai cùng SHA-256. Đây là bằng chứng nhánh phần mềm
đã chạy và số liệu khớp công thức, không phải bằng chứng có photon thật.

### 1:15–2:00 — Eve toàn phần và chỉ có nhiễu

Chọn **Eve toàn phần**, bấm chạy: khoảng Wilson vượt ngưỡng, trạng thái bất thường,
không phát hành khóa và không mã hóa. Giải thích QBER kỳ vọng 25%; số đo một phiên
có thể lệch do mẫu hữu hạn.

Chọn **Chỉ nhiễu**, chạy lại: `f=0`, `p=10%` cũng có thể làm kênh bất thường.
Thông điệp: “QBER phát hiện kênh không đạt điều kiện; không tự xác định nguyên nhân là Eve.”

### 2:00–3:00 — Can thiệp yếu và hai kiểu thiếu tài nguyên

Chọn **Can thiệp yếu**, chạy lại. Ở seed 2026 đã kiểm tra, QBER mẫu khoảng **1,569%**,
giám sát vẫn cho tiếp tục. Hậu xử lý sửa 43 sai khác nhưng không còn đủ ngân sách
256 bit nên **không mã hóa**. Đây là ví dụ Eve có mặt nhưng không bị gắn bất thường;
không diễn giải QBER thấp thành phiên an toàn.

Chọn **Ít mẫu** để thấy `inconclusive`; khi không có mẫu, QBER là chưa xác định.
Muốn minh họa thiếu khóa dù giám sát đạt: chọn **Kênh sạch**, đổi N thành
**1.024**, chạy lại. Kết quả đã kiểm tra cho `continue` nhưng `insufficient_key`.

### 3:00–3:45 — Sửa transcript phải hủy ngay

Chọn **Kênh sạch**. Mở **Tham số giám sát**, bật **Thử sửa transcript công khai**,
bấm chạy. Giao diện báo lỗi xác thực; không được trình bày quyết định hợp lệ,
khóa hoặc kết quả mã hóa cho phiên này. Tắt tùy chọn sau khi minh họa.

Giải thích PSK xác thực độc lập với khóa đang tạo; BB84 không tự xác thực danh tính.

### 3:45–4:30 — AEAD, sửa bản mã và phát lại

Tại **Mã hóa & xác thực thông điệp**, nhập thông điệp rồi bấm **Kiểm tra AEAD**.
Ba kết quả cần đạt: khôi phục đúng, từ chối bản mã bị sửa, từ chối phát lại.
Phần này dùng khóa ngẫu nhiên riêng của hệ điều hành nên chạy được ngay cả khi
phiên BB84 vừa bị hủy. Luồng BB84 tích hợp cũng chạy ba phép kiểm tra tương tự khi
tạo được khóa mô hình.

Chỉ ra nonce bộ đếm 96 bit, AAD ràng buộc phiên/vai trò/số thứ tự và không lưu khóa
qua lần khởi động. HKDF sau Toeplitz chỉ ràng buộc phiên, không tạo thêm entropy.

### 4:30–6:15 — Thí nghiệm, đối sánh và kết quả không cải thiện

Mở **Thí nghiệm**. Chỉ vào **3.300 phiên độc lập**, lựa chọn đóng băng **25%** và
bộ đánh giá **1.500 phiên**. Không gọi 4.500 kết quả ba phương án là 4.500 phiên
độc lập; 450 phiên hiệu chỉnh đã thuộc bộ chính.

Chọn N/nhiễu để đối chiếu đường QBER đo được với kỳ vọng, xem bảng tỷ lệ bất thường,
chưa đủ bằng chứng và khoảng tin cậy. Mở biểu đồ đối sánh hoặc tải CSV/JSON:

- Bộ hiệu chỉnh: mẫu 10% tăng Y_pre khoảng 14,07% ở nhóm không Eve/nhiễu thấp
  nhưng giảm phát hiện tối đa 23,33 điểm phần trăm; không đạt đủ tiêu chí.
- Mẫu 50% tiêu tốn thêm vật liệu; không đạt mục tiêu tăng hiệu suất.
- Giữ B0=25%, đóng băng lựa chọn trước seed mới và **không chọn lại** sau đánh giá.

Nêu kết quả đã đo: hậu xử lý 3.300 kết quả cùng các phiên có 435 phiên tạo khóa
mô hình, 28 phiên xác nhận thất bại và bị hủy. Không che ca thất bại. Y_pre là
vật liệu trước hậu xử lý; Y_final là đầu ra mô hình đo được sau toàn bộ các bước.

### 6:15–7:00 — Tái lập và giới hạn

Bấm **Tải CSV** trong **Nhật ký phiên** để cho thấy chỉ có thống kê công khai.
Chỉ các manifest `complete` được dùng làm kết quả. Giới thiệu `tests/self_check.py`,
`bb84_lab/research/verify_quantum.py`, `selection.json` và các seed/cấu hình đã lưu.

Mở nhanh **Giới thiệu** để chốt câu hỏi “nếu không dùng BB84”: B92/E91 là các
phương án QKD cần mô hình đo khác; ML-KEM phù hợp khi chỉ có hạ tầng phần mềm;
DH/ECDH là đối sánh cổ điển và không chống máy lượng tử đủ mạnh. ChaCha20-Poly1305
không thay BB84 vì nó mã hóa dữ liệu sau khi khóa đã được thiết lập.

Kết thúc bằng phạm vi: mạch một qubit được đối chiếu Qiskit/Aer; không có phần cứng
quang học. Wilson và ngân sách entropy là công cụ giáo dục, chưa phải chứng minh
finite-key/composable. Kết quả “chưa tìm được tỷ lệ tốt hơn B0 theo tiêu chí đã
đặt” vẫn là kết quả nghiên cứu hợp lệ.

## Phương án CLI nếu cần trình bày qua terminal

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --eve 1
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --noise 0.1
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --eve 0.1
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --signals 16
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --signals 1024
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --tamper-transcript
.\.venv\Scripts\python.exe -m bb84_lab.demo aead --message "Xin chào"
```

Lệnh sửa transcript dự kiến thoát với mã **2**. Phiên bị giám sát hủy hoặc thiếu
khóa vẫn trả JSON thống kê, với `encryption: null`; đó là kết quả cần trình bày.
