"""Render key-agreement evidence from public messages and local decisions."""

from itertools import islice

from bb84_lab.core.postprocess import CONFIRMATION_BITS, SAFETY_BITS


def begin_trace(event, session_id):
    event("key_trace_begin", "Mở phiên", stage="auth", status="info", session_id=session_id,
          detail="Hai bên đã trao đổi lời chào. Tiếp theo kiểm tra HMAC-SHA256 của thảo luận công khai.")


def trace_step(event, stage, title, detail, status="info"):
    # Build detail from fixed text and aggregate measurements at the call site.
    event("key_trace_step", title, stage=stage, detail=detail, status=status)


def trace_sifting(event, signals, sifted, sampled, retained):
    trace_step(event, "bb84", "Sàng lọc theo cơ sở",
               f"Giữ {sifted} / {signals} tín hiệu cùng cơ sở Z/X. Loại {signals - sifted} tín hiệu khác cơ sở.", "ok")
    trace_step(event, "bb84", "Lấy mẫu và loại mẫu",
               f"Dùng {sampled} bit để kiểm tra lỗi. Vật liệu khóa còn {sifted} − {sampled} = {retained} bit.", "ok")


def trace_qber(event, config, decision):
    qber = decision["qber"]
    if qber is None:
        estimate = "QBER chưa xác định vì có 0 bit mẫu."
    else:
        estimate = (f"QBER = {decision['sample_errors']} / {decision['sample_count']} = {qber:.3%}. "
                    f"Wilson 95% [{decision['ci_low']:.3%}, {decision['ci_high']:.3%}].")
    reasons = {
        "insufficient_samples": f"Dừng vì cần ít nhất {config.min_samples} bit mẫu.",
        "upper_bound_at_or_below_threshold": "Cận trên đạt ngưỡng. Tiếp tục sang Cascade.",
        "lower_bound_above_threshold": "Dừng vì cận dưới vượt ngưỡng.",
        "interval_crosses_threshold": "Dừng vì khoảng Wilson cắt ngưỡng.",
    }
    trace_step(event, "bb84", "Tính QBER và quyết định",
               f"{estimate} Ngưỡng {config.threshold:.3%}. {reasons[decision['reason']]}",
               "ok" if decision["status"] == "continue" else "stopped")


def trace_cascade_queries(event, queries, parity_leak, corrections=None):
    detail = f"{queries} truy vấn × 2 bit parity = {parity_leak} bit công khai."
    if corrections is not None:
        detail += f" Bob lật bit {corrections} lần."
    trace_step(event, "cascade", "Tổng kết đối soát", detail, "ok")


def trace_budget(event, retained, upper, entropy, parity_leak, output, record_details=None):
    enough = output >= 256
    detail = (f"Entropy mô hình ⌊{retained} × (1 − h₂({upper:.3%}))⌋ = {entropy} bit, dùng cận trên Wilson. "
              f"8 × ⌊max(0, {entropy} − {parity_leak} − {CONFIRMATION_BITS} − {SAFETY_BITS}) / 8⌋ = {output} bit. "
              + ("Đủ 256 bit để tiếp tục." if enough else "Dừng vì cần ít nhất 256 bit."))
    status = "ok" if enough else "stopped"
    trace_step(event, "toeplitz", "Tính ngân sách khóa", detail, status)
    if record_details is not None:
        record_details("toeplitz", [("Tính ngân sách khóa", detail, status)])


def trace_amplification(event, retained, output):
    trace_step(event, "toeplitz", "Nhân ma trận Toeplitz trên GF(2)",
               f"Ma trận {output} hàng × {retained} cột. Mỗi hàng XOR các tích để tạo một bit. "
               f"Thu {output} bit, lấy 256 bit đầu và dẫn xuất khóa ứng dụng bằng HKDF-SHA256 gắn với phiên.",
               "ok")


def trace_bb84_details(record_details, alice_bases, bob_bases, sample, sample_seed, alice_sample, bob_sample,
                       config, decision):
    if record_details is None:
        return

    def rows():
        yield ("Cấu hình sàng lọc và lấy mẫu",
               f"N = {len(alice_bases)}, tỷ lệ mẫu α = {config.sample_fraction:.1%}. "
               f"Hoán vị danh sách cùng cơ sở với seed công khai {sample_seed:032x}, rồi lấy ⌊α × số vị trí cùng cơ sở⌋.",
               "info")
        sampled = set(sample)
        bases = ("Z", "X")
        for index, (alice, bob) in enumerate(zip(alice_bases, bob_bases)):
            outcome = "khác cơ sở, loại" if alice != bob else "đưa vào mẫu rồi loại" if index in sampled else "giữ lại"
            yield f"Tín hiệu {index + 1}", f"Alice {bases[alice]}, Bob {bases[bob]} → {outcome}.", "ok"
        errors = 0
        for order, (index, alice, bob) in enumerate(zip(sample, alice_sample, bob_sample), 1):
            delta = alice ^ bob
            errors += delta
            yield (f"Mẫu {order} · tín hiệu {index + 1}",
                   f"Bit công khai của Alice {alice} ⊕ Bob {bob} = {delta}. Lỗi lũy kế {errors}.", "ok")
        if sample:
            yield ("QBER và khoảng Wilson",
                   f"p̂ = {decision['sample_errors']} / {len(sample)} = {decision['qber']:.8f}. "
                   "Wilson 95% dùng z = 1.95996398454, d = 1 + z²/n, "
                   "c = (p̂ + z²/(2n))/d, r = z√(p̂(1−p̂)/n + z²/(4n²))/d. "
                   f"Sau khi chặn về [0, 1], khoảng [c−r, c+r] = [{decision['ci_low']:.8f}, {decision['ci_high']:.8f}].",
                   "ok")
        minimum = config.min_samples
        passed = decision["status"] == "continue"
        yield ("Quyết định QBER",
               f"Mẫu {len(sample)}, tối thiểu {minimum}, ngưỡng {config.threshold:.3%}. "
               + ("Đủ mẫu và cận trên đạt ngưỡng. Chạy Cascade." if passed else "Không đạt điều kiện. Dừng trước Cascade."),
               "ok" if passed else "stopped")

    entries = rows()
    while batch := list(islice(entries, 128)):
        record_details("bb84", batch)


def trace_parity_detail(record_details, query, indices, alice, bob, prefix="", action=""):
    if record_details is None:
        return
    positions = ", ".join(str(index + 1) for index in indices[:24])
    if len(indices) > 24:
        positions += f", … (+{len(indices) - 24})"
    relation = "số sai khác lẻ" if alice != bob else "số sai khác chẵn hoặc bằng 0"
    record_details("cascade", [(f"{prefix}Truy vấn parity {query}",
                               f"{len(indices)} bit, vị trí trong chuỗi giữ lại [{positions}]. "
                               f"Parity Alice {alice} ⊕ Bob {bob} = {alice ^ bob} → {relation}.{action}", "ok")])


def trace_cascade_plan(record_details, retained, qber, seed):
    if record_details is not None:
        record_details("cascade", [("Chia khối và hoán vị",
                                    f"Đầu vào {retained} bit, QBER = {qber:.8f}. "
                                    "Lượt đầu dùng thứ tự gốc, khối tối đa 128 nếu QBER = 0, "
                                    "ngược lại lấy max(1, ⌊0.73/QBER⌋). "
                                    f"Từ lượt sau tăng gấp đôi kích thước khối và hoán vị với seed công khai {seed}. "
                                    "Chỉ số ở mỗi truy vấn bắt đầu từ 1, tính trong chuỗi giữ lại.", "info")])


def toeplitz_row_observer(record_details, seed, retained, output):
    if record_details is None:
        return None
    record_details("toeplitz", [("Dựng ma trận từ seed công khai",
                                 f"m = {output}, n = {retained}, seed hiệu dụng m+n−1 = {len(seed)} bit. "
                                 "Chỉ số i, j bắt đầu từ 0. T[i,j] = seed[n−1+i−j]. "
                                 "Vị trí seed ở các dòng sau cũng bắt đầu từ 0.", "info")])
    for index in range(0, len(seed), 128):
        chunk = seed[index:index + 128]
        record_details("toeplitz", [(f"Seed công khai {index}–{index + len(chunk) - 1}",
                                     "".join(map(str, chunk)), "info")])

    def on_row(row, coefficients):
        width = min(24, retained)
        first = format(coefficients >> (retained - width), f"0{width}b")
        preview = first + ("…" if width < retained else "")
        record_details("toeplitz", [(f"Hàng Toeplitz {row + 1}",
                                     f"T[{row},j] đọc seed từ {retained - 1 + row} giảm tới {row}. "
                                     f"{width} hệ số đầu {preview}. Hàng có {coefficients.bit_count()} hệ số bằng 1. "
                                     "Đã XOR các bit đầu vào ở các cột có hệ số 1 để tính bit đầu ra.", "ok")])

    return on_row
