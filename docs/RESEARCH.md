# Mô hình và tái lập nghiên cứu

[README tiếng Việt](../README.vi.md) · [English README](../README.md)

Các kết quả đã đo dưới đây là hiện vật cục bộ, không đi kèm clone mới vì `outputs/` bị Git bỏ qua. Chạy từ gốc repository. Giữ nguyên bộ cũ và chọn tên output mới. Số đo thời gian phụ thuộc máy, không phải tốc độ QKD vật lý.

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

ChaCha20-Poly1305 dùng API của `cryptography`. Trong mô phỏng cùng tiến trình, HKDF-SHA256 ràng buộc khóa đã hậu xử lý với salt phiên mới 128 bit; không thay đối soát, Toeplitz hay tạo thêm entropy bí mật. Nonce là bộ đếm 96 bit, AAD chứa phiên bản/phiên/vai trò/số thứ tự; chỉ trả bản rõ sau xác thực và từ chối phát lại. Không lưu khóa để khôi phục sau khởi động lại. Demo mô phỏng giới hạn một chiều Alice→Bob trong một tiến trình; demo `network` chạy các tiến trình độc lập và HKDF dùng salt suy từ ID phiên chung đã xác thực.

## Mô phỏng E91

Tab **E91** chạy Monte Carlo cục bộ với seed do người xem chọn. Alice chọn
đều và độc lập từ các hướng `0°, 45°, 90°`, Bob chọn từ `45°, 90°, 135°`.
Mỗi đầu có kết quả `+1` hoặc `−1`. Hỗn hợp singlet với nhiễu trắng tỷ lệ
`p` cho tương quan kỳ vọng `E(a,b) = −(1−p) cos(a−b)`, với độ đo của hướng
trong cùng một mặt phẳng. [Bài gốc của Ekert](https://doi.org/10.1103/PhysRevLett.67.661)

- **CHSH** dùng bốn nhóm `(0°,45°)`, `(0°,135°)`, `(90°,45°)` và `(90°,135°)`.
  Mỗi tương quan là `(n++ + n−− − n+− − n−+)/n`. Chỉ số `S` cộng bốn
  tương quan theo dấu `+, −, +, +`. Kỳ vọng của `|S|` theo mô hình là
  `2√2(1−p)`.
- **QBER** dùng hai nhóm cùng hướng `(45°,45°)` và `(90°,90°)`. Kết quả lý
  tưởng đối tương quan. Sau khi quy đổi bằng cách đảo bit của Bob, số lỗi
  là `n++ + n−−`. Cộng số lỗi của hai nhóm rồi chia tổng số lượt của hai
  nhóm để tính QBER. Kỳ vọng theo mô hình là `p/2`.

Khoảng CHSH 95% dùng cận Hoeffding hai phía cho từng trung bình `E`, với
bán kính `sqrt(2 ln(8/0,05)/n)`, rồi ghép bốn cận bằng chặn hợp. Mỗi cận
được chặn trong `[-1,1]`, cộng theo dấu của từng hạng rồi quy đổi sang `|S|`.
Chỉ ghi vượt mốc cổ điển 2 khi cận dưới lớn hơn 2. Khoảng QBER dùng Wilson
95%. Nếu thiếu nhóm cần thiết, giao diện báo chưa đủ dữ liệu cho phép tính
tương ứng. Nhật ký dùng số đếm tổng hợp. Tab E91 cục bộ chỉ minh họa thống
kê phép đo. Khi cần gửi tệp, chọn giao thức trong Setup của demo mạng.

Nút **So sánh lý tưởng và có nhiễu** chạy hai lượt với cùng số cặp và seed.
Lượt lý tưởng dùng `p = 0`, lượt có nhiễu dùng mức đang chọn trong giao
diện. Hai biểu đồ hiển thị `|S|` và QBER đo được của mỗi lượt. Mốc 2 trên
biểu đồ `|S|` là giới hạn cổ điển. Khi trình bày ý nghĩa thống kê, xem thêm
khoảng 95% trong kết quả từng lượt. Giá trị chưa xác định do thiếu mẫu được
để trống trên biểu đồ.

### E91 trong demo mạng

Alice và Bob có thể chọn E91 trong Setup và truyền tệp qua Eve. Mỗi phiên
E91 mặc định mô phỏng 8.192 cặp. Hai máy chọn hướng đo bằng ngẫu nhiên hệ
điều hành. Alice gửi mô tả cổ điển của phép đo qua TCP. Bob sinh kết quả
có điều kiện theo tương quan singlet. Bốn nhóm Bell được dùng để tính CHSH.
QBER mạng chỉ dùng mẫu công khai lấy từ hai nhóm đo cùng hướng. Các bit
mẫu và toàn bộ kết quả đã công khai để tính Bell bị loại khỏi nguyên liệu
khóa. Quá trình này khác với tab E91 cục bộ dùng cả hai nhóm cùng hướng để
minh họa QBER và có seed cố định để tái lập.

Phiên E91 đi tiếp khi cận dưới 95% của `|S|` vượt 2 và kiểm tra QBER theo
khoảng Wilson đạt ngưỡng. Cascade, xác nhận, Toeplitz và ChaCha20-Poly1305
dùng cùng quy trình giáo dục với BB84. Trong chế độ **Làm mất tương quan**,
Eve thay một phần mô tả cặp, khiến Bob sinh kết quả độc lập cho các cặp đó.
Dữ liệu đi qua TCP có thể đọc và sao chép. Điều kiện CHSH, QBER và ngân sách
khóa chỉ minh họa quyết định của mô hình. [Quy trình demo mạng](NETWORK_DEMO.md#6-giao-thức-và-lưu-trữ)

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
3. Chọn tỷ lệ theo tiêu chí đặt trước tại [đề cương, mục 8.6](de_cuong_QKD_3_tuan.md#86-hướng-cải-tiến-và-tiêu-chí-đánh-giá), ghi `selection.json` và đóng băng hash trước bộ đánh giá. Không có ứng viên đạt đủ thì giữ B0=25%.
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

Giữ manifest cùng dữ liệu. Khi tạo study hoặc chạy `experiments`, thư mục đầu ra phải chưa tồn tại. Riêng `--postprocess` nhận study đã hoàn tất và từ chối ghi đè tệp hậu xử lý cũ; `plot_results` ghi lại biểu đồ của bộ được chọn. Thời gian chạy và ID phiên không tái lập. Seed mô phỏng tái lập vật liệu khóa thô/sàng lọc, giám sát, số bit và lựa chọn. Toeplitz dùng seed ngẫu nhiên mới được trao đổi công khai, còn HKDF gắn ngữ cảnh phiên mới: chạy lại riêng seed mô phỏng không tạo cùng khóa cuối; biết vật liệu mô phỏng và transcript công khai vẫn có thể dựng lại khóa của phiên đó. Không gọi tốc độ phần mềm mô phỏng là tốc độ QKD vật lý.

`outputs/` cục bộ chứa dữ liệu/biểu đồ nghiên cứu và, khi dùng demo mạng, cả PSK
`network/auth.key` cùng tệp Bob nhận trong `received/`. Giữ các dữ liệu còn
cần trước khi dọn. Xóa dữ liệu nghiên cứu làm trang **Thí nghiệm** trống đến
khi tạo lại study. Khôi phục bộ mặc định bằng study với `--output outputs/study`
rồi `--postprocess`; cần dependency nghiên cứu để vẽ biểu đồ.

Chạy nhanh không cần thư viện vẽ: `python -m bb84_lab.research.study --quick --no-plots --output outputs/study-smoke-new`. Bỏ `--no-plots` khi đã cài dependency nghiên cứu và muốn tạo hình. Bộ này được đánh dấu `smoke`, không dùng kết luận nghiên cứu. Runner đơn giản `python -m bb84_lab.research.experiments --config configs/smoke.json --output outputs/smoke-new` vẫn có sẵn.

## Kết quả đã đo

`outputs/study/` đã hoàn tất 3.300 phiên độc lập và năm nhóm biểu đồ. Lựa chọn đóng băng là **25%**: chưa tìm được ứng viên cải thiện đạt đủ tiêu chí. Trên bộ hiệu chỉnh, tỷ lệ 10% tăng Y_pre khoảng 14,07% ở nhóm không Eve/nhiễu thấp nhưng giảm phát hiện tối đa 23,33 điểm phần trăm so với B0; tỷ lệ 50% giảm hiệu suất. Đây là kết quả thực nghiệm, không sửa tiêu chí để tạo kết luận cải tiến.

Ví dụ bộ chính, N=4.096, p=0, lấy mẫu 25%, mỗi hàng có 30 phiên:

| f | QBER trung bình | Bất thường | Chưa đủ bằng chứng | Continue |
|---|---:|---:|---:|---:|
| 0 | 0% | 0/30 | 0/30 | 30/30 |
| 0,1 | 2,556% | 0/30 | 4/30 | 26/30 |
| 1 | 24,947% | 30/30 | 0/30 | 0/30 |

Hậu xử lý đã đo 3.300 kết quả trên cùng các phiên: **435 phiên tạo khóa mô hình**, **28 phiên xác nhận thất bại và bị hủy**; các phiên còn lại bị bỏ qua hoặc thiếu ngân sách. Mỗi phiên `ready` đã kiểm tra hai khóa khớp và AEAD khôi phục đúng. Riêng bộ đánh giá không Eve/không nhiễu/B0 có 100/100 phiên `ready`, Y_final trung bình 1.067,76 bit; khoảng Wilson 95% cho tỷ lệ `ready` xấp xỉ [96,30%; 100%]. Không diễn giải tỷ lệ hữu hạn này thành bảo đảm cho phiên tương lai.
