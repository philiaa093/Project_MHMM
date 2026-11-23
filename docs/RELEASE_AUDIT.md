# Biên bản dọn dẹp và chuẩn bị phát hành BB84 Lab

Ngày kiểm chứng: **2026-11-23**, múi giờ Asia/Saigon. Môi trường cục bộ: Windows x64, Python 3.14.5.

## 1. Kết luận và phạm vi

Đã hoàn thiện hồ sơ phát hành và kiểm chứng chức năng trên trạng thái tái cấu trúc đang có. Không sửa thuật toán, kiến trúc, frontend, cấu hình nghiên cứu hoặc dependency pins trong lượt dọn dẹp này. Không commit, stage, tag, push, publish hay sửa lịch sử Git. Chưa chọn giấy phép.

**Sẵn sàng để chủ sở hữu review và commit; chưa đủ điều kiện tuyên bố đã phát hành mã nguồn mở.** Cần chốt giấy phép/điều kiện đóng góp, commit đầy đủ phần tái cấu trúc và chạy CI trên GitHub. Các kiểm chứng cục bộ không xác nhận CI hosted hoặc mạng Internet thật.

## 2. Kiểm kê và dọn dẹp

Quét cả gốc, mã nguồn, tài liệu, cấu hình, tài nguyên web và `outputs/`, kể cả file ẩn; môi trường `.venv/` và `.git/` được nhận diện riêng. Kiểm tra trạng thái/index/lịch sử Git; không sửa nội dung môi trường đang dùng hoặc metadata Git. Đối chiếu SHA-256 tìm bản sao nội dung và kiểm tra tham chiếu trước khi xóa.

### Đã xóa trong lượt này

| Thành phần | Số lượng | Lý do và bằng chứng |
|---|---:|---|
| `outputs/structure-qa/reorganize.py` | 1 tệp, 12.897 byte | Docstring xác định công cụ tái cấu trúc dùng một lần; thao tác cơ học đã hoàn tất; không có import/tham chiếu nguồn; không phải entry point hay script kiểm tra trình duyệt |
| `bb84_lab/__pycache__/`, `core/__pycache__/`, `simulation/__pycache__/`, `local/__pycache__/`, `network/__pycache__/`, `research/__pycache__/`, `shared/__pycache__/` và `tests/__pycache__/` | 8 thư mục, 40 tệp `.pyc` | Bytecode sinh tự động, có thể tạo lại; xóa sau kiểm thử, các lượt kiểm chứng sau dùng `PYTHONDONTWRITEBYTECODE=1` |

Tổng hiện vật cũ được xóa: **41 tệp, 366.077 byte**. Danh sách từng tệp/cache được lưu cục bộ ở `outputs/release-qa/cleanup-plan.json`. Các bản sao checkout/môi trường cài đặt và binary validator tạo riêng cho lượt kiểm chứng cũng được dọn sau khi hoàn tất; không tính chúng vào số file cũ nêu trên.

### Đã vắng mặt trước lượt này

Git đã ghi nhận xóa bảy module phẳng `bb84_lab/{app,bb84,demo,education,postprocess,research_analysis,secure_channel}.py` và bốn tài nguyên `web/{app.js,education.js,index.html,styles.css}` ngay từ kiểm kê ban đầu. Đây là thay đổi tái cấu trúc có sẵn, không phải xóa mới của lượt dọn dẹp. Mã thay thế nằm trong package/tài nguyên mới; structural suite, import, CLI và HTTP đã PASS. Không tạo lại compatibility wrapper. Tên cũ chỉ còn trong bảng ánh xạ di chuyển có chủ đích.

### Giữ lại

| Thành phần | Lý do |
|---|---|
| `docs/de_cuong_QKD_3_tuan.md` | Đề cương phạm vi nghiên cứu; giữ nguyên byte, tiếng Việt, đánh số và trích dẫn |
| `outputs/study/` | Bộ 3.300 phiên, lựa chọn đóng băng, CSV/JSON, manifest hậu xử lý và 10 hình PNG/SVG; dữ liệu nghiên cứu đã đo |
| `outputs/main/` | Runner đơn giản 1.800 phiên; dù có thể chạy lại vẫn là bộ đo có provenance và định dạng riêng, không coi là bản sao dư |
| `outputs/quantum_check.json` | Kiểm chứng mạch cũ với manifest phiên bản/seed/shots |
| `outputs/network-qa/`, ảnh và browser driver trong `outputs/structure-qa/` | Người dùng xác nhận giữ bằng chứng QA; giữ cả video gốc/tải về, tệp nhận và log của lần trước |
| `outputs/server.stdout.log`, `outputs/server.stderr.log` | Không xác nhận được vòng đời tiến trình cũ; dung lượng rất nhỏ, giữ để tránh ảnh hưởng log đang dùng |
| `.venv/` | Môi trường làm việc hiện hữu; không xóa/nâng cấp |
| Các `__init__.py` rỗng | Khai báo package có chủ đích, không phải module trùng cần xóa |
| `docs/REORGANIZATION.md` | Đã đủ cây kiến trúc, trách nhiệm, chiều phụ thuộc và ánh xạ; không cần một `ARCHITECTURE.md` trùng |

SHA-256 trước/sau xác nhận **55 tệp output/QA cũ được giữ nguyên byte** (ngoại trừ công cụ di chuyển đã xác minh và xóa). Mã Python, tests, web, configs, requirements và đề cương cũng không thay đổi byte trong lượt chuẩn bị phát hành. Các bộ CSV/manifest và hình gốc không bị ghi đè.

Ba nhóm bản sao nội dung phát hiện đều là bằng chứng truyền tệp: MP4 gốc/tải/nhận, PNG nghiên cứu/tệp nhận, và văn bản nhận lặp. Giữ theo lựa chọn của người dùng. Không phát hiện bản sao module nghiệp vụ hoặc frontend cần xóa; tài liệu đề cương, demo, UI, nghiên cứu và di chuyển phục vụ các mục đích khác nhau.

## 3. Tài liệu và cấu hình

| Tệp | Thay đổi |
|---|---|
| `README.md` | Viết lại bằng tiếng Anh: nguyên lý BB84, tính năng thực tế, ba chế độ, cài đặt, ví dụ, mạng, nghiên cứu, Mermaid, kiểm thử, giới hạn và license status |
| `README.vi.md` | Tạo bản tiếng Việt tương ứng, liên kết hai chiều |
| `docs/RESEARCH.md` | Giữ mô hình, công thức, quy trình và số đo từ README cũ; làm rõ dữ liệu chỉ cục bộ, seed/transcript/khóa, output mới so với hậu xử lý và dependency plotting |
| `docs/DEMO.md` | Bỏ đường dẫn máy cá nhân; chỉ rõ clone mới không kèm study |
| `docs/REORGANIZATION.md` | Xác định đây là tài liệu kiến trúc hiện tại, thêm liên kết README/audit; giữ ánh xạ cũ |
| `CONTRIBUTING.md` | Thiết lập môi trường, bằng chứng, PR, riêng tư, phạm vi; điều kiện đóng góp cần chủ sở hữu xác nhận |
| `CHANGELOG.md` | Ghi `Unreleased`, không đặt phiên bản hoặc suy diễn lịch sử phát hành |
| `AGENTS.md` | Bổ sung quy tắc giữ dữ liệu, release và README song ngữ; sửa phát biểu cũ rằng checkout không có lịch sử Git |
| `.gitignore` | Bổ sung môi trường/cache/build, secret, log và file editor/OS; tiếp tục ignore toàn `outputs/`, không tự bỏ theo dõi file |
| `.gitattributes`, `.editorconfig` | UTF-8, LF cho nguồn/tài liệu, bốn space Python, hai space frontend/YAML/JSON, nhận diện binary |
| `.github/workflows/checks.yml` | Push/PR/manual; Python 3.14, Ubuntu/Windows, dependency check, self-check, CLI, smoke study và whitespace; token chỉ `contents: read` |

Không tạo `pyproject.toml`: dự án chạy bằng package từ checkout, chưa phát hành wheel hay cần metadata/tooling. Không tạo `.env.example`: mã hiện không đọc biến môi trường cấu hình. Không thêm LICENSE vì chưa có lựa chọn của chủ sở hữu. Giữ nguyên `requirements.txt` và `requirements-research.txt`.

Reader testing độc lập phát hiện và đã sửa năm điểm mơ hồ: phạm vi cùng tiến trình, tái lập vật liệu khóa so với khóa phiên, thư mục tạo mới so với `--postprocess`, dependency của smoke plot, và liên kết tiêu chí đề cương §8.6.

## 4. Kết quả kiểm chứng thực tế

| Kiểm tra | Kết quả quan sát |
|---|---|
| `python -m pip check` trong môi trường hiện có | PASS |
| `python -m tests.self_check` | PASS toàn bộ structure/core/simulation/research/local HTTP/network và kiểm tra AEAD |
| Bản nguồn sạch + môi trường ảo mới | Cài từ registry đúng `cryptography==50.0.2`, `cffi==2.1.1`, `pycparser==3.12`; `pip check`, self-check và CLI BB84 PASS; không cài Matplotlib/Qiskit/Aer |
| `python -m bb84_lab.simulation bb84` | `continue`, hậu xử lý `ready`, AEAD roundtrip/tamper/replay PASS |
| `--eve 1`, `--noise 0.1` | `anomalous`, bỏ hậu xử lý đúng |
| `--eve 0.1` với seed mặc định | `continue` nhưng `insufficient_key`; không mã hóa, không suy diễn Eve yếu chắc chắn bị phát hiện |
| `--signals 16`, `--monitor-only` | Lần lượt `inconclusive`/skipped và chỉ giám sát đúng |
| `--tamper-transcript`, AEAD riêng | Mã thoát 2 khi xác thực sai; AEAD độc lập PASS |
| Bảy module CLI và bốn subcommand mạng `--help` | PASS |
| `python -m bb84_lab.local --open --port 0` trong bản sạch | PASS khởi động/cờ mở trình duyệt, HTTP health; `/api/study` trả `available: false` khi không có dữ liệu |
| Chrome Dashboard mô phỏng | PASS tài nguyên CSS/JS, phiên tích hợp, bài học, sửa/giải mã/phát lại, không lỗi JavaScript hoặc tài nguyên lỗi |
| Chrome Dashboard mạng + ba CLI riêng | PASS văn bản UTF-8 có chuỗi giống HTML, PNG hiển thị, MP4 phát và tải xuống khớp byte |
| Eve qua trình duyệt | PASS intercept/tamper/replay/drop/tamper-public; không tạo tệp hoàn tất sau thất bại |
| Giao diện 320/390/768/1440 px | PASS không tràn ngang ở cả hai dashboard và ba vai trò |
| Network suite | PASS socket TCP thật: nhiều khối, rỗng/UTF-8, trực tiếp/proxy, PSK sai, thiếu mẫu/ngân sách, frame sai, upload/download/Range, dọn `.part` |
| Smoke study mới | PASS 165 phiên độc lập, giữ B0=25%, không dùng kết luận khoa học |
| Hậu xử lý smoke | PASS 165 kết quả, 20 phiên `ready`, không thêm phiên độc lập |
| Experiment runner mặc định | PASS 36 phiên độc lập, 108 phương án |
| Qiskit/Aer | PASS 8 trường hợp × 8.192 shots; seed 1701, QBER Eve toàn phần chính xác 1/4 trong sai số số thực |
| `plot_results` trên smoke mới | PASS 5 nhóm PNG/SVG; không chạm hình nghiên cứu cũ |
| `node --check` ba tệp JS | PASS |
| Workflow | YAML parse PASS; `actionlint 1.7.12` PASS không chẩn đoán |
| `git diff --check` | PASS |

Cấu hình action đối chiếu với tài liệu chính thức [checkout](https://github.com/actions/checkout) và [setup-python](https://github.com/actions/setup-python); cả hai dùng v7. Validator [actionlint](https://github.com/rhysd/actionlint) chỉ tải vào QA để kiểm tra, không thêm vào dependency/toolchain dự án.

Hai bước ensurepip/Playwright ban đầu bị sandbox Windows từ chối quyền thư mục tạm/pipe. Chạy lại với quyền thực thi phù hợp đã PASS; đây không phải lỗi mã hoặc kiểm tra bị bỏ qua. Không có từ chối auto-review còn tồn tại.

Các driver, ảnh QA, JSON kiểm chứng/cleanup/hash và dữ liệu smoke mới lưu trong `outputs/release-qa/` (Git ignore). Không có PSK QA lưu lại sau kiểm thử. Bản sao checkout/venv và executable validator chỉ là vật liệu kiểm tra tạm và được xóa sau khi ghi kết quả.

## 5. Rà soát công khai

- `git status` xác nhận nhiều thay đổi chưa commit từ lần tái cấu trúc trước; giữ nguyên và không stage/commit tự động. Các package/web/test mới vẫn untracked cho tới khi chủ sở hữu stage chúng.
- `git ls-files -ci --exclude-standard` rỗng: không có file bị ignore vẫn đang được Git theo dõi.
- Quét nguồn/tài liệu/hiện vật cũ tìm private key, mẫu GitHub/OpenAI token, AWS ID và literal credential dài: không phát hiện. Tên file credential hiện hữu không có trong hiện vật cũ/candidate.
- Quét **105 blob** thuộc lịch sử Git khả dụng bằng mẫu private key/GitHub/OpenAI/AWS: không phát hiện. Đây là kiểm tra theo mẫu, không phải chứng nhận không có mọi dạng bí mật hoặc nội dung riêng tư; vẫn review diff/dataset trước công bố.
- README không chứa đường dẫn tuyệt đối của máy cá nhân. Nội dung demo/received ở `outputs/` vẫn local, không được đưa vào candidate.
- Kiểm tra link Markdown nội bộ và hàng rào code; bản source sạch có đủ web/config và chạy được khi không có output nghiên cứu.
- Bản kiểm tra sạch được xuất từ danh sách file nguồn hiện tại có xét `.gitignore`, gồm cả file chưa commit; không sao chép `.venv`, `outputs` hoặc metadata Git. Đây là kiểm chứng candidate, **không phải clone từ commit cuối đã phát hành**. Clone mới từ commit sau khi chủ sở hữu commit vẫn cần kiểm tra.

## 6. Lỗi còn lại và giới hạn kiểm chứng

Không phát hiện lỗi chức năng mới trong các phép thử đã chạy. Chưa chạy CI hosted trên GitHub, chưa chứng nhận môi trường Linux/macOS cục bộ, chưa kiểm thử hai mạng Internet/VM thật và chưa chạy lại đầy đủ 3.300 phiên. Full dataset cũ được giữ nguyên và hash đối chiếu; smoke mới không thay thế full research.

Giới hạn đã biết vẫn giữ: mô phỏng cổ điển, entropy/Wilson không phải chứng minh QKD; Cascade có thể thất bại; trạng thái lượng tử mạng có thể sao chép; PSK cấp ngoài; truyền một chiều, không resume hoặc live video. Mất biên nhận sau khi Bob lưu có thể khiến Alice báo lỗi dù Bob đã nhận đủ.

## 7. Việc cần làm trước commit và push

1. Chủ sở hữu chốt giấy phép/điều kiện đóng góp và bổ sung LICENSE tương ứng khi đã quyết định.
2. Sao lưu riêng các bộ nghiên cứu cùng manifest; quyết định riêng nếu muốn công bố dataset đã tuyển chọn, không force-add `outputs/`.
3. Review `git status --short`, `git diff`, các file mới và bảng ánh xạ di chuyển; đặc biệt bảo đảm package/tests/web mới được stage đầy đủ cùng các xóa cũ.
4. Sau review, stage các thay đổi dự định; kiểm tra `git diff --cached --stat`, `git diff --cached --check` và nội dung staged để tránh secret hoặc thiếu tài nguyên.
5. Chạy lại `python -m pip check` và `python -m tests.self_check` nếu chỉnh mã hoặc dependency; commit bằng subject ngắn, ví dụ `chore: prepare BB84 Lab for publication`.
6. Clone commit đó vào thư mục mới, tạo `.venv`, cài `requirements.txt`, chạy self-check/CLI/Dashboard; không dựa vào output/môi trường máy hiện tại.
7. Chỉ push khi được chủ sở hữu quyết định; theo dõi workflow Checks trên Windows/Ubuntu. Chỉ đánh dấu CI đạt sau khi có run hosted thành công. Không force-push hoặc rewrite history.

## 8. Cây repository nguồn cuối cùng

Cây gồm file nguồn hiện có và file mới cần commit, không phải chỉ danh sách đang tracked. `.git/`, `.venv/`, cache và output bị ignore được trình bày riêng phía dưới.

```text
Project_MHMM/
├── .github/
│   └── workflows/
│       └── checks.yml
├── bb84_lab/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bb84.py
│   │   ├── postprocess.py
│   │   └── secure_channel.py
│   ├── local/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   └── server.py
│   ├── network/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── config.py
│   │   ├── packets.py
│   │   ├── proxy.py
│   │   ├── service.py
│   │   ├── session.py
│   │   ├── transfer.py
│   │   ├── transport.py
│   │   └── ui.py
│   ├── research/
│   │   ├── __init__.py
│   │   ├── analysis.py
│   │   ├── experiments.py
│   │   ├── plot_results.py
│   │   ├── study.py
│   │   └── verify_quantum.py
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── http.py
│   │   └── paths.py
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── education.py
│   │   └── session.py
│   └── __init__.py
├── configs/
│   ├── main.json
│   ├── smoke.json
│   └── study.json
├── docs/
│   ├── de_cuong_QKD_3_tuan.md
│   ├── DEMO.md
│   ├── NETWORK_DEMO.md
│   ├── RELEASE_AUDIT.md
│   ├── REORGANIZATION.md
│   ├── RESEARCH.md
│   └── UI_DESIGN.md
├── tests/
│   ├── __init__.py
│   ├── check_core.py
│   ├── check_local_http.py
│   ├── check_network.py
│   ├── check_research.py
│   ├── check_simulation.py
│   ├── check_structure.py
│   ├── self_check.py
│   └── support.py
├── web/
│   ├── network/
│   │   ├── app.js
│   │   ├── index.html
│   │   └── styles.css
│   ├── shared/
│   │   └── styles.css
│   └── simulation/
│       ├── app.js
│       ├── education.js
│       └── index.html
├── .editorconfig
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── README.md
├── README.vi.md
├── requirements-research.txt
└── requirements.txt
```

Các thư mục local không thuộc bản phát hành:

```text
.venv/                         # Môi trường làm việc hiện hữu
outputs/
├── main/                      # Giữ bộ đo runner đơn giản
├── study/                     # Giữ bộ nghiên cứu đầy đủ và figures/
├── quantum_check.json         # Giữ kiểm chứng mạch cũ
├── network-qa/                # Giữ bằng chứng QA cũ
├── structure-qa/              # Giữ ảnh/driver QA; bỏ công cụ tái cấu trúc
├── release-qa/                # Bằng chứng kiểm chứng của lượt này
├── server.stdout.log          # Giữ log cũ
└── server.stderr.log          # Giữ log cũ
```
