"use strict";

(() => {
  const q = (selector) => document.querySelector(selector);
  const put = (selector, value) => { q(selector).textContent = value; };
  const steps = [
    ["Chọn bit và cơ sở", "Alice chọn bit 0/1 và cơ sở Z/X cho từng tín hiệu."],
    ["Chuẩn bị trạng thái", "Cơ sở Z dùng |0⟩, |1⟩; cơ sở X dùng |+⟩, |−⟩. X đổi bit, H đổi cơ sở."],
    ["Eve can thiệp", "Eve đo ở cơ sở đã chọn rồi chuẩn bị lại trạng thái để gửi. Sai cơ sở có thể làm thay đổi kết quả."],
    ["Bob đo", "Bob chọn cơ sở độc lập. Chọn một cột để xem mạch và xác suất của tín hiệu đó."],
    ["Sàng lọc", "Alice và Bob công khai cơ sở. Vị trí khác cơ sở bị loại, kể cả khi tình cờ đo ra cùng bit."],
    ["Công khai mẫu", "Lấy 25% các vị trí đã sàng lọc, làm tròn xuống. Các bit mẫu phải được bỏ khỏi vật liệu khóa."],
    ["Tính QBER", "QBER = số sai khác trong mẫu / số bit mẫu. 16 tín hiệu không đủ ít nhất 100 mẫu nên không được phát hành khóa."],
  ];
  let lesson = null;
  let step = 0;
  let selected = 0;
  let lessonVersion = 0;
  let packet = null;
  let packetReceived = false;
  let packetBusy = false;
  let packetVersion = 0;
  let packetCreatedVersion = 0;
  let packetContext = "";

  const basis = (value) => value === 0 ? "Z" : "X";
  const hex = (value) => value.match(/.{1,2}/g)?.join(" ") || "(Rỗng: thông điệp không có byte dữ liệu)";
  function node(tag, className, value) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (value !== undefined) el.textContent = value;
    return el;
  }

  function renderLesson() {
    if (!lesson) return;
    const active = document.activeElement;
    const focusSelector = active?.dataset.lessonStep !== undefined ? `[data-lesson-step="${active.dataset.lessonStep}"]`
      : active?.dataset.signalIndex !== undefined ? `[data-signal-index="${active.dataset.signalIndex}"]` : null;
    q("#lesson-content").hidden = false;
    put("#lesson-stage-title", `${step + 1}. ${steps[step][0]}`);
    put("#lesson-stage-description", steps[step][1]);
    const nav = q("#lesson-steps");
    nav.replaceChildren();
    steps.forEach(([title], index) => {
      const li = node("li", index < step ? "completed" : "");
      const button = node("button", index === step ? "current" : "", `${index + 1}. ${title}`);
      button.type = "button";
      button.dataset.lessonStep = String(index);
      if (index === step) button.setAttribute("aria-current", "step");
      button.addEventListener("click", () => { step = index; renderLesson(); });
      li.append(button); nav.append(li);
    });
    q("#lesson-previous").disabled = step === 0;
    q("#lesson-next").disabled = step === steps.length - 1;
    q("#lesson-all").disabled = step === steps.length - 1;
    const head = q("#lesson-table-head"), body = q("#lesson-table-body");
    head.replaceChildren(); body.replaceChildren();
    const headings = node("tr");
    const first = node("th", "", "Tín hiệu"); first.scope = "col"; headings.append(first);
    for (const row of lesson.signals) {
      const th = node("th"); th.scope = "col";
      const button = node("button", "signal-select", String(row.index + 1));
      button.type = "button"; button.setAttribute("aria-label", `Xem mạch tín hiệu ${row.index + 1}`);
      button.dataset.signalIndex = String(row.index);
      button.setAttribute("aria-pressed", String(selected === row.index));
      button.addEventListener("click", () => { selected = row.index; renderLesson(); });
      th.append(button); headings.append(th);
    }
    head.append(headings);
    const rows = [
      ["Bit Alice", 0, (r) => r.alice_bit], ["Cơ sở Alice", 0, (r) => basis(r.alice_basis)],
      ["Trạng thái gửi", 1, (r) => r.state],
      ["Cơ sở Eve", 2, (r) => r.intercepted ? basis(r.eve_basis) : "—"],
      ["Eve đo được", 2, (r) => r.intercepted ? r.eve_bit : "—"],
      ["Cơ sở Bob", 3, (r) => basis(r.bob_basis)], ["Bob đo được", 3, (r) => r.bob_bit],
      ["Sau sàng lọc", 4, (r) => r.sifted ? "Giữ" : "Loại"],
      ["Mẫu công khai", 5, (r) => r.sampled ? "Mẫu" : r.sifted ? "Còn" : "—"],
      ["Sai khác trong mẫu", 6, (r) => r.sampled ? r.error ? "Lỗi" : "Khớp" : "—"],
    ];
    for (const [label, minimum, getValue] of rows) {
      const tr = node("tr"); const th = node("th", "", label); th.scope = "row"; tr.append(th);
      for (const row of lesson.signals) {
        let state = "";
        if (step >= 4) state = row.sifted ? "cell-keep" : "cell-drop";
        if (step >= 5 && row.sampled) state = "cell-sample";
        if (step >= 6 && row.sampled && row.error) state = "cell-error";
        const td = node("td", `${state}${selected === row.index ? " selected-signal" : ""}`, step >= minimum ? String(getValue(row)) : "·");
        tr.append(td);
      }
      body.append(tr);
    }
    const s = lesson.summary;
    put("#lesson-sifted", step >= 4 ? `Sàng lọc: ${s.sifted_count}/16 tín hiệu` : "Chưa sàng lọc");
    put("#lesson-samples", step >= 5 ? `Mẫu: ${s.sample_count} · còn ${s.remaining_count} bit` : "Chưa lấy mẫu");
    put("#lesson-qber", step >= 6 ? `QBER: ${s.sample_count ? `${s.sample_errors}/${s.sample_count} = ${formatPercent(s.qber)}` : "không xác định"}` : "Chưa tính QBER");
    put("#lesson-conclusion", step >= 6 ? "Bài học không tạo khóa: chỉ có 16 tín hiệu, không đủ 100 mẫu kiểm tra. Một mẫu nhỏ không có lỗi vẫn chưa chứng minh kênh an toàn. Xem trang Mô phỏng hoặc Thí nghiệm để đánh giá nhiều tín hiệu." : "Các ô có dấu · sẽ được mở khi đến bước tương ứng. Chọn số tín hiệu để theo dõi đúng một trường hợp.");
    q("#lesson-circuit-panel").hidden = step < 3;
    if (step >= 3) renderCircuit();
    if (focusSelector) q(focusSelector)?.focus({ preventScroll: true });
  }

  function sequenceDiagram(host, gates, title) {
    const width = Math.max(700, 60 + gates.length * 88);
    const svg = svgElement("svg", { viewBox: `0 0 ${width} 126`, role: "img", "aria-label": title });
    svg.append(svgElement("line", { x1: 15, x2: width - 15, y1: 65, y2: 65, stroke: "#637caa", "stroke-width": 1.5 }));
    gates.forEach((gate, index) => {
      const x = 24 + index * (width - 48) / gates.length;
      const gateWidth = (width - 48) / gates.length - 13;
      const color = gate.actor === "Eve" ? "#a3313d" : "#3158c8";
      svg.append(svgElement("text", { x: x + gateWidth / 2, y: 24, "text-anchor": "middle", fill: color, "font-size": 13 }, gate.actor));
      svg.append(svgElement("rect", { x, y: 43, width: gateWidth, height: 44, rx: 5, fill: "#fff", stroke: color, "stroke-width": 1.5 }));
      svg.append(svgElement("text", { x: x + gateWidth / 2, y: 71, "text-anchor": "middle", fill: color, "font-size": 17 }, gate.label));
      svg.append(svgElement("text", { x: x + gateWidth / 2, y: 113, "text-anchor": "middle", fill: "#58677e", "font-size": 12 }, gate.note));
    });
    host.replaceChildren(svg);
  }

  function probabilityChart(host, series, description) {
    const svg = svgElement("svg", { viewBox: "0 0 430 168", role: "img", "aria-label": description });
    for (const [index, tick] of [0, .5, 1].entries()) {
      const x = 65 + tick * 280;
      svg.append(svgElement("line", { x1: x, x2: x, y1: 12, y2: 124, stroke: "#dde4ef" }));
      svg.append(svgElement("text", { x, y: 146, "text-anchor": "middle", fill: "#58677e", "font-size": 13 }, `${index * 50}%`));
    }
    [0, 1].forEach((bit) => {
      const y = 25 + bit * 56;
      svg.append(svgElement("text", { x: 9, y: y + 16, fill: "#17263e", "font-size": 15 }, `|${bit}⟩`));
      series.forEach((item, index) => {
        const value = item.values[bit], top = y + index * 18;
        svg.append(svgElement("rect", { x: 65, y: top, width: Math.max(0, value * 280), height: 13, rx: 2, fill: item.color }));
        svg.append(svgElement("text", { x: 354, y: top + 12, fill: item.color, "font-size": 12 }, formatPercent(value)));
      });
    });
    host.replaceChildren(svg);
    const legend = node("p", "probability-legend");
    for (const item of series) legend.append(node("span", "", item.name));
    host.append(legend);
  }

  function renderCircuit() {
    const row = lesson.signals[selected];
    put("#lesson-selected-label", `Tín hiệu ${selected + 1}`);
    const gates = [{ actor: "Alice", label: row.alice_bit ? "X" : "I", note: `bit ${row.alice_bit}` },
      { actor: "Alice", label: row.alice_basis ? "H" : "I", note: `cơ sở ${basis(row.alice_basis)}` }];
    if (row.intercepted) gates.push(
      { actor: "Eve", label: row.eve_basis ? "H" : "I", note: `cơ sở ${basis(row.eve_basis)}` },
      { actor: "Eve", label: "M", note: `đo: ${row.eve_bit}` },
      { actor: "Eve", label: "|0⟩", note: "chuẩn bị lại" },
      { actor: "Eve", label: row.eve_bit ? "X" : "I", note: `bit ${row.eve_bit}` },
      { actor: "Eve", label: row.eve_basis ? "H" : "I", note: "gửi lại" });
    gates.push({ actor: "Bob", label: row.bob_basis ? "H" : "I", note: `cơ sở ${basis(row.bob_basis)}` },
      { actor: "Bob", label: "M", note: `trước nhiễu: ${row.bob_before_noise}` });
    sequenceDiagram(q("#lesson-circuit"), gates, `Chuẩn bị và đo tín hiệu ${selected + 1}; có Eve: ${row.intercepted}`);
    put("#lesson-circuit-explanation", `${row.intercepted ? "Eve đã đo rồi chuẩn bị lại một qubit; đoạn sau |0⟩ là tín hiệu gửi lại, không phải tiếp tục trạng thái trước phép đo. " : "Eve không chặn tín hiệu này. "}I nghĩa là không đặt cổng X/H. Sơ đồ dựng từ dấu vết backend, không phải ảnh một lần chạy trên phần cứng lượng tử.`);
    probabilityChart(q("#lesson-probability-chart"), [{ name: "Xác suất lý thuyết", values: row.bob_probabilities, color: "#3158c8" }], "Xác suất lý thuyết Bob đo 0 hoặc 1 trước lỗi bit nền");
    put("#lesson-observation", `Xác suất theo trạng thái thực sự được gửi đến Bob trong tín hiệu này, trước nhiễu. Lần đo mô phỏng thu ${row.bob_before_noise}; ${row.noise_flipped ? "lỗi bit nền đã lật" : "không có lật bit nền"}, nên Bob nhận ${row.bob_bit}.`);
    const archive = lesson.circuit_check;
    const reference = archive?.cases?.find((item) => item.alice_bit === row.alice_bit && item.alice_basis === row.alice_basis && item.bob_basis === row.bob_basis);
    if (reference && finite(reference.exact_p_one) && finite(reference.aer_p_one)) {
      probabilityChart(q("#lesson-reference-chart"), [
        { name: "Statevector (hàng trên)", values: [1 - reference.exact_p_one, reference.exact_p_one], color: "#3158c8" },
        { name: "Aer (hàng dưới)", values: [1 - reference.aer_p_one, reference.aer_p_one], color: "#14765d" },
      ], "Xác suất lý tưởng và tần suất đo Aer từ kết quả đã lưu");
      put("#lesson-reference-note", `${formatNumber(archive.shots_per_case)} shots/trường hợp từ ${archive.source}. Dữ liệu lưu trước, không chạy Qiskit khi bấm. Tham chiếu này không có Eve hoặc nhiễu; khác điều kiện nếu tín hiệu hiện tại bị can thiệp.`);
    } else {
      put("#lesson-reference-chart", "Chưa có dữ liệu kiểm chứng mạch đã lưu.");
      put("#lesson-reference-note", "Có thể tạo bằng lệnh verify_quantum trong README; phần bài học không cần cài Qiskit.");
    }
  }

  async function createLesson(event) {
    event.preventDefault();
    if (q("#run-lesson").disabled || !q("#lesson-form").reportValidity()) return;
    const version = lessonVersion;
    setBusy(q("#run-lesson"), true); showError("#lesson-error", null);
    try {
      lesson = await request("/api/lesson", { scenario: q("#lesson-scenario").value, seed: Number(q("#lesson-seed").value) });
      if (lesson.kind !== "public-bb84-lesson-v1" || !Array.isArray(lesson.signals) || lesson.signals.length !== 16 || lesson.key_released) throw new Error("Bài học trả dữ liệu không hợp lệ.");
      step = 0; selected = 0; renderLesson();
      put("#lesson-config-note", version === lessonVersion ? `16 tín hiệu công khai · kịch bản ${q("#lesson-scenario option:checked").textContent} · seed ${lesson.seed}` : "Đầu vào đã đổi trong lúc chạy. Bảng thuộc cấu hình lúc bấm tạo; tạo lại để cập nhật.");
    } catch (error) {
      lesson = null; q("#lesson-content").hidden = true; showError("#lesson-error", error);
      put("#lesson-config-note", "Không tạo được bài học. Kiểm tra kết nối máy chủ rồi thử lại.");
    } finally { setBusy(q("#run-lesson"), false); }
  }

  function updatePacketInput() {
    put("#packet-input-meta", `${formatNumber(new TextEncoder().encode(q("#packet-message").value).length)} byte UTF-8`);
  }
  function packetControls(busy) {
    packetBusy = busy;
    q("#create-packet").disabled = busy;
    q("#packet-decrypt").disabled = busy || !packet || packetReceived;
    q("#packet-tamper").disabled = busy || !packet || packetReceived;
    q("#packet-replay").disabled = busy || !packet || !packetReceived;
  }
  function clearPacket(message) {
    packet = null; packetReceived = false;
    packetContext = "";
    q("#packet-context").classList.remove("stale");
    q("#packet-content").hidden = true; q("#packet-empty").hidden = false;
    put("#packet-empty", message);
    put("#packet-recovered", "Bob chưa nhận gói.");
    put("#packet-ciphertext", ""); put("#packet-tag", ""); put("#packet-aad", ""); put("#packet-nonce", ""); put("#packet-digest", "");
    q("#packet-events").replaceChildren();
    packetControls(packetBusy);
  }
  function updatePacketContext() {
    const stale = packetCreatedVersion !== packetVersion;
    put("#packet-context", `${packetContext}. ${packetReceived ? "Bob đã xác thực và giải mã gói gốc." : "Gói chưa được Bob nhận."}${stale ? " Đầu vào đã đổi; các thao tác vẫn áp dụng cho gói đã tạo trước đó." : ""}`);
    q("#packet-context").classList.toggle("stale", stale);
  }
  function packetEvent(message, status) {
    const list = q("#packet-events"); list.prepend(node("li", status, message));
    while (list.children.length > 12) list.lastElementChild.remove();
  }
  function packetFlow(result) {
    const svg = svgElement("svg", { viewBox: "0 0 920 230", role: "img", "aria-label": "Khóa đi từ BB84 qua hậu xử lý và HKDF vào AEAD; thông điệp đi trực tiếp vào AEAD, không đi qua BB84" });
    const box = (x, y, width, title, caption) => {
      svg.append(svgElement("rect", { x, y, width, height: 60, rx: 6, fill: "white", stroke: "#738ec7" }));
      svg.append(svgElement("text", { x: x + width / 2, y: y + 25, "text-anchor": "middle", fill: "#17263e", "font-size": 16 }, title));
      svg.append(svgElement("text", { x: x + width / 2, y: y + 45, "text-anchor": "middle", fill: "#4d6088", "font-size": 12 }, caption));
    };
    const arrow = (points) => {
      svg.append(svgElement("polyline", { points, fill: "none", stroke: "#3158c8", "stroke-width": 1.8 }));
      const coords = points.trim().split(" ").pop().split(",").map(Number);
      svg.append(svgElement("path", { d: `M ${coords[0] - 6} ${coords[1] - 4} L ${coords[0]} ${coords[1]} L ${coords[0] - 6} ${coords[1] + 4}`, fill: "none", stroke: "#3158c8", "stroke-width": 1.8 }));
    };
    box(15, 12, 145, "BB84", `${formatNumber(result.sifted_count)} bit sàng lọc`);
    box(185, 12, 155, "Hậu xử lý", `${formatNumber(result.postprocessing.output_bits)} bit đầu ra`);
    box(365, 12, 135, "HKDF", "Khóa 32 byte");
    arrow("160,42 185,42"); arrow("340,42 365,42"); arrow("500,42 530,42 530,137 555,137");
    box(15, 135, 265, "Thông điệp UTF-8", `${formatNumber(result.packet.plaintext_bytes)} byte; không qua kênh lượng tử`);
    arrow("280,165 555,165");
    box(555, 112, 190, "ChaCha20-Poly1305", "Mã hóa + xác thực");
    arrow("745,142 770,142");
    box(770, 112, 135, "Bản mã + tag", `${formatNumber(result.packet.ciphertext_bytes)} byte`);
    svg.append(svgElement("text", { x: 645, y: 204, "text-anchor": "middle", fill: "#4d6088", "font-size": 13 }, "Nonce 12 byte + AAD là đầu vào AEAD"));
    q("#packet-flow").replaceChildren(svg);
    put("#packet-key-note", "BB84 cấp vật liệu khóa; HKDF ràng buộc khóa với phiên. Văn bản chỉ đi vào ChaCha20-Poly1305 sau khi có khóa. Các khối mô tả vai trò của lời gọi AEAD trong thư viện, không phải các bước mã hóa tự viết.");
  }

  async function createPacket(event) {
    event.preventDefault();
    if (packetBusy || !q("#packet-form").reportValidity()) return;
    const scenario = presets[q("#packet-scenario").value];
    const version = packetVersion;
    const payload = { signals: Number(q("#packet-signals").value), seed: Number(q("#packet-seed").value),
      eve_fraction: scenario.eve, noise_probability: scenario.noise, message: q("#packet-message").value };
    setBusy(q("#create-packet"), true); packetControls(true);
    clearPacket("Đang thiết lập BB84, hậu xử lý và mã hóa…");
    showError("#packet-error", null); put("#packet-context", "Đang tạo một phiên mới…");
    try {
      const result = await request("/api/packet", payload);
      const context = `${formatNumber(result.signals)} tín hiệu · QBER ${formatPercent(result.qber)} · ${statusLabels[result.status] || result.status}`;
      if (!result.packet) {
        const reason = result.postprocessing?.status === "insufficient_key" ? "Hậu xử lý không đủ 256 bit cho ứng dụng." : result.postprocessing?.status === "failed" ? "Xác nhận khóa thất bại." : "Giám sát không cho phép tiếp tục.";
        clearPacket(`${reason} Không tạo bản mã hoặc dữ liệu nhận. Thử kênh sạch với 4.096 tín hiệu.`);
        put("#packet-context", `${context}. ${reason}`);
        return;
      }
      packet = result.packet;
      packetContext = `${context} · khóa đã xác nhận`;
      packetCreatedVersion = version;
      q("#packet-content").hidden = false; q("#packet-empty").hidden = true;
      updatePacketContext();
      put("#packet-plain-size", `${formatNumber(packet.plaintext_bytes)} byte`);
      put("#packet-cipher-size", `${formatNumber(packet.ciphertext_bytes)} byte`);
      put("#packet-tag-size", `${packet.tag_bytes} byte`);
      put("#packet-ciphertext", hex(packet.ciphertext_preview_hex));
      put("#packet-preview-note", packet.preview_truncated ? `Đang xem ${packet.preview_bytes} byte đầu của ${formatNumber(packet.ciphertext_body_bytes)} byte bản mã; tag hiển thị riêng bên dưới.` : "Hiển thị toàn bộ phần bản mã; tag hiển thị riêng bên dưới.");
      put("#packet-tag", hex(packet.tag_hex)); put("#packet-nonce", hex(packet.nonce_hex));
      put("#packet-aad", packet.aad_text.replaceAll("\u0000", "␀")); put("#packet-digest", packet.ciphertext_sha256);
      put("#packet-delivery-badge", "Bob chưa nhận"); q("#packet-delivery-badge").className = "tag neutral";
      put("#packet-action-status", "Gói đã mã hóa thật bằng thư viện. Thử sửa một byte, sau đó gửi gói gốc để so sánh.");
      q("#packet-action-status").className = "packet-action-status";
      packetEvent("Đã mã hóa; chưa giải mã hoặc kiểm tra phát lại.", "");
      packetFlow(result);
    } catch (error) {
      clearPacket("Không tạo được gói. Kiểm tra lỗi và thử lại.");
      put("#packet-context", "Phiên không hoàn tất; không có dữ liệu nhận hợp lệ.");
      showError("#packet-error", error);
    } finally { setBusy(q("#create-packet"), false); packetControls(false); }
  }

  async function actOnPacket(action) {
    if (!packet || packetBusy) return;
    const button = q(`#packet-${action}`);
    setBusy(button, true); packetControls(true); showError("#packet-error", null);
    try {
      const result = await request("/api/packet/action", { token: packet.token, action });
      if (result.status === "accepted" && action === "decrypt" && result.roundtrip_ok && typeof result.plaintext === "string") {
        packetReceived = true;
        updatePacketContext();
        // This text comes only from the authenticated backend decrypt response.
        put("#packet-recovered", result.plaintext || "(Thông điệp rỗng: 0 byte, tag vẫn được xác thực.)");
        put("#packet-delivery-badge", "Đã xác thực và giải mã"); q("#packet-delivery-badge").className = "tag success";
        put("#packet-action-status", `Bob giải mã ${formatNumber(result.plaintext_bytes)} byte; backend đối chiếu khớp bản gốc. Có thể phát lại chính gói này.`);
        q("#packet-action-status").className = "packet-action-status success";
        packetEvent("Gói gốc: xác thực thành công, giải mã và đối chiếu đúng.", "success");
      } else if (result.status === "rejected" && result.reason === "invalid_tag") {
        put("#packet-recovered", "Không trả bản rõ: gói bị sửa không vượt qua xác thực.");
        put("#packet-action-status", `${result.changed_part === "tag" ? "Tag" : "Bản mã"} byte ${result.changed_offset}: ${result.original_byte} → ${result.changed_byte}. Backend từ chối vì InvalidTag. Gói gốc vẫn giữ nguyên; bấm Bob giải mã gói gốc để thử.`);
        q("#packet-action-status").className = "packet-action-status danger";
        packetEvent("Lật 1 bit trong gói: xác thực thất bại, không xuất bản rõ.", "danger");
      } else if (result.status === "rejected" && result.reason === "replay") {
        put("#packet-action-status", "Phát lại bị từ chối bởi kiểm tra số thứ tự. Không giải mã hay trả thêm bản rõ. Nội dung đang thấy là kết quả nhận hợp lệ trước đó.");
        q("#packet-action-status").className = "packet-action-status warning";
        packetEvent("Phát lại đúng gói đã nhận: từ chối theo số thứ tự.", "warning");
      } else throw new Error("Backend trả kết quả kiểm chứng không hợp lệ. Tạo gói mới để thử lại.");
    } catch (error) {
      clearPacket("Không hoàn tất thao tác. Gói có thể đã hết hạn; tạo một gói mới.");
      put("#packet-context", "Thao tác không hoàn tất; tạo một gói mới để tiếp tục.");
      showError("#packet-error", error);
    } finally { setBusy(button, false); packetControls(false); }
  }

  q("#lesson-form").addEventListener("submit", createLesson);
  for (const id of ["lesson-scenario", "lesson-seed"]) q(`#${id}`).addEventListener("input", () => {
    lessonVersion += 1;
    if (lesson) put("#lesson-config-note", "Cấu hình đã đổi. Bảng hiện tại thuộc lần tạo trước; bấm Tạo 16 tín hiệu để cập nhật.");
  });
  q("#lesson-previous").addEventListener("click", () => { if (lesson && step > 0) { step -= 1; renderLesson(); } });
  q("#lesson-next").addEventListener("click", () => { if (lesson && step < steps.length - 1) { step += 1; renderLesson(); } });
  q("#lesson-all").addEventListener("click", () => { if (lesson) { step = steps.length - 1; renderLesson(); } });
  q("#packet-form").addEventListener("submit", createPacket);
  for (const action of ["decrypt", "tamper", "replay"]) q(`#packet-${action}`).addEventListener("click", () => actOnPacket(action));
  q("#packet-form").addEventListener("input", () => {
    packetVersion += 1; updatePacketInput();
    if (packet) updatePacketContext();
  });
  updatePacketInput(); packetControls(false);
})();
