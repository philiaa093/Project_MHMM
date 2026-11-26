"""Loopback-only dashboards; TCP peer ports never expose these controls."""

from http.server import ThreadingHTTPServer
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, unquote

from bb84_lab.network.config import CHUNK_BYTES
from bb84_lab.network.setup import PSK_BYTES, SetupConflict
from bb84_lab.shared.http import LoopbackHandler, validate_message
from bb84_lab.shared.paths import OUTPUT_ROOT, WEB_ROOT


MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp", ".mp4": "video/mp4",
               ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg"}
KEY_TRACE_ROUTE = re.compile(r"/api/key-trace/([0-9a-f]{64})/(bb84|e91|cascade|toeplitz)/([0-9]{1,8})")
STATIC_FILES = {
    "/app.js": ("network/app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("network/styles.css", "text/css; charset=utf-8"),
    "/shared/styles.css": ("shared/styles.css", "text/css; charset=utf-8"),
    "/setup.js": ("network/setup.js", "text/javascript; charset=utf-8"),
    "/setup.css": ("network/setup.css", "text/css; charset=utf-8"),
    "/key-lesson": ("network/key-lesson.html", "text/html; charset=utf-8"),
    "/key-lesson.js": ("network/key-lesson.js", "text/javascript; charset=utf-8"),
    "/key-lesson.css": ("network/key-lesson.css", "text/css; charset=utf-8"),
}


class NetworkHandler(LoopbackHandler):
    server_version = "BB84NetworkUI/1"

    @property
    def _node(self):
        launcher = self.server.launcher
        return launcher.node if launcher is not None else self.server.node

    def _headers(self, status, length, content_type, extra=None):
        self.send_response(status)
        headers = {
            "Content-Type": content_type, "Content-Length": str(length),
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "Connection": "close",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'",
        }
        self.close_connection = True
        for key, value in {**headers, **(extra or {})}.items():
            self.send_header(key, value)
        self.end_headers()

    def _send(self, status, body, content_type="application/json; charset=utf-8", filename=None):
        self._headers(status, len(body), content_type)
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self._local_request():
            return
        try:
            path = self._path()
            launcher = self.server.launcher
            if path in STATIC_FILES:
                name, content_type = STATIC_FILES[path]
                self._send(200, (WEB_ROOT / name).read_bytes(), content_type)
            elif path == "/" or (path == "/setup" and launcher is not None):
                page = "setup.html" if path == "/setup" or self._node is None else "index.html"
                self._send(200, (WEB_ROOT / "network" / page).read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/setup" and launcher is not None:
                self._json(200, launcher.snapshot())
            elif path == "/api/state":
                node = self._node
                if node is None:
                    self._error(409, "Hãy chọn và khởi động Alice hoặc Bob")
                    return
                self._json(200, {**node.snapshot(), "setup_available": launcher is not None,
                                 "eve_available": launcher is not None and launcher.eve is not None})
            elif path in ("/eve", "/api/eve/state"):
                eve = launcher.eve if launcher is not None else None
                if eve is None:
                    self._error(404, "Chưa bật Eve trên máy Alice")
                elif path == "/eve":
                    self._send(200, (WEB_ROOT / "network" / "index.html").read_bytes(), "text/html; charset=utf-8")
                else:
                    self._json(200, {**eve.snapshot(), "setup_available": True})
            elif (trace := KEY_TRACE_ROUTE.fullmatch(path)) is not None:
                session_id, stage, offset = trace.groups()
                self._key_trace_page(session_id, stage, int(offset))
            elif re.fullmatch(r"/api/download/[0-9a-f]{32}", path):
                self._download(path.rsplit("/", 1)[1])
            else:
                self._error(404, "Không tìm thấy tài nguyên")
        except (ValueError, TypeError, UnicodeError):
            self._error(400, "Yêu cầu không hợp lệ")
        except OSError:
            self._error(404, "Tệp không còn tồn tại")

    def _key_trace_page(self, session_id, stage, offset):
        node = self._node
        if node is None or node.role == "eve" or stage not in (node.protocol, "cascade", "toeplitz"):
            self._error(404, "Log chi tiết chỉ có trên Alice và Bob")
            return
        page = node.trace_page(session_id, stage, offset)
        if page is None:
            self._error(409, "Phiên đã thay đổi. Hãy mở log của phiên hiện tại.", "stale_session")
            return
        self._json(200, page)

    def _download(self, transfer_id):
        node = self._node
        item = node.download(transfer_id) if node is not None else None
        if item is None:
            self._error(404, "Không tìm thấy tệp đã nhận")
            return
        path = Path(item["path"])
        # Keep filesystem errors before response headers; a missing file is 404.
        with path.open("rb") as handle:
            size = path.stat().st_size
            start, end, status = 0, size - 1, 200
            range_value = self.headers.get("Range")
            if range_value:
                match = re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", range_value)
                if match and size and (match[1] or match[2]):
                    if match[1]:
                        start = int(match[1])
                        end = min(size - 1, int(match[2])) if match[2] else size - 1
                    else:
                        start = max(0, size - int(match[2]))
                    status = 206
                if not match or not size or start > end or start >= size or not (match[1] or match[2]):
                    self._headers(416, 0, "application/octet-stream", {"Content-Range": f"bytes */{size}"})
                    return
            media_type = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
            disposition = "attachment" if media_type == "application/octet-stream" else "inline"
            extra = {"Accept-Ranges": "bytes",
                     "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(item['name'], safe='')}"}
            if status == 206:
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"
            length = max(0, end - start + 1)
            self._headers(status, length, media_type, extra)
            handle.seek(start)
            try:
                while length:
                    chunk = handle.read(min(CHUNK_BYTES, length))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    length -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _setup_post(self, path):
        launcher = self.server.launcher
        if launcher is None or path not in ("/api/setup/psk", "/api/setup/psk-import", "/api/setup/start"):
            self._error(404, "Không tìm thấy thao tác cấu hình")
            return
        origins = self.headers.get_all("Origin", [])
        if origins and origins != [f"http://{self.headers['Host']}"]:
            self._error(403, "Nguồn yêu cầu cấu hình không hợp lệ", "forbidden_origin")
            return
        if path == "/api/setup/psk-import":
            if (self.headers.get_all("Content-Type", []) != ["application/octet-stream"]
                    or self.headers.get_all("Content-Length", []) != [str(PSK_BYTES)]
                    or self.headers.get("Transfer-Encoding") is not None):
                raise ValueError("Chọn tệp PSK gốc có đúng 32 byte")
            launcher.write_psk(self.rfile.read(PSK_BYTES))
        else:
            payload = self._read_json()
            if path == "/api/setup/psk":
                if payload:
                    raise ValueError("Yêu cầu tạo PSK không có tham số")
                launcher.write_psk()
            else:
                if set(payload).difference({"eve", "protocol"}) != {"role", "host", "port"}:
                    raise ValueError("Cần vai trò, địa chỉ IPv4 và cổng TCP")
                launcher.start(payload["role"], payload["host"], payload["port"],
                               eve=payload.get("eve", False), protocol=payload.get("protocol", "bb84"))
        self._json(200, launcher.snapshot())

    def do_POST(self):
        if not self._local_request():
            return
        temporary = None
        try:
            path = self._path()
            if path.startswith("/api/setup/"):
                self._setup_post(path)
                return
            node = self._node
            if path == "/api/eve/attack":
                launcher = self.server.launcher
                node = launcher.eve if launcher is not None else None
                if node is None:
                    self._error(404, "Chưa bật Eve trên máy Alice")
                    return
            if node is None:
                self._error(409, "Hãy chọn và khởi động Alice hoặc Bob")
                return
            if path in ("/api/attack", "/api/eve/attack"):
                payload = self._read_json()
                if set(payload) != {"mode", "fraction"}:
                    raise ValueError("Sai trường cấu hình Eve")
                node.set_attack(payload["mode"], payload["fraction"])
                self._json(200, {"ok": True})
                return
            if path not in ("/api/send-text", "/api/upload") or node.role != "alice":
                self._error(404, "Chỉ Alice có thể gửi dữ liệu")
                return
            if node.busy.locked():
                self._error(409, "Đang có phiên gửi; chờ phiên này kết thúc")
                return
            staging = OUTPUT_ROOT / "network-staging"
            staging.mkdir(parents=True, exist_ok=True)
            if path == "/api/send-text":
                payload = self._read_json()
                if set(payload) != {"message"}:
                    raise ValueError("Chỉ chấp nhận trường message")
                data = validate_message(payload["message"]).encode("utf-8")
                name, kind = "thong-diep.txt", "text"
                with tempfile.NamedTemporaryFile(prefix="bb84-send-", dir=staging, delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(data)
            else:
                lengths = self.headers.get_all("Content-Length", [])
                names = self.headers.get_all("X-Filename", [])
                if (self.headers.get("Transfer-Encoding") is not None or len(lengths) != 1
                        or not re.fullmatch(r"[0-9]+", lengths[0]) or len(names) != 1
                        or self.headers.get("Content-Type") != "application/octet-stream"):
                    raise ValueError("Upload cần Content-Length, X-Filename và application/octet-stream")
                remaining = int(lengths[0])
                if remaining > node.max_bytes:
                    self._error(413, "Tệp vượt giới hạn dung lượng")
                    return
                name, kind = unquote(names[0], errors="strict"), "file"
                with tempfile.NamedTemporaryFile(prefix="bb84-send-", dir=staging, delete=False) as handle:
                    temporary = Path(handle.name)
                    while remaining:
                        chunk = self.rfile.read(min(CHUNK_BYTES, remaining))
                        if not chunk:
                            raise ValueError("Upload chưa đầy đủ")
                        handle.write(chunk)
                        remaining -= len(chunk)
            node.send_background(temporary, name, kind, self.server.config)
            temporary = None  # Worker now owns and removes the upload.
            self._json(202, {"accepted": True})
        except SetupConflict as error:
            self._error(409, str(error))
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
            self._error(400, str(error) if type(error) is ValueError else "Yêu cầu không hợp lệ")
        except OSError:
            self._error(500, "Không đọc hoặc ghi được tệp. Kiểm tra quyền lưu trên máy này.")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def make_ui_server(node=None, port=8770, config=None, launcher=None):
    server = ThreadingHTTPServer(("127.0.0.1", port), NetworkHandler)
    server.daemon_threads = True
    server.node = node
    server.launcher = launcher
    server.config = config
    return server
