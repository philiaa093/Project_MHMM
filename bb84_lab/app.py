"""Giao diện BB84 local: python -m bb84_lab.app --open (chỉ lắng nghe 127.0.0.1)."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote, urlsplit
import webbrowser

from bb84_lab.bb84 import Config
from bb84_lab.secure_channel import AuthenticationError


ROOT = Path(__file__).resolve().parents[1]
MAX_BODY_BYTES = 262144
MAX_MESSAGE_BYTES = 16384
CONFIG_FIELDS = set(Config.__dataclass_fields__)
RESULT_FILES = {
    "main.csv", "calibration.csv", "evaluation.csv", "paired_differences.csv",
    "selection.json", "manifest.json", "summary.json", "main_summary.json",
    "calibration_summary.json", "evaluation_summary.json", "paired_summary.json",
    "threshold_summary.json",
    "postprocessing.csv", "postprocessing_summary.json", "postprocessing_manifest.json",
}
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".csv": "text/csv; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml",
}


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON không được lặp tên trường")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("JSON không chấp nhận NaN hoặc Infinity")


def _message(value):
    if type(value) is not str or len(value.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("Thông điệp phải là văn bản UTF-8 không quá 16.384 byte")
    return value


def _result_path(study_dir, relative):
    if relative not in RESULT_FILES and not re.fullmatch(r"figures/[A-Za-z0-9_-]+\.(png|svg)", relative):
        return None
    candidate = (study_dir / relative).resolve()
    if not candidate.is_relative_to(study_dir.resolve()) or not candidate.is_file():
        return None
    return candidate


class DemoHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "BB84Local/1"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        # No request bodies, messages, transcript material or keys in server logs.
        return

    def _send(self, status, body, content_type="application/json; charset=utf-8", filename=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; "
                         "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
                         "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Connection", "close")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status, value):
        self._send(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))

    def _error(self, status, message, code="invalid_request"):
        self._json(status, {"error": message, "code": code})

    def _local_request(self):
        port = self.server.server_address[1]
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host_values = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        if len(host_values) != 1 or host_values[0] not in hosts:
            self._error(403, "Chỉ chấp nhận địa chỉ local của ứng dụng", "forbidden_host")
            return False
        if origins and (len(origins) != 1 or origins[0] not in {f"http://{host}" for host in hosts}):
            self._error(403, "Nguồn yêu cầu không hợp lệ", "forbidden_origin")
            return False
        return True

    def _path(self):
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc:
            raise ValueError("Đường dẫn không hợp lệ")
        return unquote(parsed.path, errors="strict")

    def _read_json(self):
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") is not None:
            raise ValueError("Không hỗ trợ Transfer-Encoding")
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]+", lengths[0]):
            raise ValueError("Yêu cầu Content-Length hợp lệ")
        length = int(lengths[0])
        if not 1 <= length <= MAX_BODY_BYTES:
            raise ValueError("Kích thước yêu cầu phải từ 1 đến 262.144 byte")
        content_types = self.headers.get_all("Content-Type", [])
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("Yêu cầu Content-Type application/json")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError("Nội dung yêu cầu chưa đầy đủ")
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_object_without_duplicates,
                             parse_constant=_reject_constant)
        if type(payload) is not dict:
            raise ValueError("Nội dung phải là một đối tượng JSON")
        return payload

    def do_GET(self):
        if not self._local_request():
            return
        try:
            path = self._path()
            static = {"/": "index.html", "/index.html": "index.html",
                      "/styles.css": "styles.css", "/app.js": "app.js"}
            if path in static:
                file = ROOT / "web" / static[path]
                if not file.is_file():
                    self._error(404, "Giao diện chưa sẵn sàng", "not_found")
                    return
                self._send(200, file.read_bytes(), CONTENT_TYPES[file.suffix])
            elif path == "/api/health":
                self._json(200, {"ok": True, "application": "BB84 Lab", "scope": "classical simulation"})
            elif path == "/api/study":
                self._study()
            elif path.startswith("/results/"):
                file = _result_path(self.server.study_dir, path[len("/results/"):])
                if file is None:
                    self._error(404, "Không tìm thấy kết quả", "not_found")
                    return
                filename = file.name if file.suffix == ".csv" else None
                self._send(200, file.read_bytes(), CONTENT_TYPES[file.suffix], filename)
            else:
                self._error(404, "Không tìm thấy đường dẫn", "not_found")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            self._error(400, "Đường dẫn hoặc dữ liệu kết quả không hợp lệ")
        except OSError:
            self._error(500, "Không đọc được tài nguyên local", "resource_error")

    def _study(self):
        summary_path = self.server.study_dir / "summary.json"
        if not summary_path.is_file():
            self._json(200, {"available": False})
            return
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if type(summary) is not dict:
            raise ValueError("Invalid study summary")
        manifest = summary.get("manifest")
        if type(manifest) is not dict or manifest.get("state") != "complete":
            self._json(200, {"available": False, "reason": "study_incomplete"})
            return
        result = {"available": True}
        for field in ("manifest", "selection", "main_summary", "evaluation_summary", "paired_summary",
                      "postprocessing_manifest", "postprocessing_summary", "scope"):
            result[field] = summary.get(field)
        result["figures"] = []
        figures = summary.get("figures", [])
        if type(figures) is not list:
            raise ValueError("Invalid study figure list")
        for figure in figures:
            if type(figure) is not dict:
                continue
            relative = figure.get("file")
            if type(relative) is str and _result_path(self.server.study_dir, relative):
                result["figures"].append({"name": str(figure.get("name", relative)),
                                          "url": "/results/" + quote(relative, safe="/")})
        result["downloads"] = [
            {"label": name, "url": "/results/" + name}
            for name in sorted(RESULT_FILES) if _result_path(self.server.study_dir, name)
        ]
        self._json(200, result)

    def do_POST(self):
        if not self._local_request():
            return
        try:
            path = self._path()
            if path not in ("/api/session", "/api/aead"):
                self._error(404, "Không tìm thấy đường dẫn", "not_found")
                return
            payload = self._read_json()
            message = _message(payload.get("message", "Xin chào từ BB84 Lab"))
            if path == "/api/aead":
                if set(payload) - {"message"}:
                    raise ValueError("Thông số demo AEAD không hợp lệ")
                from bb84_lab.demo import aead_demo
                result = aead_demo(message)
            else:
                if set(payload) - CONFIG_FIELDS - {"message", "tamper_transcript"}:
                    raise ValueError("Có thông số phiên không được hỗ trợ")
                tamper = payload.get("tamper_transcript", False)
                if type(tamper) is not bool:
                    raise ValueError("tamper_transcript phải là true hoặc false")
                config = Config(**{key: value for key, value in payload.items() if key in CONFIG_FIELDS})
                if config.signals > 65536 or config.min_samples > 65536 or config.seed > 2**63 - 1:
                    raise ValueError("Giới hạn: signals/min_samples ≤ 65.536; seed ≤ 2^63−1")
                from bb84_lab.demo import integrated_session
                result = integrated_session(config, tamper=tamper, message=message)
            self._json(200, result)
        except AuthenticationError:
            self._error(422, "Xác thực thất bại; phiên đã hủy, không phát hành khóa hoặc bản rõ",
                        "authentication_failed")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            self._error(400, "Thông số hoặc JSON không hợp lệ; kiểm tra kiểu, phạm vi và kích thước dữ liệu")
        except (TimeoutError, OSError):
            self._error(408, "Yêu cầu chưa đầy đủ hoặc quá thời gian", "request_timeout")
        except Exception:
            self._error(500, "Không hoàn thành được phiên mô phỏng", "simulation_error")


def make_server(port=8765, study_dir=ROOT / "outputs" / "study"):
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port phải là số nguyên từ 0 đến 65.535")
    server = ThreadingHTTPServer(("127.0.0.1", port), DemoHandler)
    server.daemon_threads = True
    server.study_dir = Path(study_dir).resolve()
    return server


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--study-dir", type=Path, default=ROOT / "outputs" / "study")
    parser.add_argument("--open", action="store_true", help="Mở trình duyệt mặc định")
    args = parser.parse_args()
    try:
        server = make_server(args.port, args.study_dir)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Không khởi động được giao diện: {error}\n")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"BB84 Lab: {url}\nMô phỏng cổ điển; nhấn Ctrl+C để dừng.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
