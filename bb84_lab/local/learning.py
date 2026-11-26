"""Read-only, explicitly allowlisted source material for the project learning UI."""

import ast
import hashlib

from bb84_lab.shared.paths import PROJECT_ROOT


# Deliberately exclude outputs, PSKs, uploads, environment files and arbitrary paths.
SOURCE_FILES = (
    ("bb84_lab/core/bb84.py", "core", "BB84, lấy mẫu và quyết định Wilson"),
    ("bb84_lab/core/postprocess.py", "core", "Cascade, ngân sách khóa và Toeplitz"),
    ("bb84_lab/core/secure_channel.py", "core", "HMAC, HKDF, AEAD và chống phát lại"),
    ("bb84_lab/core/e91.py", "core", "Tương quan singlet, CHSH và QBER E91"),
    ("bb84_lab/simulation/session.py", "simulation", "Ghép một phiên BB84 hoàn chỉnh"),
    ("bb84_lab/simulation/education.py", "simulation", "16 tín hiệu công khai và xem gói"),
    ("bb84_lab/simulation/cli.py", "simulation", "Tham số mô phỏng dòng lệnh"),
    ("bb84_lab/local/server.py", "local", "Nhận HTTP, gọi mô phỏng, trả JSON"),
    ("bb84_lab/local/cli.py", "local", "Khởi động dashboard và trang học"),
    ("bb84_lab/shared/http.py", "shared", "Giới hạn HTTP, JSON và loopback"),
    ("bb84_lab/shared/paths.py", "shared", "Đường dẫn tài nguyên của project"),
    ("bb84_lab/network/config.py", "network", "Giới hạn và cấu hình mạng"),
    ("bb84_lab/network/session.py", "network", "Hai đầu Alice/Bob tạo khóa BB84"),
    ("bb84_lab/network/e91_session.py", "network", "Hai đầu Alice/Bob tạo khóa E91"),
    ("bb84_lab/network/transport.py", "network", "TCP frame và PublicPeer"),
    ("bb84_lab/network/packets.py", "network", "Đóng gói bản mã để gửi qua TCP"),
    ("bb84_lab/network/transfer.py", "network", "Gửi khối, xác thực, lưu tệp hoàn tất"),
    ("bb84_lab/network/proxy.py", "network", "Sáu chế độ can thiệp của Eve"),
    ("bb84_lab/network/service.py", "network", "Trạng thái và công việc nền từng vai trò"),
    ("bb84_lab/network/ui.py", "network", "API dashboard của từng vai trò"),
    ("bb84_lab/network/setup.py", "network", "Thiết lập Alice/Bob/Eve và PSK"),
    ("bb84_lab/network/key_trace.py", "network", "Nhật ký công khai của phiên tạo khóa"),
    ("bb84_lab/network/cli.py", "network", "Lệnh init, setup, alice, bob, eve"),
    ("bb84_lab/research/analysis.py", "research", "Tổng hợp, chọn mẫu và bootstrap ghép cặp"),
    ("bb84_lab/research/study.py", "research", "Chạy nghiên cứu có thể tái lập"),
    ("bb84_lab/research/experiments.py", "research", "Thực nghiệm Monte Carlo và CSV"),
    ("bb84_lab/research/plot_results.py", "research", "Năm nhóm hình study, SD và khoảng tin cậy"),
    ("bb84_lab/research/plot_comparison.py", "research", "Hình đối sánh BB84–E91 và hiệu năng"),
    ("bb84_lab/research/verify_quantum.py", "research", "Kiểm chứng mạch bằng Qiskit tùy chọn"),
    ("web/simulation/app.js", "web", "Giao diện mô phỏng gọi API Python"),
    ("web/simulation/education.js", "web", "Trình bày bài học 16 tín hiệu"),
    ("web/simulation/e91.js", "web", "Giao diện so sánh E91"),
    ("tests/self_check.py", "tests", "Runner các nhóm assert"),
    ("tests/check_core.py", "tests", "Kiểm tra thuật toán lõi và mật mã"),
    ("tests/check_local_http.py", "tests", "Kiểm tra HTTP, trang học và API"),
    ("tests/check_network.py", "tests", "Kiểm tra TCP và truyền tệp thật"),
    ("configs/smoke.json", "configs", "Cấu hình thực nghiệm nhỏ"),
    ("configs/study.json", "configs", "Cấu hình nghiên cứu"),
)
SOURCE_CATALOG = {path: {"path": path, "group": group, "description": description}
                  for path, group, description in SOURCE_FILES}


def source_catalog():
    return list(SOURCE_CATALOG.values())


def read_source(relative):
    """Read current source without executing it or accepting filesystem traversal."""
    if relative not in SOURCE_CATALOG:
        return None
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()) or not path.is_file():
        return None
    data = path.read_bytes()
    if len(data) > 512 * 1024:
        return None
    text = data.decode("utf-8-sig")
    symbols = []
    if path.suffix == ".py":
        tree = ast.parse(text)

        def record(node, prefix=""):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return
            name = prefix + node.name
            decorators = getattr(node, "decorator_list", ())
            start = min([node.lineno, *(item.lineno for item in decorators)])
            symbols.append({"name": name, "start": start, "end": node.end_lineno,
                            "kind": "class" if isinstance(node, ast.ClassDef) else "function"})
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    record(child, name + ".")

        for node in tree.body:
            record(node)
    return {**SOURCE_CATALOG[relative], "text": text, "symbols": symbols,
            "line_count": len(text.splitlines()), "sha256": hashlib.sha256(data).hexdigest()}
