"""Simulation dashboard HTTP endpoints and study resources on loopback."""

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import quote

from bb84_lab.core.bb84 import Config
from bb84_lab.core.e91 import simulate_e91
from bb84_lab.core.secure_channel import AuthenticationError
from bb84_lab.local.learning import read_source, source_catalog
from bb84_lab.shared.http import LoopbackHandler, validate_message
from bb84_lab.shared.paths import OUTPUT_ROOT, WEB_ROOT
from bb84_lab.simulation.education import PacketInspector, lesson_session


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


def _result_path(study_dir, relative):
    if relative not in RESULT_FILES and not re.fullmatch(r"figures/[A-Za-z0-9_-]+\.(png|svg)", relative):
        return None
    candidate = (study_dir / relative).resolve()
    if not candidate.is_relative_to(study_dir.resolve()) or not candidate.is_file():
        return None
    return candidate


class DemoHandler(LoopbackHandler):
    server_version = "BB84Local/1"

    def do_GET(self):
        if not self._local_request():
            return
        try:
            path = self._path()
            static = {"/": "simulation/index.html", "/index.html": "simulation/index.html",
                      "/shared/styles.css": "shared/styles.css",
                      "/app.js": "simulation/app.js", "/education.js": "simulation/education.js",
                      "/e91.js": "simulation/e91.js", "/e91.css": "simulation/e91.css",
                      "/learn": "simulation/learn/index.html", "/learn/": "simulation/learn/index.html",
                      "/learn/index.html": "simulation/learn/index.html",
                      "/learn/learn.css": "simulation/learn/learn.css",
                      "/learn/content.js": "simulation/learn/content.js",
                      "/learn/learn.js": "simulation/learn/learn.js"}
            if path in static:
                file = WEB_ROOT / static[path]
                if not file.is_file():
                    self._error(404, "Giao diện chưa sẵn sàng", "not_found")
                    return
                self._send(200, file.read_bytes(), CONTENT_TYPES[file.suffix])
            elif path == "/api/learn/sources":
                self._json(200, {"sources": source_catalog()})
            elif path.startswith("/api/learn/source/"):
                source = read_source(path[len("/api/learn/source/"):])
                if source is None:
                    self._error(404, "Tệp không nằm trong danh sách mã nguồn học tập", "not_found")
                    return
                self._json(200, source)
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
            if path not in ("/api/session", "/api/aead", "/api/lesson", "/api/packet", "/api/packet/action",
                            "/api/e91/simulate"):
                self._error(404, "Không tìm thấy đường dẫn", "not_found")
                return
            payload = self._read_json()
            if path == "/api/e91/simulate":
                if set(payload) != {"signals", "seed", "noise_probability"}:
                    raise ValueError("E91 cần số cặp, seed và xác suất nhiễu")
                self._json(200, simulate_e91(**payload))
                return
            if path == "/api/lesson":
                if set(payload) - {"scenario", "seed"}:
                    raise ValueError("Unsupported lesson fields")
                result = lesson_session(payload.get("scenario", "clean"), payload.get("seed", 2026))
                check_path = OUTPUT_ROOT / "quantum_check.json"
                result["circuit_check"] = None
                if check_path.is_file():
                    try:
                        check = json.loads(check_path.read_text(encoding="utf-8"))
                        if check.get("status") == "passed":
                            result["circuit_check"] = {
                                "shots_per_case": check["shots_per_case"],
                                "cases": check["prepare_measure_cases"],
                                "source": "outputs/quantum_check.json", "archived": True,
                            }
                    except (OSError, ValueError, KeyError, AttributeError):
                        pass
                self._json(200, result)
                return
            if path == "/api/packet/action":
                if set(payload) != {"token", "action"}:
                    raise ValueError("Unsupported packet action fields")
                self._json(200, self.server.packet_inspector.act(payload["token"], payload["action"]))
                return
            message = validate_message(payload.get("message", "Xin chào từ BB84 Lab"))
            if path == "/api/aead":
                if set(payload) - {"message"}:
                    raise ValueError("Thông số demo AEAD không hợp lệ")
                from bb84_lab.simulation.session import aead_demo
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
                if path == "/api/packet":
                    from bb84_lab.simulation.session import prepare_packet_session
                    result, channel = prepare_packet_session(config, tamper=tamper)
                    if channel is not None:
                        result["packet"] = self.server.packet_inspector.create(channel, message)
                else:
                    from bb84_lab.simulation.session import integrated_session
                    result = integrated_session(config, tamper=tamper, message=message)
            self._json(200, result)
        except AuthenticationError:
            self._error(422, "Xác thực thất bại; phiên đã hủy, không phát hành khóa hoặc bản rõ",
                         "authentication_failed")
        except KeyError:
            self._error(404, "Gói đã hết hạn, bị thay thế hoặc máy chủ đã khởi động lại. Tạo gói mới để thử tiếp.",
                        "packet_expired")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            self._error(400, "Thông số hoặc JSON không hợp lệ; kiểm tra kiểu, phạm vi và kích thước dữ liệu")
        except (TimeoutError, OSError):
            self._error(408, "Yêu cầu chưa đầy đủ hoặc quá thời gian", "request_timeout")
        except Exception:
            self._error(500, "Không hoàn thành được phiên mô phỏng", "simulation_error")


def make_server(port=8765, study_dir=OUTPUT_ROOT / "study"):
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port phải là số nguyên từ 0 đến 65.535")
    server = ThreadingHTTPServer(("127.0.0.1", port), DemoHandler)
    server.daemon_threads = True
    server.study_dir = Path(study_dir).resolve()
    server.packet_inspector = PacketInspector()
    return server
