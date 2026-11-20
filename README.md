# BB84 Lab — mô phỏng, giám sát QBER và demo mã hóa

Giao diện tiếng Việt cho Alice–Bob–Eve, giám sát QBER, hậu xử lý khóa ở mức giáo dục và ChaCha20-Poly1305. Bộ nghiên cứu tách hiệu chỉnh với đánh giá độc lập, lưu dữ liệu tái lập và xuất năm nhóm biểu đồ.

**Đây là mô phỏng cổ điển. Seed nghiên cứu là công khai; khóa mô phỏng có thể tái tạo khi biết dữ liệu công khai của giao thức. Không dùng khóa này bảo vệ dữ liệu thật.** Khoảng Wilson và ngân sách entropy dưới đây không phải chứng minh an toàn QKD finite-key/composable.

## Chạy giao diện

Đã kiểm chứng trên Windows, Python 3.14.5. Chạy PowerShell tại thư mục dự án:

```powershell
cd E:\Project_MHMM
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tests.self_check
.\.venv\Scripts\python.exe -m bb84_lab.app --open
```

Mở `http://127.0.0.1:8765`. Server chỉ lắng nghe loopback; nhấn `Ctrl+C` để dừng. Nếu cổng đang dùng, chạy `python -m bb84_lab.app --port 8766 --open`. Không cần Node.js, tài khoản cloud hoặc kích hoạt môi trường ảo.

Trang **Mô phỏng** có năm kịch bản, tham số QBER, biểu đồ Wilson, luồng xử lý khóa, sơ đồ vai trò BB84 → hậu xử lý → ChaCha20-Poly1305, kiểm tra AEAD và lịch sử 10 phiên gần nhất trong bộ nhớ trang. Sau mỗi phiên, **Nhật ký kiểm chứng thực thi** hiển thị công thức đã thay số, module/hàm backend thực sự được gọi, kích thước key/nonce/AAD/tag, kết quả sửa bản mã/phát lại và dấu vân tay SHA-256; có thể tải JSON công khai để đối chiếu. Trang **Giới thiệu** đối sánh BB84 với B92, E91, ML-KEM và DH/ECDH, đồng thời chỉ rõ dữ liệu cần quan sát ở mỗi phương án. **Tải CSV** chỉ xuất thống kê công khai. Trang **Thí nghiệm** đọc bộ đã hoàn tất trong `outputs/study/`; dùng `python -m bb84_lab.app --study-dir outputs/study-new` để xem bộ khác. Kịch bản trình bày 5–7 phút: [docs/DEMO.md](docs/DEMO.md).

## Chạy bằng CLI

```powershell
# Kênh sạch: mô phỏng, giám sát, Cascade, xác nhận, Toeplitz và AEAD
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84

# Eve toàn phần; chỉ nhiễu; can thiệp yếu; thiếu mẫu
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --eve 1
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --noise 0.1
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --eve 0.1
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --signals 16

# Xác thực thất bại: hủy phiên, mã thoát 2
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --tamper-transcript

# Chỉ giám sát; hoặc demo AEAD riêng bằng khóa ngẫu nhiên từ hệ điều hành
.\.venv\Scripts\python.exe -m bb84_lab.demo bb84 --monitor-only
.\.venv\Scripts\python.exe -m bb84_lab.demo aead --message "Xin chào"
```

Lệnh `bb84` trả JSON gồm cấu hình/seed, QBER, số bit, dữ liệu tiết lộ, trạng thái hậu xử lý, kết quả kiểm tra mã hóa và `verification` với từng bước tính toán cùng SHA-256 của log. `bb84_key_released: true` chỉ có nghĩa đã tạo **khóa mô hình**; không chứng nhận khóa bí mật trước đối thủ thực tế. Không xuất khóa, bit thô, giá trị mẫu công khai, nonce, bản rõ, bản mã hoặc PSK trong kết quả/nhật ký.

## Quy tắc mô hình và hủy phiên

`f` là xác suất Eve chặn–đo–gửi lại độc lập mỗi tín hiệu. `p` là xác suất lật bit sau phép đo Bob, không phải tham số depolarizing. Kỳ vọng trên chuỗi sàng lọc: `q = p + f/4 - p*f/2`; khi `f=1, p=0`, kỳ vọng bằng 25%.

Lấy `floor(alpha * n_sift)` mẫu theo hoán vị độc lập với giá trị bit và loại các vị trí đó khỏi vật liệu khóa của cả hai phía. Mặc định `alpha=25%`, ít nhất 100 mẫu, ngưỡng vận hành `tau=5%`. Thiếu mẫu không được gán QBER mặc định bằng 0.

| Trạng thái giám sát | Điều kiện Wilson 95% | Hành động |
|---|---|---|
| `continue` | Đủ mẫu, cận trên ≤ tau | Cho phép hậu xử lý |
| `anomalous` | Đủ mẫu, cận dưới > tau | Hủy; nghi can thiệp hoặc nhiễu cao |
| `inconclusive` | Khoảng cắt ngưỡng hoặc thiếu mẫu | Hủy việc đi tiếp |

Mỗi phiên kiểm tra một lần ở cỡ mẫu đã chốt. QBER cao không xác định chắc chắn Eve; QBER thấp không xác nhận vắng Eve. Bộ giám sát chỉ đọc mẫu công khai đã xác thực, không dùng nhãn `f`, `p` hay vị trí nghe lén để quyết định.

Hậu xử lý gồm Cascade giáo dục bốn lượt với lookback, xác nhận SHA-256 và Toeplitz universal-2. Bob sửa bit qua parity, không sao chép chuỗi Alice. Mỗi truy vấn công khai parity hai phía tính **2 bit rò rỉ**, kể cả truy vấn lặp. Xác nhận tính **257 bit**: digest 256 bit và phản hồi chấp nhận 1 bit. Mọi thông điệp đi qua HMAC-SHA256 với PSK độc lập, được cung cấp ngoài BB84.

Với `n` bit sau loại mẫu, `q_upper` là cận trên Wilson và `h2` là entropy nhị phân, độ dài đầu ra của **giả định entropy giáo dục** là:

```text
ell = 8 * floor(max(0, floor(n * (1 - h2(q_upper)))
                       - parity_leak_bits - 257 - 64) / 8)
```

Hủy nếu `q_upper >= 0.5`, xác nhận thất bại, hai đầu ra khác nhau hoặc `ell < 256`. Không đệm, lặp bit hoặc băm chuỗi ngắn để lách điều kiện này. Khi thành công, lấy 256 bit đầu ra cho ứng dụng; Y_final vẫn là toàn bộ `ell` bit trước bước đó. 64 bit trừ thêm là biên dự phòng của mô hình, không phải tham số an toàn đã chứng minh.

ChaCha20-Poly1305 dùng API của `cryptography`. HKDF-SHA256 chỉ ràng buộc khóa đã hậu xử lý với salt phiên mới 128 bit; không thay đối soát, Toeplitz hay tạo thêm entropy bí mật. Nonce là bộ đếm 96 bit, AAD chứa phiên bản/phiên/vai trò/số thứ tự; chỉ trả bản rõ sau xác thực và từ chối phát lại. Không lưu khóa để khôi phục sau khởi động lại. Demo giới hạn một chiều Alice→Bob trong một tiến trình.

## Nghiên cứu và biểu đồ

Cài phần nghiên cứu khi cần tạo lại biểu đồ hoặc chạy Qiskit/Aer; giao diện và self-check cơ bản chỉ cần `requirements.txt`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-research.txt
.\.venv\Scripts\python.exe -m pip check

# Đối chiếu mạch một qubit; tên output phải mới
.\.venv\Scripts\python.exe -m bb84_lab.research.verify_quantum --output outputs/quantum-new.json

# Runner đơn giản; mặc định đọc configs/smoke.json
.\.venv\Scripts\python.exe -m bb84_lab.research.experiments --output outputs/smoke-new

# Smoke study không cần thư viện nghiên cứu
.\.venv\Scripts\python.exe -m bb84_lab.research.study --quick --no-plots --output outputs/study-smoke-new

# Bộ đầy đủ; thư mục đầu ra phải chưa tồn tại
.\.venv\Scripts\python.exe -m bb84_lab.research.study --output outputs/study-new

# Đo Y_final trên cùng các phiên đã có; không chọn lại tỷ lệ mẫu
.\.venv\Scripts\python.exe -m bb84_lab.research.study --output outputs/study-new --postprocess

# Vẽ lại năm nhóm biểu đồ PNG/SVG từ dữ liệu đã đo
.\.venv\Scripts\python.exe -m bb84_lab.research.plot_results outputs/study-new
```

`requirements-research.txt` khóa các phiên bản đã kiểm chứng, gồm Qiskit 2.6.2, Aer 0.18.2 và Matplotlib 3.11.2. Mạch kiểm chứng tám trường hợp chuẩn bị/đo Z/X bằng Statevector và Aer; phép tính có điều kiện Eve toàn phần cho QBER 1/4. Kết quả đã chạy: `outputs/quantum_check.json`, 8.192 shots/trường hợp.

Quy trình nghiên cứu theo `configs/study.json`:

1. Chạy 1.800 phiên chính: 60 cấu hình × 30 seed, lấy mẫu chuẩn 25%.
2. Lấy 450 phiên trong bộ chính làm hiệu chỉnh, xử lý ghép cặp ba tỷ lệ 10%/25%/50% trên cùng dữ liệu đo và hoán vị mẫu: 1.350 kết quả.
3. Chọn tỷ lệ theo tiêu chí §8.6 đặt trước, ghi `selection.json` và đóng băng hash trước bộ đánh giá. Không có ứng viên đạt đủ thì giữ B0=25%.
4. Chạy 1.500 phiên seed mới: 100 phiên × 15 cấu hình, ba tỷ lệ mỗi phiên tạo 4.500 kết quả ghép cặp. Không chọn lại tỷ lệ từ bộ này.
5. `--postprocess` đo hậu xử lý cho các phiên chính và B0/tỷ lệ đã chọn ở bộ đánh giá. Đây là xử lý lại **cùng phiên**, không tăng tổng 3.300 phiên độc lập.

Seed chính và đánh giá rời nhau. Chênh lệch Y_pre dùng bootstrap ghép cặp 95%, kèm phân bố; tỷ lệ trạng thái có khoảng Wilson. Khảo sát ngưỡng 3%/8% chỉ mang tính mô tả, không dùng đổi tiêu chí sau đánh giá. Y_pre bằng số bit sau loại mẫu nếu `continue`, ngược lại bằng 0. Y_final bằng đầu ra hậu xử lý đo được, bằng 0 khi hủy, thất bại hoặc thiếu ngân sách.

| Tệp trong bộ kết quả | Nội dung |
|---|---|
| `manifest.json` | Cấu hình, môi trường, seed, số phiên, hash lựa chọn và trạng thái |
| `main.csv`, `calibration.csv`, `evaluation.csv` | Thống kê từng phiên/phương án; đánh dấu bộ hiệu chỉnh |
| `selection.json`, `evaluation_checks.json` | Lựa chọn đóng băng và kiểm tra trên seed mới |
| `paired_differences.csv`, `paired_summary.json` | Chênh lệch Y_pre theo cặp, khoảng bootstrap và phân bố |
| `postprocessing.csv`, `postprocessing_summary.json` | Rò rỉ, trạng thái, Y_final, thời gian, kết quả khôi phục |
| `postprocessing_manifest.json` | Tiến độ/phạm vi hậu xử lý; chỉ dùng bản `complete` |
| `summary.json`, `*_summary.json` | Tổng hợp theo cấu hình cho giao diện và biểu đồ |
| `figures/` | Năm nhóm biểu đồ, mỗi nhóm có PNG và SVG |

Giữ manifest cùng dữ liệu. Thư mục đầu ra có sẵn bị từ chối; `--postprocess` cũng từ chối ghi đè tệp hậu xử lý cũ. Thời gian chạy, ID phiên và nội dung khóa không phải giá trị tái lập; giám sát, số bit và lựa chọn dựa trên seed/cấu hình cố định. Không gọi tốc độ phần mềm mô phỏng là tốc độ QKD vật lý.

Có thể xóa `outputs/` mà không làm hỏng mã nguồn, demo mô phỏng hoặc self-check. Việc này xóa dữ liệu đã đo và biểu đồ; trang **Thí nghiệm** sẽ trống đến khi tạo lại study. Để khôi phục bộ mặc định, chạy study với `--output outputs/study`, rồi `--postprocess`; cần thư viện nghiên cứu để vẽ biểu đồ. Nếu chỉ dọn file dư, giữ `outputs/study/`, `outputs/main/`, `outputs/quantum_check.json` và ảnh demo; các bộ smoke, bản kiểm chứng tạm và ZIP mã cũ đã được dọn.

Chạy nhanh để kiểm tra điều phối: `python -m bb84_lab.research.study --quick --output outputs/study-smoke-new`. Bộ này được đánh dấu `smoke`, không dùng kết luận nghiên cứu. Runner đơn giản `python -m bb84_lab.research.experiments --config configs/smoke.json --output outputs/smoke-new` vẫn có sẵn.

## Kết quả đã đo

`outputs/study/` đã hoàn tất 3.300 phiên độc lập và năm nhóm biểu đồ. Lựa chọn đóng băng là **25%**: chưa tìm được ứng viên cải thiện đạt đủ tiêu chí. Trên bộ hiệu chỉnh, tỷ lệ 10% tăng Y_pre khoảng 14,07% ở nhóm không Eve/nhiễu thấp nhưng giảm phát hiện tối đa 23,33 điểm phần trăm so với B0; tỷ lệ 50% giảm hiệu suất. Đây là kết quả thực nghiệm, không sửa tiêu chí để tạo kết luận cải tiến.

Ví dụ bộ chính, N=4.096, p=0, lấy mẫu 25%, mỗi hàng có 30 phiên:

| f | QBER trung bình | Bất thường | Chưa đủ bằng chứng | Continue |
|---|---:|---:|---:|---:|
| 0 | 0% | 0/30 | 0/30 | 30/30 |
| 0,1 | 2,556% | 0/30 | 4/30 | 26/30 |
| 1 | 24,947% | 30/30 | 0/30 | 0/30 |

Hậu xử lý đã đo 3.300 kết quả trên cùng các phiên: **435 phiên tạo khóa mô hình**, **28 phiên xác nhận thất bại và bị hủy**; các phiên còn lại bị bỏ qua hoặc thiếu ngân sách. Mỗi phiên `ready` đã kiểm tra hai khóa khớp và AEAD khôi phục đúng. Riêng bộ đánh giá không Eve/không nhiễu/B0 có 100/100 phiên `ready`, Y_final trung bình 1.067,76 bit; khoảng Wilson 95% cho tỷ lệ `ready` xấp xỉ [96,30%; 100%]. Không diễn giải tỷ lệ hữu hạn này thành bảo đảm cho phiên tương lai.

## Kiểm chứng, tổ chức mã và giới hạn

`tests/self_check.py` kiểm tra loại mẫu, Wilson, đầu vào sai, QBER lý thuyết, Cascade/lookback, Toeplitz so với ma trận nhỏ, thất bại xác nhận/thiếu ngân sách, xác thực, AEAD bị sửa/phát lại, nonce và HTTP local. Kiểm tra nghiên cứu chạy bộ smoke từ đầu đến hậu xử lý, kiểm tra seed rời nhau, dữ liệu ghép cặp, hash lựa chọn đóng băng, từ chối ghi đè và import giữa các package. Không chạy với `python -O`, vì tùy chọn đó tắt assert. Qiskit/Aer có kiểm chứng riêng như trên.

| Đường dẫn | Trách nhiệm |
|---|---|
| `bb84_lab/bb84.py` | Mô phỏng Z/X, Eve/nhiễu, sàng lọc, lấy mẫu và giám sát |
| `bb84_lab/postprocess.py` | Cascade, xác nhận, kế toán rò rỉ và Toeplitz |
| `bb84_lab/secure_channel.py` | HMAC transcript, HKDF ràng buộc phiên và ChaCha20-Poly1305 |
| `bb84_lab/demo.py` | Điều phối phiên tích hợp và CLI/demo AEAD riêng |
| `bb84_lab/app.py`, `web/` | HTTP local và giao diện HTML/CSS/JavaScript, không CDN |
| `bb84_lab/research/experiments.py`, `bb84_lab/research/study.py` | Runner thống kê và quy trình hiệu chỉnh/đánh giá |
| `bb84_lab/research_analysis.py` | Thống kê thuần, tiêu chí chọn tỷ lệ mẫu và bootstrap ghép cặp dùng chung |
| `bb84_lab/research/plot_results.py`, `bb84_lab/research/verify_quantum.py` | Biểu đồ từ dữ liệu và kiểm chứng Qiskit/Aer |
| `tests/self_check.py` | Kiểm tra assert trực tiếp, không test framework |
| `docs/` | Đề cương, kịch bản demo và hồ sơ tổ chức lại cấu trúc |
| `configs/`, `outputs/` | Cấu hình nguồn tách khỏi dữ liệu/biểu đồ sinh ra |

Package đặt ngay tại gốc để chạy bằng `python -m ...` từ checkout, không cần cài editable hoặc sửa `PYTHONPATH`. Chỉ nhóm nghiên cứu có thêm một cấp thư mục; không tạo tầng tiện ích hay framework mới. Cây thư mục, ánh xạ từng file và quan hệ import: [docs/REORGANIZATION.md](docs/REORGANIZATION.md).

`outputs/` và `.venv/` được `.gitignore` loại khỏi mã nguồn. Đề cương và tài liệu tham khảo: [docs/de_cuong_QKD_3_tuan.md](docs/de_cuong_QKD_3_tuan.md).

Mã Python chỉ nằm trong `bb84_lab/` và `tests/`; 11 file chuyển tiếp tại gốc đã được xóa theo yêu cầu. Chạy các lệnh `python -m ...` từ gốc dự án như hướng dẫn phía trên. Import dùng đường dẫn package, ví dụ `from bb84_lab.bb84 import Config` và `from bb84_lab.research.study import run_study`.

Tài nguyên `web/`, cấu hình mặc định và thư mục tạm self-check được xác định theo project root từ `__file__`. Với CLI, `--config`, `--output`, đối số thư mục biểu đồ và `--study-dir` tường minh vẫn tính đường dẫn tương đối theo thư mục làm việc như trước.

Giới hạn còn lại là phạm vi nghiên cứu: không có photon/thiết bị lượng tử thật, không chứng minh an toàn finite-key/composable hay chống tấn công thiết bị. Cascade giáo dục có thể thất bại và phải hủy; PSK được cung cấp trong bộ mô phỏng, chưa có hạ tầng cấp khóa giữa hai máy thật. Giao diện chỉ chạy local, không có triển khai mạng công cộng, quản lý khóa lâu dài hoặc kênh hai chiều.
