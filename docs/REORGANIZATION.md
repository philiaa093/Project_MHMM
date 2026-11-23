# Cấu trúc và ranh giới mã nguồn

Tài liệu này là tài liệu kiến trúc hiện tại và ánh xạ di chuyển; không cần
thêm một bản `ARCHITECTURE.md` trùng nội dung. Hướng dẫn cài đặt:
[English](../README.md) · [Tiếng Việt](../README.vi.md).
Hồ sơ kiểm chứng trước công bố: [RELEASE_AUDIT.md](RELEASE_AUDIT.md).

## Cây thư mục

```text
Project_MHMM/
├── bb84_lab/
│   ├── __init__.py
│   ├── core/                       # Thuật toán và mật mã dùng chung
│   │   ├── bb84.py
│   │   ├── postprocess.py
│   │   └── secure_channel.py
│   ├── simulation/                 # Phiên mô phỏng trong một tiến trình
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── session.py
│   │   └── education.py
│   ├── local/                      # Dashboard mô phỏng trên loopback
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   └── server.py
│   ├── network/                    # Alice, Bob và Eve độc lập
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── config.py
│   │   ├── session.py
│   │   ├── packets.py
│   │   ├── transfer.py
│   │   ├── transport.py
│   │   ├── proxy.py
│   │   ├── service.py
│   │   └── ui.py
│   ├── research/                   # Phân tích và runner nghiên cứu
│   │   ├── analysis.py
│   │   ├── experiments.py
│   │   ├── study.py
│   │   ├── plot_results.py
│   │   └── verify_quantum.py
│   └── shared/                     # Hạ tầng chung cho các giao diện
│       ├── http.py
│       └── paths.py
├── web/
│   ├── simulation/                 # index.html, app.js, education.js
│   ├── network/                    # index.html, app.js, styles.css
│   └── shared/                     # styles.css dùng chung
├── tests/
│   ├── self_check.py               # Điểm chạy toàn bộ kiểm tra
│   ├── support.py                  # Hàm assert dùng chung
│   ├── check_structure.py
│   ├── check_core.py
│   ├── check_simulation.py
│   ├── check_research.py
│   ├── check_local_http.py
│   └── check_network.py
├── configs/                        # JSON cấu hình nguồn
├── docs/                           # Đề cương và hướng dẫn
├── outputs/                        # Dữ liệu, hình, PSK và tệp nhận sinh ra
├── AGENTS.md
├── README.md
├── requirements.txt
└── requirements-research.txt
```

Mỗi package Python có `__init__.py`; cây trên lược các tệp khai báo con.
Gốc `bb84_lab/` chỉ giữ `__init__.py`, không đặt module nghiệp vụ hoặc file
chuyển tiếp. Không có mã Python tại gốc repository. Package đặt trực tiếp
trong checkout để chạy `python -m`, không cần thêm build system hoặc cài editable.

## Trách nhiệm

| Nhóm | Nội dung và giới hạn |
|---|---|
| `core/` | Mô phỏng BB84/QBER, Cascade, Toeplitz, HMAC và AEAD; không biết HTTP, TCP hay dashboard |
| `simulation/` | Điều phối phiên trong một tiến trình, nhật ký kiểm chứng và bài học; CLI tách khỏi xử lý phiên |
| `local/` | API mô phỏng, bài học, gói thử và kết quả nghiên cứu; không quản lý tiến trình Alice/Bob/Eve |
| `network/config.py` | Tham số và giới hạn dung lượng của demo mạng |
| `network/session.py` | Challenge phiên, cơ sở, mẫu QBER, Cascade qua parity và xác nhận khóa |
| `network/packets.py` | Chuyển đổi packet AEAD thành frame; không triển khai lại primitive mật mã |
| `network/transfer.py` | Metadata, khối tệp, SHA-256, dọn `.part`, công nhận tệp và biên nhận |
| `network/transport.py` | Frame TCP có giới hạn và thảo luận công khai đã xác thực |
| `network/proxy.py` | Chuyển tiếp và các chế độ can thiệp Eve |
| `network/service.py` | Một phiên mỗi vai trò, quản lý thread và trạng thái dashboard |
| `network/ui.py` | Dashboard mạng local, upload/download và HTTP Range |
| `network/cli.py` | Tham số dòng lệnh, tạo PSK và khởi động dịch vụ |
| `research/` | Thống kê, bootstrap, lựa chọn tỷ lệ mẫu, runner và kiểm chứng Qiskit; dependency nghiên cứu nạp khi cần |
| `shared/http.py` | Base handler loopback, Host/Origin, JSON có giới hạn và header phản hồi |
| `shared/paths.py` | Vị trí project, web, configs và outputs độc lập thư mục làm việc |
| `web/` | Giao diện chia theo chế độ; stylesheet chung giữ nguyên thứ tự áp dụng |
| `tests/` | Các nhóm assert theo chức năng, không dùng framework mới |

## Chiều phụ thuộc

- `core` chỉ phụ thuộc thư viện và các module khác trong `core`.
- `simulation` dùng `core`; không import dashboard hoặc mạng.
- `local` dùng `core`, `simulation` và `shared`.
- `network` dùng `core` và `shared`; không import `local`, `simulation` hoặc `research`.
- `research` dùng `core`, `simulation` và các đường dẫn tài nguyên dùng chung.
- `shared` không phụ thuộc bất kỳ nhóm nghiệp vụ nào.

Hai dashboard kế thừa `shared.http.LoopbackHandler` độc lập. Dashboard mạng
không còn kế thừa/import handler của dashboard mô phỏng. `check_structure.py`
đọc AST để kiểm tra các ranh giới này và từ chối module Python bị đặt lại vào
gốc `bb84_lab/`.

## Ánh xạ từ cấu trúc phẳng trước đây

| Vị trí trước đây | Vị trí hiện tại |
|---|---|
| `bb84_lab/bb84.py` | `bb84_lab/core/bb84.py` |
| `bb84_lab/postprocess.py` | `bb84_lab/core/postprocess.py` |
| `bb84_lab/secure_channel.py` | `bb84_lab/core/secure_channel.py` |
| `bb84_lab/demo.py` | `simulation/session.py` và `simulation/cli.py` trong `bb84_lab/` |
| `bb84_lab/education.py` | `bb84_lab/simulation/education.py` |
| `bb84_lab/app.py` | `local/server.py`, `local/cli.py`, `shared/http.py` trong `bb84_lab/` |
| `bb84_lab/network.py` | `bb84_lab/network/cli.py` |
| `bb84_lab/network_protocol.py` | `network/config.py`, `session.py`, `packets.py`, `transfer.py` trong `bb84_lab/` |
| `bb84_lab/network_transport.py` | `bb84_lab/network/transport.py` |
| `bb84_lab/network_proxy.py` | `bb84_lab/network/proxy.py` |
| `bb84_lab/network_service.py` | `bb84_lab/network/service.py` |
| `bb84_lab/network_ui.py` | `bb84_lab/network/ui.py` |
| `bb84_lab/research_analysis.py` | `bb84_lab/research/analysis.py` |
| `web/index.html`, `app.js`, `education.js` | `web/simulation/` |
| `web/network.html`, `network.js`, `network.css` | `web/network/index.html`, `app.js`, `styles.css` |
| `web/styles.css` | `web/shared/styles.css` |
| `tests/self_check.py` | Runner gọn và các tệp `tests/check_*.py` |

Các runner nghiên cứu vẫn ở `bb84_lab/research/`. Không tạo file tương thích
ở vị trí cũ. Nội dung đề cương, cấu hình nghiên cứu và bộ kết quả đã đo giữ nguyên.

## Lệnh chạy hiện tại

```powershell
# Dashboard mô phỏng
.\.venv\Scripts\python.exe -m bb84_lab.local --open

# CLI mô phỏng và AEAD
.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84
.\.venv\Scripts\python.exe -m bb84_lab.simulation aead --message "Xin chào"

# Các vai trò mạng (các lệnh init/alice/bob/eve giữ cú pháp đã hướng dẫn)
.\.venv\Scripts\python.exe -m bb84_lab.network --help

# Runner và kiểm tra tổng
.\.venv\Scripts\python.exe -m bb84_lab.research.study --quick --no-plots --output outputs/study-new
.\.venv\Scripts\python.exe -m tests.self_check
```

Lệnh dashboard trước đây `python -m bb84_lab.app` được thay bằng
`python -m bb84_lab.local`; CLI `python -m bb84_lab.demo` được thay bằng
`python -m bb84_lab.simulation`. Lệnh mạng `python -m bb84_lab.network`
và các lệnh nghiên cứu không đổi.

Tham số tường minh như `--config`, `--output`, `--inbox` và `--psk-file`
vẫn được hiểu tương đối với thư mục làm việc. Tài nguyên web và cấu hình
mặc định được xác định qua `shared/paths.py`.

Kiểm tra tổng tiếp tục bao gồm smoke study, truyền tệp thật qua socket,
các chế độ can thiệp, xác thực/replay/nonce và tài nguyên HTTP. Chạy không có
`-O` để assert được thực thi. Hướng dẫn chạy hai laptop khác mạng:
[NETWORK_DEMO.md](NETWORK_DEMO.md).

## Kiểm chứng sau khi tách package

| Kiểm tra | Kết quả |
|---|---|
| `python -m tests.self_check` | PASS: các nhóm assert và ranh giới phụ thuộc |
| Bảy điểm chạy CLI với `--help` | PASS: local, simulation, network và bốn runner nghiên cứu |
| CLI BB84, AEAD, transcript sai | PASS: khôi phục và mã thoát hủy phiên 2 |
| Chrome dashboard local | PASS: tài nguyên CSS/JS, phiên, bài học, sửa/giải mã/phát lại |
| Chrome ba tiến trình mạng | PASS: văn bản UTF-8, PNG, MP4, tải tệp và các chế độ Eve |
| Các cỡ màn hình | PASS: không tràn ngang ở 320, 390, 768 và 1440 px |
| Dependency và whitespace | `pip check`, kiểm tra cú pháp JavaScript và `git diff --check` đạt |

Kiểm tra mạng chạy trên loopback. Lượt này không kiểm chứng thêm kết nối
Internet giữa các thiết bị vật lý hoặc chạy lại toàn bộ nghiên cứu 3.300 phiên.
