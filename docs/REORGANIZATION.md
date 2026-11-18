# Tổ chức lại cấu trúc dự án

## Phạm vi và lựa chọn cấu trúc

Đã đọc 11 module Python nguồn, cấu hình, README, kịch bản demo, đề cương và
các đường dẫn tài nguyên web. Các script/bản chụp trong `outputs/` là kết quả
kiểm chứng lịch sử, không phải mã nguồn đang phát triển; đã dọn sau khi hoàn
tất kiểm chứng theo yêu cầu người dùng.

Package `bb84_lab/` chứa mã ứng dụng và lõi. `bb84_lab/research/` chứa bốn
chương trình nghiên cứu liên quan. `tests/` giữ self-check assert hiện có;
`docs/` giữ tài liệu. Không thêm dependency, build system hoặc framework.
Package đặt tại gốc để chạy `python -m ...` ngay từ checkout, không cần
`src/`, cài editable hay sửa `PYTHONPATH`.

Theo yêu cầu cuối cùng của người dùng, đã xóa 11 file chuyển tiếp tại gốc.
Mỗi module chỉ còn một bản triển khai trong package; kiểm thử nằm trong
`tests/`. Dùng lệnh `python -m ...` và import bằng tên package. `AGENTS.md`
và tài liệu đã được cập nhật để không tạo lại lớp tương thích cũ.

## Cây thư mục đích

```text
E:\Project_MHMM/
├── bb84_lab/
│   ├── __init__.py
│   ├── app.py
│   ├── bb84.py
│   ├── demo.py
│   ├── postprocess.py
│   ├── research_analysis.py
│   ├── secure_channel.py
│   └── research/
│       ├── __init__.py
│       ├── experiments.py
│       ├── plot_results.py
│       ├── study.py
│       └── verify_quantum.py
├── tests/
│   ├── __init__.py
│   └── self_check.py
├── docs/
│   ├── de_cuong_QKD_3_tuan.md
│   ├── DEMO.md
│   └── REORGANIZATION.md
├── configs/                  # Giữ nguyên ba JSON nguồn
├── web/                      # Giữ nguyên HTML/CSS/JavaScript
├── outputs/                  # Giữ kết quả nghiên cứu và ảnh demo
├── .venv/                    # Giữ nguyên môi trường
├── .gitignore
├── AGENTS.md
├── README.md
├── requirements.txt
└── requirements-research.txt
```

## Ánh xạ từng file

| Đường dẫn cũ | Mã nguồn/tài liệu mới |
|---|---|
| `app.py` | `bb84_lab/app.py` |
| `bb84.py` | `bb84_lab/bb84.py` |
| `demo.py` | `bb84_lab/demo.py` |
| `postprocess.py` | `bb84_lab/postprocess.py` |
| `secure_channel.py` | `bb84_lab/secure_channel.py` |
| `research_analysis.py` | `bb84_lab/research_analysis.py` |
| `experiments.py` | `bb84_lab/research/experiments.py` |
| `study.py` | `bb84_lab/research/study.py` |
| `plot_results.py` | `bb84_lab/research/plot_results.py` |
| `verify_quantum.py` | `bb84_lab/research/verify_quantum.py` |
| `self_check.py` | `tests/self_check.py` |
| `DEMO.md` | `docs/DEMO.md` |
| `de_cuong_QKD_3_tuan.md` | `docs/de_cuong_QKD_3_tuan.md` |

File thêm: ba `__init__.py` để khai báo package và tài liệu này.
README và hướng dẫn đường dẫn trong AGENTS được cập nhật tại chỗ.
Các file ngoài bảng giữ vị trí cũ.

## Trách nhiệm và quan hệ import

| Module | Trách nhiệm | Phụ thuộc nội bộ trực tiếp |
|---|---|---|
| `bb84_lab.bb84` | Mô phỏng, lấy mẫu, QBER, Wilson | Không |
| `bb84_lab.secure_channel` | Xác thực, HKDF, AEAD, kiểm chứng mật mã | Không |
| `bb84_lab.postprocess` | Cascade, xác nhận, Toeplitz | `secure_channel` |
| `bb84_lab.demo` | Điều phối phiên và CLI | `bb84`, `postprocess`, `secure_channel` |
| `bb84_lab.app` | HTTP loopback, API và phục vụ web/kết quả | `bb84`, `secure_channel`, `demo` (lazy) |
| `bb84_lab.research_analysis` | Thống kê, chọn tỷ lệ mẫu, bootstrap | `bb84` |
| `bb84_lab.research.experiments` | Runner Monte Carlo từ JSON | `bb84`, `research_analysis` |
| `bb84_lab.research.study` | Hiệu chỉnh, đánh giá, hậu xử lý study | `bb84`, `research_analysis`, `demo` và `plot_results` (lazy) |
| `bb84_lab.research.plot_results` | Vẽ dữ liệu đã đo | `bb84`; Matplotlib lazy |
| `bb84_lab.research.verify_quantum` | Đối chiếu mạch một qubit | Không; Qiskit/Aer lazy |
| `tests.self_check` | Các kiểm chứng assert hiện có và cấu trúc package | Các module trên, không cần thư viện nghiên cứu |

Import nội bộ dùng đường dẫn package; không còn file Python tại gốc.
Không thêm tầng tiện ích hoặc dịch vụ vì chưa có nhu cầu thực tế.

## Quy tắc đường dẫn và lệnh chạy

- HTTP lấy project root từ vị trí `bb84_lab/app.py`, giữ nguyên `web/` và
  mặc định `outputs/study/` kể cả khi chạy từ thư mục làm việc khác.
- Runner lấy cấu hình mặc định từ project root; `--config` tường minh và
  đường dẫn output tương đối vẫn được hiểu theo thư mục làm việc như trước.
- Self-check tạo rồi dọn thư mục riêng dưới `outputs/` ở project root.
- Lệnh ưu tiên: `python -m bb84_lab.app --open`,
  `python -m bb84_lab.demo bb84`, `python -m bb84_lab.research.study ...`,
  `python -m tests.self_check`. Các CLI tại gốc đã được bỏ.
  Chi tiết trong [README](../README.md).

## Kết quả kiểm chứng thực tế

Sau khi bỏ 11 file chuyển tiếp tại gốc:

| Kiểm tra | Kết quả |
|---|---|
| `python -m tests.self_check` | PASS: mô phỏng, hậu xử lý, xác thực, AEAD, HTTP và nghiên cứu tái lập |
| Sáu CLI package với `--help` | PASS: app, demo, experiments, study, plot_results, verify_quantum |
| Ba ca CLI demo | PASS: BB84, AEAD và hủy transcript với mã thoát 2 |
| Cấu trúc | Không có file `*.py` tại gốc; module nguồn nằm trong package |
| Import | Mã sản phẩm và kiểm thử không import module cũ tại gốc |

Không đổi thuật toán hoặc dependency. Self-check vẫn chạy smoke study 165
phiên từ đầu đến hậu xử lý, kiểm tra seed rời nhau và dữ liệu ghép cặp.
Bộ nghiên cứu đầy đủ 3.300 phiên được giữ nguyên, không chạy lại.

Lượt đối chiếu trước đó xác nhận chín kịch bản phiên, dữ liệu nghiên cứu và
năm PNG khớp baseline sau khi chuẩn hóa thời gian/ID phiên. Qiskit/Aer đã
PASS tám trường hợp với 8.192 shots/trường hợp. Các số liệu này thuộc lượt
kiểm chứng tổ chức lại ban đầu; dữ liệu kiểm chứng tạm đã được dọn.

## Dọn file sinh ra sau kiểm chứng

Theo yêu cầu người dùng, đã xóa hai thư mục kiểm chứng tạm
`outputs/refactor-validation-d895eb9e/` và
`outputs/structure-validation-0a05bd47/`, hai bộ chạy thử `outputs/smoke/`
và `outputs/study-smoke/`, ZIP mã cũ `outputs/BB84_Lab.zip` cùng cache
`__pycache__/` ngoài `.venv`. Các snapshot, diff và báo cáo JSON chi tiết
trong thư mục kiểm chứng đã được xóa; bảng phía trên giữ kết quả đã ghi nhận.

Giải phóng 20,99 MiB. Đối chiếu SHA-256 xác nhận 31 file được giữ trong
`outputs/study/`, `outputs/main/`, `outputs/quantum_check.json` và
`outputs/demo-desktop.jpg` không thay đổi. `.venv/` giữ nguyên;
`AGENTS.md` giữ tại gốc, cập nhật vị trí mã nguồn và lệnh chạy package.

Xóa toàn bộ `outputs/` không ảnh hưởng mã nguồn nhưng làm mất bộ nghiên cứu
đã đo, biểu đồ và ảnh demo. Trang Thí nghiệm sẽ trống đến khi tạo lại study.
