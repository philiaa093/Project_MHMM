# Đối sánh hiệu quả vận hành BB84 và E91

[Mô hình nghiên cứu](RESEARCH.md) · [README tiếng Việt](../README.vi.md)

Bộ đối sánh này bổ sung thí nghiệm trên mã nguồn, không thay đề cương hoặc tên đề tài đã có. Kết quả là phép đo phần mềm mô phỏng cổ điển. Không suy ra an toàn QKD vật lý, finite-key hoặc độc lập thiết bị từ CHSH, Wilson hay ngân sách Toeplitz giáo dục.

## Câu hỏi và cấu hình chốt trước khi chạy

`configs/comparison.json` quy định cấu hình, ngưỡng, tỷ lệ mẫu và số lần lặp. Runner ghi hash cấu hình, hash mã nguồn và trạng thái `running` trước quan sát đầu tiên. Không hiệu chỉnh tham số theo kết quả đối sánh. Mặc định lấy mẫu 25%, tối thiểu 100 mẫu, ngưỡng QBER 5%, 100 phiên cho mỗi giao thức ở mỗi cấu hình.

| Nhóm | Cấu hình mặc định | Đại lượng quan sát |
|---|---|---|
| Hiệu suất tạo khóa | B = 4.096 / 8.192 / 16.384; p = 0 / 1% / 3%; hai cách tính ngân sách | Bit sàng lọc, mẫu, bit giữ lại, đối soát, xác nhận, Toeplitz; tỷ lệ cấp khóa và bit đầu ra trên **mọi** phiên thử |
| Phát hiện can thiệp | B = 8.192; f = 0 / 5% / 10% / 25% / 50% / 100%; p = 0 / 1% | Báo bất thường, chưa đủ bằng chứng, dừng, can thiệp qua giám sát, can thiệp vẫn được cấp khóa |
| Chịu nhiễu | B = 8.192; p = 0 / 1% / 3% / 5% / 8% / 12% / 16%; f = 0; hai cách tính ngân sách | Xác suất qua giám sát và hoàn tất cấp khóa ở cùng QBER kỳ vọng |
| Hiệu năng hệ thống | TCP loopback; hai tiến trình; B = 8.192; tệp 64 KiB / 1 MiB; 20 lần/ô; hai cách tính ngân sách | Thiết lập khóa, hậu xử lý qua TCP, truyền tệp, thông lượng, CPU và RSS |

Ba nhóm mô phỏng có 44 cấu hình × 2 giao thức × 100 lần = **8.800 phiên đo độc lập**. Mỗi phiên E91 còn được đánh giá với biến thể chỉ xét QBER, tạo tổng 13.200 dòng quan sát. Các dòng chẩn đoán này dùng lại cùng phép đo, không làm tăng số phiên độc lập. Nhóm hệ thống có 160 phiên đo cùng bốn lượt làm nóng bị loại khỏi thống kê. Các con số trên mô tả thiết kế mặc định; chỉ dùng kết quả khi manifest thực tế là `complete` và số dòng khớp cấu hình.

## Hai cách tính ngân sách

- `equal_signals`: BB84 mô phỏng B tín hiệu; E91 mô phỏng B cặp. Có tương ứng B và 2B phép đo lượng tử tại hai đầu.
- `equal_measurements`: BB84 mô phỏng B tín hiệu; E91 mô phỏng B/2 cặp. Cùng B phép đo tại hai đầu, nhưng không tính công chuẩn bị trạng thái, tạo/định tuyến cặp, mất mát, thiết bị hay thời gian truyền vật lý.

Thiết lập cơ sở/hướng đo được chọn đều như trong triển khai hiện tại, không tối ưu riêng từng giao thức. Không gọi cùng số tín hiệu là cùng chi phí vật lý. Ngân sách bit công khai **được đo, chưa bị ràng buộc bằng nhau**: số bit kết quả đo công bố, parity/digest và số byte của một mã hóa JSON xác thực được ghi riêng. Thiết lập đo, vị trí mẫu, seed Toeplitz, HMAC và metadata không được nhập nhằng với bit kết quả đo. Byte JSON của bộ mô phỏng không phải số byte TCP của benchmark.

## Mô hình nhiễu và can thiệp

Trong bộ đối sánh, `p` là xác suất lật bit sau phép đo Bob của **cả hai** giao thức. Khi không can thiệp, QBER kỳ vọng bằng p. Điều này khác tham số nhiễu trắng w trong tab E91 cũ: ở nhóm sinh khóa, w tương ứng 2p, không phải p.

BB84 dùng chặn–đo–gửi lại, có `q = p + f/4 - p*f/2`. E91 thay kết quả của một phần cặp bằng kết quả độc lập, có `q = p + f/2 - p*f` và kỳ vọng `|S| = 2√2(1-f)(1-2p)` trong miền p ≤ 1/2 đang khảo sát. Hai mô hình can thiệp **không tương đương**. Cùng f không đủ để kết luận giao thức nào có khả năng chống tấn công tổng quát tốt hơn.

E91 tách riêng bốn tổ hợp góc Bell và hai tổ hợp cùng hướng sinh khóa. Toàn bộ kết quả Bell và mẫu QBER công bố đều bị loại khỏi vật liệu khóa. Bob đảo bit ở nhóm cùng hướng. Quyết định dùng QBER mẫu Wilson 95% và CHSH Hoeffding/chặn hợp như demo mạng; không dùng nhãn f, p hoặc vị trí can thiệp để ra quyết định.

## Định nghĩa trạng thái và mẫu số

- **Báo bất thường**: QBER có cận dưới vượt ngưỡng hoặc CHSH có cận trên không vượt 2. Đây là hợp hai điều kiện, kể cả khi trạng thái tổng bị CHSH ghi đè.
- **Chưa đủ bằng chứng**: thiếu mẫu hoặc khoảng tin cậy chưa đủ để đi tiếp; không tự gán thành đã phát hiện Eve.
- **Báo động nhầm**: báo bất thường khi f = 0 và QBER kỳ vọng không vượt ngưỡng. Khi p > ngưỡng, báo lỗi do nhiễu không được tính là báo động nhầm; số báo bất thường khi không can thiệp vẫn được ghi riêng.
- **Không được gắn cờ**: f > 0 nhưng không báo bất thường, kể cả phiên dừng do chưa đủ bằng chứng.
- **Bỏ sót ở giám sát**: f > 0 nhưng điều kiện giám sát cho đi tiếp. Ghi riêng trường hợp sau đó vẫn cấp khóa; không gộp với phiên đã bị dừng.
- **Cấp khóa thành công**: Cascade và xác nhận đạt, ngân sách cho ít nhất 256 bit, hai đầu ra Toeplitz khớp, AEAD khôi phục đúng và từ chối sửa/phát lại.
- **Y_final**: toàn bộ số bit Toeplitz ở phiên thành công; bằng 0 ở mọi phiên còn lại. Trung bình chính lấy trên mọi phiên thử. Trung bình chỉ trong phiên thành công được ghi riêng.

Cascade và xác nhận không cắt vị trí khỏi chuỗi giữ lại. Rò rỉ parity hai chiều (2 bit/truy vấn), digest/phản hồi (257 bit), biên dự phòng (64 bit) và phần làm tròn được trừ trong **ngân sách** trước Toeplitz. Không vẽ chúng như các bước giảm trực tiếp số bit của chuỗi.

Biến thể `qber_only_ablation` của E91 dùng đúng phép đo, mẫu và chuỗi giữ lại của phiên có CHSH. Nó chỉ bỏ điều kiện quyết định CHSH, vẫn loại bit Bell và vẫn chia sẻ chi phí sinh/kiểm tra dữ liệu. Vì thế nó đo tác động đến tỷ lệ dừng và sản lượng; không chứng minh tiết kiệm toàn bộ chi phí phép đo/CPU khi thiết kế lại E91. Biến thể không được đưa vào demo vận hành.

## Thống kê và hiệu năng

Tỷ lệ dùng khoảng Wilson 95%; sản lượng trung bình dùng percentile bootstrap mô tả với seed/số lần lặp ghi trong cấu hình. BB84 và E91 có seed riêng, không phân tích như mẫu ghép cặp. Chỉ hai phương án E91 trên cùng phép đo mới ghép cặp. Không xem CI suy biến của dữ liệu toàn 0 là bảo đảm cho phiên tương lai; không tuyên bố ý nghĩa thống kê chỉ từ hai CI giao nhau hay không giao nhau. Các phép đo nhiều cấu hình mang tính mô tả, chưa hiệu chỉnh kiểm định nhiều giả thuyết.

Benchmark dùng `send_transfer`/`receive_transfer` thật, ChaCha20-Poly1305, xác nhận biên nhận, kích thước và SHA-256; không thay RNG hệ điều hành bằng seed. Chạy tuần tự, đảo thứ tự giao thức giữa các lần, tách lượt làm nóng. Thời gian thiết lập khóa tính từ trước băm tệp/kết nối đến sự kiện khóa đã xác nhận. Thời gian hậu xử lý qua TCP tính từ sự kiện QBER đến sự kiện khóa, gồm Cascade, xác nhận, Toeplitz và bắt tay khóa ứng dụng. Tốc độ sau cấp khóa tính byte bản rõ trên thời gian đến biên nhận; có thêm tốc độ đầu cuối gồm thiết lập khóa.

CPU là tổng `process_time` của hai tiến trình, biểu diễn theo một lõi (có thể vượt 100%). RSS là tổng bộ nhớ thường trú lấy mẫu 10 ms, có đường nền và độ tăng đỉnh; có thể bỏ qua đỉnh ngắn. Việc lấy mẫu có chi phí, RSS có thể tính trùng trang chia sẻ, và số đo không tương đương đỉnh working set do hệ điều hành ghi nhận. Tiến trình nhận bắt đầu tính CPU trước bind socket; thời gian tường loại thời gian khởi động tiến trình. Đo trên cùng máy vòng lặp không dự báo LAN/WAN hoặc thiết bị lượng tử. Nếu không có `psutil`, dữ liệu tài nguyên là thiếu và được ghi trạng thái rõ ràng.

## Lệnh tái lập

Chạy từ gốc repository với Python của môi trường dự án. Không cần cài dependency mới cho bản không vẽ. Thư mục đầu ra phải chưa tồn tại.

```powershell
# Kiểm tra nhanh; không dùng làm bằng chứng kết luận nghiên cứu
.\.venv\Scripts\python.exe -m bb84_lab.research.comparison --quick --no-plots --output outputs/comparison-smoke-new

# Bộ đầy đủ và hình (Matplotlib đã cài từ requirements-research.txt)
.\.venv\Scripts\python.exe -m bb84_lab.research.comparison --output outputs/comparison-new

# Cũng bộ đầy đủ nhưng không vẽ
.\.venv\Scripts\python.exe -m bb84_lab.research.comparison --no-plots --output outputs/comparison-no-plots-new

# Đo hệ thống trên máy rảnh; psutil tùy chọn cho CPU/RAM, không lưu PSK
.\.venv\Scripts\python.exe -m bb84_lab.network.benchmark --output outputs/system-new
.\.venv\Scripts\python.exe -m bb84_lab.research.plot_comparison outputs/system-new --system

# Vẽ lại trực tiếp từ JSON đã đo (ghi lại hình, giữ CSV/JSON)
.\.venv\Scripts\python.exe -m bb84_lab.research.plot_comparison outputs/comparison-new
.\.venv\Scripts\python.exe -m tests.self_check
```

## Hiện vật

| Tệp | Ý nghĩa |
|---|---|
| `manifest.json`, `config.json` | Cấu hình chốt trước, môi trường, quy ước, hash nguồn và trạng thái |
| `sessions.csv` | Kết quả từng phiên/phương án; chỉ số công khai, không có bit thô/khóa/PSK |
| `summary.json` | Tỷ lệ, CI, bit trung bình trên mọi phiên và trên phiên thành công |
| `chsh_ablation.json` | Đối chiếu hai điều kiện giám sát trên cùng phiên E91 |
| `figures/*.png`, `figures/*.svg` | Biểu đồ tạo từ JSON đã đo, không dùng ảnh minh họa làm dữ liệu |
| Benchmark: `warmups.json`, `received/`, `public-benchmark-*.bin` | Lượt làm nóng tách riêng và dữ liệu mẫu đã truyền; không phải tệp riêng tư |

Giữ bộ cũ và toàn bộ bằng chứng. Dữ liệu trong `outputs/` bị Git bỏ qua nhưng không phải rác; không xóa hoặc force-add cả thư mục. Dashboard study hiện có vẫn đọc định dạng BB84 cũ; bộ đối sánh mới được đọc bằng JSON/CSV và trình vẽ riêng.
