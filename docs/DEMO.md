# Kịch bản demo BB84 Lab — 5–7 phút

Nếu trình bày cả BB84 và E91 qua mạng hai máy, dùng
[kịch bản kết hợp khoảng 8 phút](#kịch-bản-kết-hợp-bb84-hai-máy-và-e91).

## Chuẩn bị

```powershell
# Chạy tại gốc checkout sau khi cài đặt theo README
.\.venv\Scripts\python.exe -m tests.self_check
.\.venv\Scripts\python.exe -m bb84_lab.local --open
```

Mở `http://127.0.0.1:8765`. Giữ seed **2026**, tỷ lệ mẫu **25%**, ngưỡng **5%**,
mẫu tối thiểu **100**. Trang **Thí nghiệm** đọc bộ hoàn tất trong `outputs/study/`,
không tự chạy 3.300 phiên khi bấm xem. Clone mới không kèm dữ liệu này.
Muốn tái tạo, dùng lệnh trong [README tiếng Việt](../README.vi.md) hoặc
[tài liệu nghiên cứu](RESEARCH.md); dùng `--study-dir` để chọn bộ khác.

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

Ở **Dữ liệu đến Bob**, đối chiếu số byte UTF-8, bản mã cộng tag và số byte
khôi phục được backend xác nhận. Ví dụ nhập `Chào Bob!`: 10 byte đầu vào,
26 byte bản mã cộng tag, 10 byte khôi phục. Kích thước này chưa tính nonce,
AAD và thông tin đóng gói. Khi đổi đầu vào, kết quả cũ được đánh dấu cho đến
khi bấm chạy lại; giao diện không dựng bản rõ Bob từ ô nhập Alice.

Mở **Khóa đã đi qua những bước nào?** để xem năm bước hậu xử lý. Mở
**Nhật ký kiểm chứng thực thi**. Chỉ vào các dòng `BB84-01` đến
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

Mở **Mã hóa & xác thực thông điệp**, nhập thông điệp rồi bấm **Kiểm tra AEAD**.
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

Bấm **Tải CSV** trong **Các phiên vừa chạy** để cho thấy chỉ có thống kê công khai.
Chỉ các manifest `complete` được dùng làm kết quả. Giới thiệu `tests/self_check.py`,
`bb84_lab/research/verify_quantum.py`, `selection.json` và các seed/cấu hình đã lưu.

Mở nhanh **Giới thiệu** để đối chiếu các cách thiết lập khóa. Tab **E91** minh họa
phép đo trên các cặp vướng víu. B92 là phương án QKD dùng hai trạng thái không
trực giao. ML-KEM phù hợp khi chỉ có hạ tầng phần mềm. DH/ECDH là đối sánh cổ
điển và không chống máy lượng tử đủ mạnh. ChaCha20-Poly1305 mã hóa dữ liệu sau
khi khóa đã được thiết lập.

Kết thúc bằng phạm vi: mạch một qubit được đối chiếu Qiskit/Aer; không có phần cứng
quang học. Wilson và ngân sách entropy là công cụ giáo dục, chưa phải chứng minh
finite-key/composable. Kết quả “chưa tìm được tỷ lệ tốt hơn B0 theo tiêu chí đã
đặt” vẫn là kết quả nghiên cứu hợp lệ.

## Trình diễn cơ chế trên web

Dùng các trang dưới đây để trình diễn phép đo hoặc mã hóa. Có thể thay phần
đọc log chi tiết bằng một mục, hoặc trình diễn riêng sau kịch bản 5–7 phút.

### BB84 từng bước

1. Mở **BB84 từng bước**, chọn **Kênh sạch**, seed `2026`, bấm **Tạo 16 tín hiệu**.
2. Bấm **Bước tiếp theo**: giải thích bit/cơ sở, trạng thái, Eve, Bob đo,
   sàng lọc, công khai mẫu, rồi QBER. Các ô chưa đến bước vẫn bị che bằng `·`.
3. Bấm số thứ tự tín hiệu để xem sơ đồ X/H/I/M và xác suất Bob đo. Phân biệt
   xác suất lý thuyết với kết quả đo cụ thể và với dữ liệu Aer đã lưu.
4. Đổi sang **Eve chặn toàn bộ**, tạo lại, rồi **Hiện toàn bộ**. Với seed này,
   bài học thu 9 vị trí cùng cơ sở, 2 mẫu và 1 sai khác (QBER mẫu 50%). Đây là
   mẫu cực nhỏ; không nhầm với kỳ vọng 25% trên nhiều tín hiệu.
5. Chỉ vào bước Eve đo rồi chuẩn bị lại và những ô mẫu sai khác. Nhấn mạnh:
   các bit trên màn hình là bài học công khai, không dùng tạo khóa ứng dụng;
   16 tín hiệu không đủ 100 mẫu kiểm tra.

### Mã hóa và chủ động gây lỗi

1. Mở **Mã hóa**. Giữ **Kênh sạch**, N `4096`, seed `2026`, nhập `Chào Bob!`.
   Bấm **Thiết lập phiên và mã hóa**. Mỗi lần tạo là một phiên mới.
2. Xem sơ đồ hai đường: BB84 → hậu xử lý → HKDF tạo khóa ứng dụng; văn bản
   đi trực tiếp vào ChaCha20-Poly1305. Dữ liệu không truyền qua kênh lượng tử.
3. Đối chiếu 10 byte UTF-8, 10 byte phần bản mã, 16 byte tag; tổng bản mã + tag
   là 26 byte, chưa gồm nonce/AAD/đóng gói. Xem đoạn hex thực tế và tag riêng.
4. Bấm **Sửa một byte**: backend lật một bit, xác thực thất bại, không trả
   bản rõ. Gói gốc không bị thay đổi.
5. Bấm **Bob giải mã gói gốc**: phần nhận hiện chính `Chào Bob!` do backend
   giải mã và đối chiếu. Bấm **Phát lại gói**: bị từ chối theo số thứ tự;
   thông điệp đang thấy vẫn là kết quả hợp lệ trước đó, không phải lần nhận mới.
6. Đổi sang **Eve chặn toàn bộ**, tạo lại để thấy không phát hành gói mã hóa.
   Các bản rõ/bản mã của lượt cũ được xóa khỏi vùng kết quả.

Gói hết hạn sau 10 phút hoặc có thể bị thay thế khi bộ nhớ đạt giới hạn.
Chỉ dùng thông điệp thử nghiệm công khai; bản rõ/bản mã không đưa vào log/CSV.

### E91 và phép kiểm tra CHSH

Kịch bản khoảng 3–4 phút. Mở dashboard cục bộ rồi vào tab **E91**.

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.local --open
```

**0:00–0:30 · Chạy hai lượt.** Điền **Số cặp N = 4096**, **Seed = 2026**,
đặt **Xác suất nhiễu trắng = 50%**, rồi bấm **So sánh lý tưởng và có nhiễu**.
Chỉ vào dòng cấu hình chung phía trên biểu đồ.

> Đây là mô phỏng phép đo E91 trên các cặp singlet. Nút này chạy hai lượt
> với cùng 4.096 cặp và cùng seed. Lượt lý tưởng dùng nhiễu 0%, lượt còn
> lại dùng nhiễu trắng 50%.

**0:30–1:25 · Đọc hai biểu đồ.** Trên biểu đồ **CHSH |S|**, chỉ vào vạch
đứt ở 2, hai thanh và khoảng 95% dưới mỗi thanh. Trên biểu đồ **QBER**,
chỉ vào số lỗi và mẫu số 969 bên dưới hai thanh.

> Vạch 2 là giới hạn CHSH của mô hình cổ điển cục bộ. Ở lượt lý tưởng,
> |S| khoảng 2,83 và cả khoảng 95% nằm trên 2. Với nhiễu 50%, |S| giảm còn
> khoảng 1,34 và cả khoảng nằm dưới 2. QBER trên các cặp đo cùng hướng
> tăng từ 0% lên 24,87%.

**1:25–2:25 · Mở log lý tưởng.** Bấm **Xem nhật ký lý tưởng**. Chỉ vào
nhãn nhiễu `0%`, hàng `0° / 45°` trong **Nhật ký tính CHSH** và phép cộng
bốn hệ số bên dưới. Cuộn đến **Nhật ký tính QBER** để chỉ hai hàng có 0 lỗi.

> Hai dấu trong bảng lần lượt là kết quả của Alice và Bob. Ở hàng
> 0° / 45°, lấy số cùng dấu trừ số trái dấu rồi chia 451. Ta có
> (29 + 25 − 196 − 201) / 451 ≈ −0,7605. Ghép bốn hệ số bằng các dấu
> cộng, trừ, cộng, cộng thì S ≈ −2,8313. Biểu đồ dùng trị tuyệt đối của S.
> Hai nhóm đo cùng hướng có tổng cộng 0 lỗi trên 969 cặp sau khi Bob đảo bit.

**2:25–3:30 · Mở log có nhiễu.** Cuộn lên hai biểu đồ, bấm
**Xem nhật ký có nhiễu**. Chỉ vào nhãn nhiễu `50%`, cùng hàng `0° / 45°`
và hai dòng đếm lỗi trong **Nhật ký tính QBER**.

> Với nhiễu 50%, hàng 0° / 45° cho (75 + 75 − 150 − 151) / 451 ≈ −0,3348.
> Ghép đủ bốn hàng thì S ≈ −1,3359. QBER dùng 495 cặp ở 45° / 45° và
> 474 cặp ở 90° / 90°. Sau khi Bob đảo bit, các lượt vốn cùng dấu trở thành
> lỗi. Hai hàng có 102 và 139 lỗi, nên QBER là 241 / 969 ≈ 24,87%.

**3:30–3:45 · Nêu phạm vi.** Quay lại hai biểu đồ.

> Hai lượt cho thấy nhiễu trong mô hình làm tương quan CHSH yếu đi và lỗi
> tăng lên. Phần này chạy trong dashboard mô phỏng. Trong demo truyền tệp,
> Alice và Bob có thể chọn BB84 hoặc E91 khi thiết lập hai máy.

Nếu còn thời gian, đặt nhiễu `30%` và bấm so sánh lại. Với cùng số cặp và
seed, khoảng 95% của |S| từ `1,2981` đến `2,5170` cắt qua mốc 2. Lượt này
chưa đủ bằng chứng để kết luận tương quan vượt giới hạn cổ điển.

## Kịch bản kết hợp BB84 hai máy và E91

Thời lượng dự kiến 8 phút. Cả hai lượt gửi cùng tệp `demo.png` qua
**Alice → Eve → Bob**. Eve giữ chế độ **Chỉ chuyển tiếp** ở cả hai lượt.

| Người | Vị trí | Phụ trách |
|---|---|---|
| **A** | Máy gửi | Dẫn demo, chạy Setup Alice, gửi tệp và đọc mã phiên. |
| **B** | Máy nhận | Chạy Setup Bob, xác nhận tệp, chiếu nhật ký BB84 và E91. |
| **C** | Máy gửi | Kiểm tra Eve, chuyển nguồn chiếu và tổng hợp số liệu hai lượt. |

Nếu nhóm có hai người, A kiêm C. Nếu có bốn người, D đọc bảng so sánh và kết
thúc. Chỉ chuyển nguồn chiếu khi người đang nói nhắc tên người kế tiếp.

### Trước giờ chiếu

1. Dùng cùng bản mã nguồn trên hai máy, tạo môi trường `.venv` riêng và kết
   nối vào cùng LAN hoặc VPN riêng. B lấy IPv4 của máy nhận bằng `ipconfig`
   và gửi địa chỉ cho A. Chuẩn bị ảnh PNG nhỏ `demo.png` trên máy gửi.
2. Mở PowerShell tại thư mục dự án trên mỗi máy và chạy lệnh bên dưới. B
   tạo PSK hoặc dùng tệp sẵn có. Chép đúng tệp sang A qua kênh riêng, rồi
   A chọn **Nhập tệp PSK**. Cả hai máy phải báo **PSK đã sẵn sàng**. Để
   màn hình Setup mở trước khi bắt đầu chiếu.
3. C chuẩn bị một bảng ghi hai cột **BB84** và **E91**. Chừa chỗ cho mã
   phiên, QBER mẫu, khoảng Wilson 95%, bit giữ lại, đầu ra Toeplitz và
   SHA-256 tệp nhận. Cột E91 thêm `|S|` và khoảng 95% của nó. Chuẩn bị
   tệp ghi chú để dán hai bản **Sao chép tóm tắt**.

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network setup --open
```

Dashboard mặc định ở `http://127.0.0.1:8770` trên mỗi máy. Eve mở tại
`http://127.0.0.1:8770/eve` trên máy gửi. [Thiết lập và kiểm tra mạng](NETWORK_DEMO.md#thiết-lập-alice-và-bob-trong-trình-duyệt)

### 0:00–1:15 · B khởi động Bob, A khởi động Alice và Eve

**Chiếu máy nhận.** B chọn **Bob → BB84** trong **Giao thức tạo khóa**,
nhập IPv4 của máy Bob và cổng `9100`, bấm **Khởi động Bob**. Khi thấy
trang **Bob · Nhận dữ liệu**, B nói “Bob đã sẵn sàng, mời Alice.”

**Chuyển sang máy gửi.** A chọn **Alice → BB84**, nhập IPv4 và cổng của
Bob, tích **Chạy kèm Eve trên máy Alice**, bấm **Khởi động Alice và Eve**.
C mở **Bảng điều khiển Eve**, chỉ chế độ **Chỉ chuyển tiếp**, rồi trả
màn hình về Alice.

> **A nói** “Nhóm sẽ gửi cùng một tệp qua Eve hai lần. Lượt đầu Alice và
> Bob thiết lập khóa bằng BB84. Eve chuyển tiếp ở cả hai lượt để nhóm
> đối chiếu bước thiết lập khóa của hai giao thức.”

### 1:15–3:05 · A gửi tệp BB84, B thu log trước khi đổi giao thức

**A** chọn `demo.png`, bấm **Gửi tệp**, chờ **Hoàn tất** và đọc vài ký
tự đầu của mã phiên để dẫn sang màn hình Bob. C có thể chỉ dòng **Đã
chuyển tiếp biên nhận của Bob** trong nhật ký Eve để xác nhận đường đi.

**Chuyển sang máy nhận.** B mở **Bob đã nhận** và ghi lại SHA-256 đã
khớp. Đối chiếu mã phiên với Alice, rồi mở **Terminal tạo khóa → Xem log
chi tiết → BB84**. Chỉ một dòng giữ hoặc loại theo cơ sở Z/X và quay về
tóm tắt để đọc QBER, Wilson và quyết định. Chỉ thêm một truy vấn parity
ở **Cascade** và một dòng đầu ra ở **Toeplitz**.

> **B nói** “BB84 giữ các vị trí cùng cơ sở, công khai một phần để tính
> QBER rồi loại mẫu đó. Nếu qua kiểm tra, hai bên đối soát bằng Cascade
> và rút ngắn chuỗi bằng Toeplitz. Phiên đã xác nhận khóa ứng dụng và
> Bob nhận đúng tệp.”

**B bấm Sao chép tóm tắt**, dán vào cột BB84. Chụp màn hình các dòng log
chi tiết muốn chiếu lại và dòng SHA-256 trước khi dừng. C ghi số liệu thực
tế. B nói “Đã lưu log BB84, mời A và C chuyển sang E91.”

### 3:05–4:30 · A và B đổi giao thức trong Setup

1. A và B nhấn `Ctrl+C` ở cửa sổ PowerShell đang chạy Setup trên hai máy,
   rồi chạy lại lệnh `setup --open` ở trên. Dừng máy gửi cũng dừng Eve.
2. **Chiếu máy nhận.** B chọn **Bob → E91**, giữ IPv4 và cổng `9100`,
   bấm **Khởi động Bob**. Dùng lại PSK đã có. B nói “Bob đã chọn E91.”
3. **Chuyển sang máy gửi.** A chọn **Alice → E91**, nhập lại IPv4 và cổng
   của Bob, tích **Chạy kèm Eve trên máy Alice**, bấm **Khởi động Alice
   và Eve**. C mở lại hoặc tải lại tab Eve, chỉ **E91** và **Chỉ chuyển tiếp**.

> **C nói** “Hai đầu đã chọn E91. Địa chỉ Bob, PSK, tệp và đường đi qua
> Eve giữ nguyên. Bây giờ phiên sẽ dùng thêm phép kiểm tra CHSH.”

### 4:30–6:45 · A gửi lại cùng tệp, B đọc log E91

**A** chọn lại chính tệp `demo.png`, bấm **Gửi tệp**, chờ **Hoàn tất** rồi
đọc mã phiên mới. **Chuyển sang máy nhận.** B mở **Bob đã nhận**, so SHA-256
với ghi chú lượt BB84. B đối chiếu mã phiên E91 với Alice, rồi chỉ
`|S|`, khoảng 95%, QBER và quyết định giám sát đang hiển thị.

**B bấm** **Terminal tạo khóa → Xem log chi tiết → E91 · CHSH và QBER**.
Chỉ một hàng **Tương quan**, dòng **Ghép bốn hạng CHSH**, rồi dòng
**Kiểm tra QBER**. Chỉ lại **Cascade**, **Toeplitz** và **Khóa ứng dụng
đã khớp** để nối phần đo với phần truyền tệp. Sao chép tóm tắt lượt E91.

> **B nói** “E91 dùng bốn tổ hợp góc để tính CHSH. Hai nhóm đo cùng hướng
> cung cấp vật liệu khóa. Bob đảo bit rồi hai bên lấy một phần làm mẫu
> QBER. Trong lượt này, cận dưới của khoảng `|S|` vượt 2 và QBER đạt điều
> kiện mô hình, nên phiên tiếp tục qua hậu xử lý và gửi tệp.”

### 6:45–8:00 · C đối chiếu log, A kết thúc

**C chiếu bảng ghi của hai lượt.** Đọc các số đo vừa lưu trên Bob.

| Cần đối chiếu | BB84 | E91 |
|---|---|---|
| Giám sát trước hậu xử lý | Sàng lọc theo cơ sở Z/X, QBER mẫu và Wilson 95%. | Bốn hệ số tương quan và khoảng 95% của `|S|`, cùng QBER mẫu và Wilson 95%. |
| Mã phiên | Trùng giữa Alice và Bob trong lượt BB84. | Trùng giữa Alice và Bob trong lượt E91, khác lượt BB84. |
| Sau khi đạt giám sát | Cascade → Toeplitz → xác nhận khóa → truyền tệp. | Cùng các bước hậu xử lý và truyền tệp. |
| Bằng chứng tệp nhận | Bob báo hoàn tất và ghi SHA-256. | SHA-256 trùng lượt BB84 khi gửi cùng nội dung. |

> **C nói** “Điểm khác thấy rõ trong log là E91 kiểm tra thêm CHSH. Hai
> lượt đều đối soát, xác nhận khóa và nhận được cùng tệp. Mã phiên khác
> nhau vì mỗi lần gửi tạo một phiên mới.”

> **A kết** “Đây là hai luồng thiết lập khóa mô phỏng chạy qua TCP. Kết
> quả cho thấy phần mềm đi qua đúng các bước của từng giao thức và Bob
> nhận đúng dữ liệu trong hai lượt demo.”

Đọc giá trị thực tế trên màn hình. Số bit và QBER có thể khác giữa các lượt.
BB84 mặc định dùng 4.096 tín hiệu, E91 dùng 8.192 cặp. Trình bày số bit đầu
ra như thống kê của mỗi phiên. Sau khi khởi động lại Bob, hộp nhận trên giao
diện bắt đầu trống và tệp đã nhận vẫn nằm trong `outputs/received/`.

Nếu phiên chưa hoàn tất, đọc bước dừng đang hiện. Khi cả hai máy chọn cùng
giao thức và Eve báo **Chỉ chuyển tiếp**, có thể gửi lại một lần. Chỉ xác
nhận hai tệp giống nhau sau khi Bob đã nhận và đối chiếu cả hai SHA-256.

## Phương án CLI nếu cần trình bày qua terminal

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84
.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84 --eve 1
.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84 --noise 0.1
.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84 --eve 0.1
.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84 --signals 16
.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84 --signals 1024
.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84 --tamper-transcript
.\.venv\Scripts\python.exe -m bb84_lab.simulation aead --message "Xin chào"
```

Lệnh sửa transcript dự kiến thoát với mã **2**. Phiên bị giám sát hủy hoặc thiếu
khóa vẫn trả JSON thống kê, với `encryption: null`; đó là kết quả cần trình bày.
