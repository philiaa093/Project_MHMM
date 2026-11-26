"""Eve's independent, explicitly routed proxy for this educational protocol."""

import base64
import random
import select
import socket

from bb84_lab.network.config import E91_PAIR_FRAME, E91_REPLACED_STATE
from bb84_lab.network.transport import configure_socket, receive_frame, send_frame


ATTACK_MODES = {"pass", "intercept", "tamper", "replay", "drop", "tamper-public"}
MONITOR_FIELDS = {"sample_count", "sample_errors", "qber", "ci_low", "ci_high", "status", "reason",
                  "qber_status", "qber_reason"}
BELL_FIELDS = {"s", "abs_s", "ci_low", "ci_high", "status"}


def relay(alice, target, mode="pass", fraction=1.0, seed=2026, event=lambda *a, **k: None):
    if mode not in ATTACK_MODES or type(fraction) not in (int, float) or not 0 <= fraction <= 1:
        raise ValueError("Chế độ Eve không hợp lệ")
    rng = random.Random(seed)
    attacked = False
    configure_socket(alice)
    with socket.create_connection(target, timeout=15) as bob:
        configure_socket(bob)
        event("connected", "Alice đã kết nối qua Eve tới Bob", mode=mode, fraction=fraction, seed=seed)
        while True:
            readable, _, _ = select.select([alice, bob], [], [], 90)
            if not readable:
                raise TimeoutError("Proxy hết thời gian chờ")
            for source in readable:
                try:
                    frame = receive_frame(source)
                except ConnectionError:
                    return
                destination = bob if source is alice else alice
                if source is alice and frame.get("kind") == "quantum" and mode == "intercept":
                    states = frame.get("states")
                    if type(states) is not list or any(type(s) is not int or not 0 <= s <= 3 for s in states):
                        raise ValueError("Sai tín hiệu mô phỏng")
                    intercepted = 0
                    changed = []
                    for state in states:
                        if rng.random() < fraction:
                            basis = rng.getrandbits(1)
                            bit = state % 2 if state // 2 == basis else rng.getrandbits(1)
                            state = 2 * basis + bit
                            intercepted += 1
                        changed.append(state)
                    frame = {**frame, "states": changed}
                    event("attack", "Đã chặn–đo–gửi lại tín hiệu mô phỏng", intercepted=intercepted,
                          signals=len(states), mode=mode, seed=seed)
                if source is alice and frame.get("kind") == E91_PAIR_FRAME and mode == "intercept":
                    states = frame.get("states")
                    if type(states) is not list or any(type(state) is not int or not 0 <= state < E91_REPLACED_STATE
                                                      for state in states):
                        raise ValueError("Sai cặp E91 mô phỏng")
                    changed = [E91_REPLACED_STATE if rng.random() < fraction else state for state in states]
                    frame = {**frame, "states": changed}
                    event("attack", "Đã thay một phần cặp E91 bằng kết quả độc lập ở Bob",
                          intercepted=changed.count(E91_REPLACED_STATE), signals=len(states), mode=mode)
                if (source is alice and mode == "tamper-public" and not attacked
                        and frame.get("kind") == "public"):
                    frame["payload"] = {**frame.get("payload", {}), "modified_by_proxy": True}
                    attacked = True
                    event("attack", "Đã sửa thông điệp công khai; giữ nguyên HMAC", mode=mode)
                # Sequence 0 confirms the key; 1 is metadata; 2 starts file data/end.
                if (source is alice and frame.get("kind") == "data"
                        and type(frame.get("sequence")) is int and frame["sequence"] >= 2 and not attacked):
                    if mode == "drop":
                        event("attack", "Đã ngắt kết nối giữa lúc truyền", mode=mode)
                        return
                    if mode == "tamper":
                        data = base64.b64decode(frame["ciphertext"], validate=True)
                        frame["ciphertext"] = base64.b64encode(bytes([data[0] ^ 1]) + data[1:]).decode("ascii")
                        attacked = True
                        event("attack", "Đã đảo một bit trong bản mã", mode=mode)
                    elif mode == "replay":
                        send_frame(destination, frame)
                        attacked = True
                        event("attack", "Đã gửi lặp một gói mã hóa", mode=mode)
                if source is bob and frame.get("kind") == "public":
                    payload = frame.get("payload", {})
                    if payload.get("kind") in ("decision", "e91-decision"):
                        decision = payload["decision"]
                        summary = {field: decision[field] for field in MONITOR_FIELDS if field in decision}
                        if payload["kind"] == "e91-decision":
                            bell = decision["bell"]
                            summary["bell"] = {field: bell[field] for field in BELL_FIELDS if field in bell}
                        event("qber", "Quan sát thống kê công khai từ Bob (Eve không có PSK)", **summary)
                        if decision.get("status") != "continue":
                            event("aborted", "Bob dừng phiên theo kết quả giám sát công khai", **summary)
                    elif payload.get("kind") == "receipt":
                        event("complete", "Đã chuyển tiếp biên nhận của Bob", bytes=payload.get("size"))
                send_frame(destination, frame)
