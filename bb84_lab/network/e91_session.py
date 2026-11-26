"""Two-peer E91 simulator and monitoring over the educational TCP transport.

The source encodes conditional singlet measurements as classical descriptors.
These descriptors are readable on the wire and do not supply quantum secrecy.
Only authenticated Bell outcomes and sacrificial key samples enter the trace.
"""

import secrets

from bb84_lab.core.bb84 import monitor
from bb84_lab.core.e91 import ALICE_ANGLES, BELL_BOUND, BELL_PAIRS, BOB_ANGLES, bell_summary, same_outcome_probability
from bb84_lab.core.e91_key import combine_monitoring
from bb84_lab.core.secure_channel import AuthenticationError
from bb84_lab.network.config import E91_PAIR_FRAME, E91_REPLACED_STATE, public_config
from bb84_lab.network.key_trace import trace_step
from bb84_lab.network.session import _bits, _positions, finish_alice_channel, finish_bob_channel, receive_config
from bb84_lab.network.transport import receive_frame, send_frame


BELL_DIRECTIONS = tuple((alice, bob) for alice, bob, _ in BELL_PAIRS)
SINGLET_AGREEMENT = tuple(
    tuple(same_outcome_probability(alice, bob) for bob in BOB_ANGLES) for alice in ALICE_ANGLES
)


def _settings(payload, length):
    values = payload.get("settings")
    if (set(payload) != {"kind", "settings"} or type(values) is not list or len(values) != length
            or any(type(value) is not int or not 0 <= value < 3 for value in values)):
        raise ValueError("Thiết lập góc đo E91 không hợp lệ")
    return values


def _positions_e91(alice_settings, bob_settings, config, sample_seed):
    alice = [ALICE_ANGLES[index] for index in alice_settings]
    bob = [BOB_ANGLES[index] for index in bob_settings]
    bell = [(index, pair) for index, pair in enumerate(zip(alice, bob)) if pair in BELL_DIRECTIONS]
    # The intersection of the two setting sets is exactly the two key directions.
    sifted, sample, retained = _positions(alice, bob, config.sample_fraction, sample_seed)
    return bell, sifted, sample, retained


def _check_session(config, bell_positions, alice_bell, bob_bell, alice_sample, bob_sample):
    counts = {pair: [0, 0, 0, 0] for pair in BELL_DIRECTIONS}
    for (_, angles), alice, bob in zip(bell_positions, alice_bell, bob_bell):
        counts[angles][2 * alice + bob] += 1
    bell = bell_summary(counts)
    qber = monitor(sum(a != b for a, b in zip(alice_sample, bob_sample)), len(alice_sample),
                   config.threshold, config.min_samples)
    return combine_monitoring(qber, bell)


def _record_result(peer, config, decision, sifted, retained, event, record_details):
    bell = decision["bell"]
    count = sum(pair["count"] for pair in bell["pairs"])
    trace_step(event, "e91", "Tách lượt đo E91",
               f"{count} cặp kiểm tra CHSH; {len(sifted)} cặp cùng hướng dùng cho vật liệu khóa; "
               f"{config.signals - count - len(sifted)} cặp bỏ qua. Bob đảo bit của nhóm cùng hướng.", "ok")
    if bell["abs_s"] is None:
        bell_text = "Thiếu mẫu ở ít nhất một tổ hợp góc CHSH."
    else:
        bell_text = (f"S = {bell['s']:.5f}, |S| = {bell['abs_s']:.5f}. "
                     f"Khoảng 95% cho |S| từ {bell['ci_low']:.5f} đến {bell['ci_high']:.5f}. ")
        if bell["status"] == "violation":
            bell_text += f"Cận dưới vượt {BELL_BOUND:g}."
        elif bell["status"] == "at_or_below_bound":
            bell_text += f"Cận trên không vượt {BELL_BOUND:g}. Dừng trước khi tạo khóa."
        else:
            bell_text += f"Khoảng còn cắt mốc {BELL_BOUND:g}. Dừng vì chưa đủ bằng chứng."
    bell_status = "ok" if bell["status"] == "violation" else "stopped"
    trace_step(event, "e91", "Kiểm tra Bell–CHSH", bell_text, bell_status)

    samples = decision["sample_count"]
    if samples:
        qber_text = (f"{decision['sample_errors']} lỗi / {samples} bit mẫu = {decision['qber']:.3%}. "
                     f"Wilson 95% từ {decision['ci_low']:.3%} đến {decision['ci_high']:.3%}. ")
    else:
        qber_text = "Chưa có bit mẫu cùng hướng để tính QBER. "
    qber_text += (f"Ngưỡng {config.threshold:.3%}, tối thiểu {config.min_samples} bit mẫu. "
                  f"Đã loại {samples} bit mẫu, còn {len(retained)} bit.")
    qber_status = "ok" if decision["qber_status"] == "continue" else "stopped"
    trace_step(event, "e91", "Tính QBER mẫu E91", qber_text, qber_status)

    if record_details is not None:
        rows = []
        for pair in bell["pairs"]:
            a, b = pair["alice_angle"], pair["bob_angle"]
            if pair["count"]:
                value = pair["correlation"]
                detail = (f"E = ({pair['pp']} + {pair['mm']} − {pair['pm']} − {pair['mp']}) "
                          f"/ {pair['count']} = {value:.6f}. Hạng trong S = {pair['sign'] * value:.6f}.")
            else:
                detail = "Chưa có lượt đo thuộc tổ hợp này."
            rows.append((f"Tương quan {a}° / {b}°", detail, "ok" if pair["count"] else "info"))
        record_details("e91", [*rows,
                                ("Ghép bốn hạng CHSH", "Dùng dấu +, −, +, + cho bốn hàng. " + bell_text, bell_status),
                                ("Kiểm tra QBER", qber_text, qber_status)])

    stats = {**decision, "protocol": "e91", "sifted_bits": len(sifted), "retained_bits": len(retained),
             "session_id": peer.session_id, "config": public_config(config), "random_source": "OS"}
    event("qber", "Đã đối chiếu CHSH và loại các bit mẫu QBER", **stats)
    return stats


def prepare_e91_alice_channel(peer, config, event, *, record_details=None):
    peer.send({"kind": "e91-config", "config": public_config(config)})
    rng = secrets.SystemRandom()
    settings = [rng.randrange(len(ALICE_ANGLES)) for _ in range(config.signals)]
    bits = [rng.getrandbits(1) for _ in settings]
    # Encode the software source's conditional state for Bob, not a quantum pair.
    send_frame(peer.connection, {"kind": E91_PAIR_FRAME, "states": [2 * a + bit for a, bit in zip(settings, bits)]})
    peer.send({"kind": "e91-settings", "settings": settings})
    bob_settings = _settings(peer.receive("e91-settings"), config.signals)
    trace_step(event, "e91", "Trao đổi thiết lập E91",
               f"Hai máy đã chọn và đối chiếu thiết lập đo của {config.signals} cặp mô phỏng.", "ok")

    sample_seed = secrets.randbits(128)  # Bob already measured before sending his settings.
    bell, sifted, sample, retained = _positions_e91(settings, bob_settings, config, sample_seed)
    alice_bell = [bits[index] for index, _ in bell]
    alice_sample = [bits[index] for index in sample]
    peer.send({"kind": "e91-sample", "bell_bits": alice_bell, "sample_seed": sample_seed, "bits": alice_sample})
    response = peer.receive("e91-decision")
    if set(response) != {"kind", "bell_bits", "bits", "decision"}:
        raise ValueError("Phản hồi kiểm tra E91 không hợp lệ")
    bob_bell = _bits(response["bell_bits"], len(bell))
    bob_sample = _bits(response["bits"], len(sample))
    decision = _check_session(config, bell, alice_bell, bob_bell, alice_sample, bob_sample)
    if response["decision"] != decision:
        raise AuthenticationError("Hai bên tính kết quả E91 khác nhau")
    stats = _record_result(peer, config, decision, sifted, retained, event, record_details)
    if decision["status"] != "continue":
        return None, stats
    return finish_alice_channel(peer, tuple(bits[index] for index in retained), config, stats, event, record_details)


def prepare_e91_bob_channel(peer, event, noise=0, *, record_details=None):
    config = receive_config(peer, "e91-config")
    frame = receive_frame(peer.connection)
    states = frame.get("states")
    if (set(frame) != {"kind", "states"} or frame["kind"] != E91_PAIR_FRAME
            or type(states) is not list or len(states) != config.signals
            or any(type(value) is not int or not 0 <= value <= E91_REPLACED_STATE for value in states)):
        raise ValueError("Mô tả cặp mô phỏng E91 không hợp lệ")
    rng = secrets.SystemRandom()
    settings = [rng.randrange(len(BOB_ANGLES)) for _ in states]
    bits = []
    for state, setting in zip(states, settings):
        if state == E91_REPLACED_STATE:
            bit = rng.getrandbits(1)
        else:
            alice_setting, alice_bit = divmod(state, 2)
            bit = alice_bit ^ int(rng.random() >= SINGLET_AGREEMENT[alice_setting][setting])
        bits.append(bit ^ int(noise > 0 and rng.random() < noise))

    alice_settings = _settings(peer.receive("e91-settings"), config.signals)
    peer.send({"kind": "e91-settings", "settings": settings})
    trace_step(event, "e91", "Trao đổi thiết lập E91",
               f"Bob đã đo {config.signals} cặp mô phỏng với thiết lập chọn độc lập.", "ok")
    payload = peer.receive("e91-sample")
    sample_seed = payload.get("sample_seed")
    if (set(payload) != {"kind", "bell_bits", "sample_seed", "bits"}
            or type(sample_seed) is not int or not 0 <= sample_seed < 2**128):
        raise ValueError("Yêu cầu lấy mẫu E91 không hợp lệ")
    bell, sifted, sample, retained = _positions_e91(alice_settings, settings, config, sample_seed)
    alice_bell = _bits(payload["bell_bits"], len(bell))
    alice_sample = _bits(payload["bits"], len(sample))
    bob_bell = [bits[index] for index, _ in bell]
    bob_sample = [1 ^ bits[index] for index in sample]
    decision = _check_session(config, bell, alice_bell, bob_bell, alice_sample, bob_sample)
    peer.send({"kind": "e91-decision", "decision": decision, "bell_bits": bob_bell, "bits": bob_sample})
    stats = _record_result(peer, config, decision, sifted, retained, event, record_details)
    if decision["status"] != "continue":
        return None, stats
    return finish_bob_channel(peer, tuple(1 ^ bits[index] for index in retained), config, stats, event, record_details)
