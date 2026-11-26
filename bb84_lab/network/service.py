"""Thread ownership and bounded public UI state for network demo roles."""

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import socketserver
import threading

from bb84_lab.network.config import DEFAULT_MAX_FILE_BYTES, PROTOCOLS
from bb84_lab.network.transfer import receive_transfer, send_transfer
from bb84_lab.network.proxy import relay
from bb84_lab.network.transport import ProtocolMismatch


TRACE_STAGE_LIMIT = 8192
TRACE_PAGE_SIZE = 100


class NetworkNode:
    def __init__(self, role, psk=None, target=None, inbox="outputs/received", max_bytes=DEFAULT_MAX_FILE_BYTES,
                 mode="pass", fraction=1.0, seed=2026, noise=0, *, protocol="bb84"):
        if protocol not in PROTOCOLS:
            raise ValueError("Chọn giao thức BB84 hoặc E91")
        self.role, self._psk, self.target = role, psk, target
        self.protocol = protocol
        self.inbox, self.max_bytes = Path(inbox), max_bytes
        self.mode, self.fraction, self.seed, self.noise = mode, fraction, seed, noise
        self._lock = threading.Lock()
        self.busy = threading.Lock()
        self._events = deque(maxlen=80)
        self._received = deque(maxlen=100)
        self._downloads = {}
        self._state = "idle"
        self._statistics = {}
        self._progress = {"bytes": 0, "total": 0}
        self._trace_session_id = None
        self._trace_steps = deque(maxlen=32)
        self._trace_details = {stage: [] for stage in (protocol, "cascade", "toeplitz")}
        self._trace_omitted = dict.fromkeys(self._trace_details, 0)
        self._trace_active = False
        self.listen_address = None

    def _append_trace(self, stage, title, detail, status):
        self._trace_steps.append({"time": datetime.now(timezone.utc).isoformat(), "stage": stage,
                                  "title": title, "detail": detail, "status": status})

    def _reset_trace(self, session_id=None):
        self._trace_session_id = session_id
        self._trace_steps.clear()
        for stage, steps in self._trace_details.items():
            steps.clear()
            self._trace_omitted[stage] = 0

    def record_details(self, stage, rows):
        with self._lock:
            steps = self._trace_details[stage]
            room = TRACE_STAGE_LIMIT - len(steps)
            self._trace_omitted[stage] += max(0, len(rows) - room)
            time = datetime.now(timezone.utc).isoformat()
            steps.extend({"time": time, "stage": stage, "title": title, "detail": detail, "status": status}
                         for title, detail, status in rows[:room])

    def trace_page(self, session_id, stage, offset):
        with self._lock:
            if self._trace_session_id != session_id:
                return None
            steps = self._trace_details[stage]
            return {"session_id": session_id, "stage": stage, "offset": offset, "page_size": TRACE_PAGE_SIZE,
                    "recorded": len(steps), "omitted": self._trace_omitted[stage],
                    "steps": [dict(step) for step in steps[offset:offset + TRACE_PAGE_SIZE]]}

    def event(self, code, message, **values):
        with self._lock:
            if code == "key_trace_begin" or code == "key_trace_step":
                if code == "key_trace_begin":
                    self._trace_active = True
                    self._reset_trace(values["session_id"])
                self._append_trace(values["stage"], message, values["detail"], values["status"])
                return
            if code == "progress":
                self._progress = values
                self._state = "transferring"
                return
            if code in ("connecting", "connected"):
                self._statistics = {}
                self._progress = {"bytes": 0, "total": 0}
                self._trace_active = self.role == "alice"
                if self._trace_active:
                    self._reset_trace()
                    self._append_trace("auth", "Kết nối tới đầu nhận", message, "info")
            if self._trace_active and code == "failed":
                self._append_trace(self._trace_steps[-1]["stage"], "Phiên thất bại", message, "error")
            if self._trace_active and code == "complete":
                self._append_trace("transfer", "Truyền dữ liệu hoàn tất", f"{message}. Tổng {values['bytes']} byte.", "ok")
            if code in ("qber", "key", "aborted"):
                self._statistics = {**self._statistics, **values}
            self._state = code
            self._events.append({"time": datetime.now(timezone.utc).isoformat(),
                                 "code": code, "message": message, **values})

    def snapshot(self):
        with self._lock:
            snapshot = {"role": self.role, "protocol": self.protocol, "state": self._state, "busy": self.busy.locked(),
                    "target": list(self.target) if self.target else None,
                    "listen": self.listen_address, "max_file_bytes": self.max_bytes,
                    "mode": self.mode, "fraction": self.fraction, "seed": self.seed,
                    "statistics": dict(self._statistics), "progress": dict(self._progress),
                    "events": list(self._events),
                    "received": [{k: v for k, v in item.items() if k != "path"} for item in self._received]}
            if self.role in ("alice", "bob"):
                snapshot["key_trace"] = {"session_id": self._trace_session_id,
                                         "steps": [dict(step) for step in self._trace_steps],
                                         "details": {stage: {"recorded": len(steps), "omitted": self._trace_omitted[stage]}
                                                     for stage, steps in self._trace_details.items()}}
            return snapshot

    def completed(self, item):
        with self._lock:
            if len(self._received) == self._received.maxlen:
                old = self._received[0]
                self._downloads.pop(old["id"], None)
            self._received.append(item)
            self._downloads[item["id"]] = dict(item)

    def download(self, transfer_id):
        with self._lock:
            item = self._downloads.get(transfer_id)
            return dict(item) if item else None

    def set_attack(self, mode, fraction):
        from bb84_lab.network.proxy import ATTACK_MODES
        if self.role != "eve" or mode not in ATTACK_MODES or type(fraction) not in (int, float) or not 0 <= fraction <= 1:
            raise ValueError("Cấu hình Eve không hợp lệ")
        if not self.busy.acquire(blocking=False):
            raise ValueError("Chờ phiên hiện tại kết thúc rồi đổi chế độ")
        try:
            with self._lock:
                self.mode, self.fraction = mode, fraction
        finally:
            self.busy.release()
        self.event("configured", "Chế độ Eve sẽ áp dụng cho phiên tiếp theo", mode=mode, fraction=fraction)

    def send_background(self, path, name, kind, config):
        if self.role != "alice" or not self.busy.acquire(blocking=False):
            raise ValueError("Alice đang bận hoặc sai vai trò")

        def worker():
            try:
                send_transfer(self.target, self._psk, path, name, kind, config, self.event, self.max_bytes,
                              record_details=self.record_details, protocol=self.protocol)
            except Exception as error:
                self.event("failed", _error_message(error))
            finally:
                Path(path).unlink(missing_ok=True)
                self.busy.release()

        self.event("connecting", "Đang tạo phiên gửi mới")
        threading.Thread(target=worker, daemon=True).start()


def _error_message(error):
    # Do not expose exception reprs containing payloads, paths or key material.
    from bb84_lab.core.secure_channel import AuthenticationError
    if isinstance(error, ProtocolMismatch):
        return "Alice và Bob phải chọn cùng giao thức BB84 hoặc E91. Mở lại Setup trên máy cần đổi."
    if isinstance(error, AuthenticationError):
        return "Xác thực thất bại hoặc gói bị phát lại; đã hủy phiên"
    if isinstance(error, (ConnectionError, OSError, TimeoutError)):
        return "Kết nối bị ngắt hoặc hết thời gian; kiểm tra địa chỉ, VPN và tường lửa"
    return "Dữ liệu/giao thức không hợp lệ; đã hủy phiên"


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False
    request_queue_size = 8

    def process_request(self, request, client_address):
        # Acquire before spawning: a remote peer cannot create unbounded threads.
        if not self.node.busy.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.node.busy.release()
            raise


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        node = self.server.node
        node.event("connected", "Đã nhận kết nối mới")
        try:
            if node.role == "bob":
                receive_transfer(self.request, node._psk, node.inbox, node.event, node.max_bytes,
                                 node.noise, node.completed, record_details=node.record_details, protocol=node.protocol)
            else:
                relay(self.request, node.target, node.mode, node.fraction, node.seed, node.event)
        except Exception as error:
            node.event("failed", _error_message(error))
        finally:
            node.busy.release()


def make_transport_server(node, host="127.0.0.1", port=0):
    if node.role not in ("bob", "eve"):
        raise ValueError("Chỉ Bob hoặc Eve lắng nghe TCP")
    server = _Server((host, port), _Handler)
    server.node = node
    node.listen_address = list(server.server_address)
    return server
