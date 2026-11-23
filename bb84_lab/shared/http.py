"""Loopback HTTP validation, JSON bounds and response headers shared by dashboards."""

from http.server import BaseHTTPRequestHandler
import json
import re
from urllib.parse import unquote, urlsplit

MAX_BODY_BYTES = 262144
MAX_MESSAGE_BYTES = 16384

def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON không được lặp tên trường")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("JSON không chấp nhận NaN hoặc Infinity")


def validate_message(value):
    if type(value) is not str or len(value.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("Thông điệp phải là văn bản UTF-8 không quá 16.384 byte")
    return value


class LoopbackHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "BB84HTTP/1"
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
