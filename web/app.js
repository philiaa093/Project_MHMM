"use strict";

const $ = (selector) => document.querySelector(selector);
const numberFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });
const percentFormat = new Intl.NumberFormat("vi-VN", { style: "percent", maximumFractionDigits: 2 });
const history = [];
let study = null;
let studyLoading = false;
let lastVerification = null;
const statusLabels = { continue: "Đủ điều kiện tiếp tục", anomalous: "Bất thường", inconclusive: "Chưa đủ bằng chứng" };
const statusClasses = { continue: "success", anomalous: "danger", inconclusive: "warning" };
const finite = (value) => typeof value === "number" && Number.isFinite(value);
const formatNumber = (value) => finite(value) ? numberFormat.format(value) : "—";
const formatPercent = (value) => finite(value) ? percentFormat.format(value) : "—";

function text(selector, value) {
  $(selector).textContent = value;
}

async function request(path, payload) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch(path, {
      method: payload === undefined ? "GET" : "POST",
      headers: payload === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: controller.signal,
      cache: "no-store",
    });
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) throw new Error("Máy chủ chưa trả dữ liệu JSON hợp lệ.");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Yêu cầu thất bại (HTTP ${response.status}).`);
    if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error("Dữ liệu trả về không hợp lệ.");
    return result;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Phiên chạy quá thời gian chờ. Kiểm tra máy chủ và thử lại.");
    if (error instanceof TypeError) throw new Error("Không kết nối được máy chủ. Hãy kiểm tra ứng dụng đang chạy trên localhost.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.classList.toggle("loading", busy);
  button.setAttribute("aria-busy", String(busy));
}

function showError(selector, error) {
  const element = $(selector);
  element.textContent = error ? error.message || String(error) : "";
  element.hidden = !error;
}

function setView(view, updateHash = true) {
  if (!["simulation", "experiments", "about"].includes(view)) view = "simulation";
  document.querySelectorAll(".view").forEach((element) => { element.hidden = element.id !== `view-${view}`; });
  document.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  text("#breadcrumb-current", { simulation: "Mô phỏng BB84", experiments: "Kết quả thí nghiệm", about: "Giới thiệu mô hình" }[view]);
  if (updateHash) window.history.replaceState(null, "", `#${view}`);
  if (view === "experiments" && !study) loadStudy();
}

function updateSliders() {
  for (const id of ["eve", "noise"]) {
    const input = $(`#${id}`);
    const ratio = (Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min));
    input.style.background = `linear-gradient(to right, #118a8d ${ratio * 100}%, #e6edef ${ratio * 100}%)`;
    text(`#${id}-value`, formatPercent(Number(input.value)));
  }
  const eve = Number($("#eve").value);
  $("#eve-node").classList.toggle("intercepting", eve > 0);
  text("#eve-channel-label", eve > 0 ? `Chặn ${formatPercent(eve)} tín hiệu` : "Không can thiệp");
  text("#noise-channel-label", `Nhiễu nền ${formatPercent(Number($("#noise").value))}`);
}

const presets = {
  clean: { signals: 4096, eve: 0, noise: 0 },
  eve: { signals: 4096, eve: 1, noise: 0 },
  noise: { signals: 4096, eve: 0, noise: 0.1 },
  weak: { signals: 4096, eve: 0.1, noise: 0 },
  small: { signals: 16, eve: 0, noise: 0 },
};

function choosePreset(name) {
  const preset = presets[name];
  if (!preset) return;
  for (const [field, value] of Object.entries(preset)) $(`#${field}`).value = String(value);
  $("#sample").value = "0.25";
  $("#threshold").value = "0.05";
  $("#min-samples").value = "100";
  $("#tamper-transcript").checked = false;
  document.querySelectorAll("[data-preset]").forEach((button) => button.classList.toggle("active", button.dataset.preset === name));
  updateSliders();
}

function svgElement(name, attributes = {}, content) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (content !== undefined) element.textContent = content;
  return element;
}

function drawQber(result) {
  const host = $("#qber-visual");
  host.replaceChildren();
  if (![result.qber, result.ci_low, result.ci_high, result.threshold].every(finite)) {
    const message = document.createElement("p");
    message.textContent = "Không có mẫu để tính QBER và khoảng tin cậy. Phiên không được đi tiếp.";
    host.append(message);
    return;
  }
  const max = Math.min(1, Math.max(0.1, Math.ceil(Math.max(result.ci_high, result.threshold) * 1.2 * 10) / 10));
  const x = (value) => 14 + Math.min(max, Math.max(0, value)) / max * 536;
  const svg = svgElement("svg", { viewBox: "0 0 564 76", role: "img", "aria-labelledby": "qber-chart-title" });
  svg.append(svgElement("title", { id: "qber-chart-title" }, `QBER ${formatPercent(result.qber)}, khoảng Wilson ${formatPercent(result.ci_low)} đến ${formatPercent(result.ci_high)}, ngưỡng ${formatPercent(result.threshold)}.`));
  svg.append(svgElement("rect", { x: 14, y: 31, width: 536, height: 7, rx: 3.5, fill: "#e9eff1" }));
  svg.append(svgElement("rect", { x: 14, y: 31, width: x(result.threshold) - 14, height: 7, rx: 3.5, fill: "#cee6e0" }));
  const color = { continue: "#168678", anomalous: "#bd5757", inconclusive: "#c28a35" }[result.status] || "#668a99";
  svg.append(svgElement("line", { x1: x(result.ci_low), x2: x(result.ci_high), y1: 34.5, y2: 34.5, stroke: color, "stroke-width": 5, "stroke-linecap": "round" }));
  svg.append(svgElement("line", { x1: x(result.threshold), x2: x(result.threshold), y1: 22, y2: 46, stroke: "#839ba6", "stroke-width": 1, "stroke-dasharray": "3 2" }));
  svg.append(svgElement("circle", { cx: x(result.qber), cy: 34.5, r: 5, fill: color, stroke: "white", "stroke-width": 2 }));
  svg.append(svgElement("text", { x: Math.min(515, Math.max(45, x(result.qber))), y: 14, "text-anchor": "middle", fill: color, "font-size": 10, "font-weight": 600 }, `QBER ${formatPercent(result.qber)}`));
  svg.append(svgElement("text", { x: 14, y: 61, fill: "#95a9b2", "font-size": 9 }, "0%"));
  svg.append(svgElement("text", { x: 550, y: 61, "text-anchor": "end", fill: "#95a9b2", "font-size": 9 }, formatPercent(max)));
  svg.append(svgElement("text", { x: Math.min(485, Math.max(79, x(result.threshold))), y: 75, "text-anchor": "middle", fill: "#7d96a2", "font-size": 9 }, `Ngưỡng ${formatPercent(result.threshold)}`));
  host.append(svg);
}

function metricValue(selector, value, unit = "") {
  const element = $(selector);
  element.replaceChildren(document.createTextNode(value));
  if (unit) {
    const small = document.createElement("small");
    small.textContent = unit;
    element.append(small);
  }
}

function renderVerification(log, emptyMessage = "Chạy một phiên để xem dấu vết tính toán từ backend.") {
  const empty = $("#verification-empty");
  const content = $("#verification-content");
  const button = $("#download-verification");
  const groups = { bb84: $("#verification-bb84"), postprocess: $("#verification-postprocess"), aead: $("#verification-aead") };
  for (const list of Object.values(groups)) list.replaceChildren();
  if (!log || !Array.isArray(log.entries) || typeof log.sha256 !== "string") {
    lastVerification = null;
    empty.textContent = emptyMessage;
    empty.hidden = false;
    content.hidden = true;
    button.disabled = true;
    return;
  }
  const labels = { passed: "ĐÃ CHẠY", stopped: "DỪNG", failed: "LỖI", not_run: "CHƯA GỌI" };
  for (const entry of log.entries) {
    const list = groups[entry.group];
    if (!list) continue;
    const item = document.createElement("li");
    item.className = "verification-entry";
    const head = document.createElement("div");
    head.className = "verification-entry-head";
    const code = document.createElement("span");
    code.className = "verification-code";
    code.textContent = entry.code || "TRACE";
    const title = document.createElement("strong");
    title.textContent = entry.title || "Bước thực thi";
    const status = document.createElement("span");
    status.className = `verification-status ${entry.status || "not_run"}`;
    status.textContent = labels[entry.status] || "TRẠNG THÁI";
    const implementation = document.createElement("code");
    implementation.className = "verification-implementation";
    implementation.textContent = entry.implementation || "—";
    const formula = document.createElement("p");
    formula.className = "verification-formula";
    formula.textContent = entry.formula || "—";
    const result = document.createElement("p");
    result.className = "verification-result";
    result.textContent = entry.result || "—";
    head.append(code, title, status);
    item.append(head, implementation, formula, result);
    list.append(item);
  }
  lastVerification = log;
  text("#verification-sha", log.sha256);
  empty.hidden = true;
  content.hidden = false;
  button.disabled = false;
}

function downloadVerification() {
  if (!lastVerification) return;
  const session = String(lastVerification.session_id || "session").replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 32) || "session";
  const blob = new Blob([JSON.stringify(lastVerification, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `bb84-verification-${session}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function resetSessionAfterError() {
  metricValue("#metric-qber", "—", "%");
  metricValue("#metric-samples", "—");
  metricValue("#metric-retained", "—", "bit");
  metricValue("#metric-output", "—", "bit");
  text("#metric-ci", "Không có quyết định được xác thực");
  text("#metric-errors", "Phiên đã hủy");
  text("#metric-key-status", "Không phát hành khóa");
  const badge = $("#session-state");
  badge.className = "result-badge danger";
  badge.textContent = "Đã hủy phiên";
  text("#transcript-status", "Chưa xác thực thành công");
  $("#transcript-status").classList.remove("verified");
  text("#decision-explanation", "Không có kết quả giám sát hợp lệ cho phiên này. Không tiếp tục hậu xử lý hoặc mã hóa.");
  text("#qber-visual", "Phiên bị từ chối trước khi hiển thị quyết định QBER.");
  for (const [id, value] of [["stage-sifted", "— bit"], ["stage-retained", "— bit"], ["stage-parity", "— bit tiết lộ"], ["stage-confirmation", "Chưa thực hiện"], ["stage-output", "— bit đầu ra"]]) text(`#${id}`, value);
  document.querySelectorAll(".pipeline li").forEach((item) => item.classList.remove("done"));
  text("#integrated-status", "Phiên đã hủy. Không phát hành khóa hoặc bản rõ.");
  text("#integrated-badge", "CHƯA MÃ HÓA");
  $("#integrated-encryption").classList.remove("success");
  $("#session-details").hidden = true;
  text("#runtime-label", "PHIÊN ĐÃ HỦY");
  renderVerification(null, "Phiên bị hủy trước khi backend tạo được nhật ký kiểm chứng hợp lệ.");
}

function renderSession(result) {
  const post = result.postprocessing || {};
  const encrypted = result.encryption;
  const badge = $("#session-state");
  badge.className = `result-badge ${statusClasses[result.status] || "neutral"}`;
  badge.textContent = statusLabels[result.status] || "Trạng thái chưa xác định";
  metricValue("#metric-qber", finite(result.qber) ? numberFormat.format(result.qber * 100) : "—", "%");
  metricValue("#metric-samples", formatNumber(result.sample_count));
  metricValue("#metric-retained", formatNumber(result.remaining_count), "bit");
  metricValue("#metric-output", formatNumber(post.output_bits ?? 0), "bit");
  text("#metric-ci", finite(result.ci_low) && finite(result.ci_high) ? `CI 95%: ${formatPercent(result.ci_low)}–${formatPercent(result.ci_high)}` : "Chưa đủ mẫu để tính khoảng");
  text("#metric-errors", `${formatNumber(result.sample_errors)} sai khác trong mẫu`);
  const postLabels = { ready: "Khóa mô hình đã xác nhận", skipped: "Chưa đi tiếp hậu xử lý", failed: "Hậu xử lý thất bại", insufficient_key: "Không đủ ngân sách khóa" };
  text("#metric-key-status", postLabels[post.status] || "Chưa phát hành khóa");
  text("#transcript-status", result.transcript_authenticated ? "Đã xác thực" : "Chưa xác thực");
  $("#transcript-status").classList.toggle("verified", Boolean(result.transcript_authenticated));
  drawQber(result);
  const explanations = {
    continue: "Cận trên Wilson không vượt ngưỡng vận hành. Phiên được phép vào hậu xử lý; điều này chưa chứng minh không có Eve hoặc an toàn QKD.",
    anomalous: "Cận dưới Wilson vượt ngưỡng: bất thường/nghi can thiệp hoặc nhiễu cao. Hủy phiên; QBER không xác định chắc chắn nguyên nhân.",
    inconclusive: result.sample_count < result.min_samples ? "Mẫu kiểm tra ít hơn mức tối thiểu. Chưa đủ bằng chứng; phiên không được tạo khóa." : "Khoảng Wilson cắt ngưỡng vận hành. Chưa đủ bằng chứng; phiên không được tạo khóa.",
  };
  text("#decision-explanation", explanations[result.status] || result.scope || "");
  text("#stage-sifted", `${formatNumber(result.sifted_count)} bit`);
  text("#stage-retained", `${formatNumber(result.remaining_count)} bit`);
  text("#stage-parity", finite(post.parity_leak_bits) ? `${formatNumber(post.parity_leak_bits)} bit tiết lộ` : "Chưa thực hiện");
  text("#stage-confirmation", post.key_match ? "Hai phía khớp" : finite(post.confirmation_leak_bits) && post.confirmation_leak_bits > 0 ? "Không xác nhận được" : "Chưa thực hiện");
  text("#stage-output", `${formatNumber(post.output_bits ?? 0)} bit đầu ra`);
  document.querySelectorAll(".pipeline li").forEach((item, index) => {
    const completed = index < 2 || (index === 2 && finite(post.parity_leak_bits) && !["skipped", undefined].includes(post.status)) || (index === 3 && post.key_match) || (index === 4 && post.status === "ready");
    item.classList.toggle("done", Boolean(completed));
  });
  $("#integrated-encryption").classList.toggle("success", Boolean(encrypted?.roundtrip_ok));
  text("#integrated-badge", encrypted?.roundtrip_ok ? "ĐÃ KIỂM CHỨNG" : "CHƯA MÃ HÓA");
  if (encrypted?.roundtrip_ok) {
    const checks = [encrypted.tamper_rejected ? "từ chối sửa gói" : "", encrypted.replay_rejected ? "từ chối phát lại" : ""].filter(Boolean);
    text("#integrated-status", `Khôi phục đúng ${formatNumber(encrypted.plaintext_bytes)} byte; ${checks.join("; ")}. ${encrypted.key_source || "Khóa từ mô hình BB84."}`);
  } else {
    const reasons = { insufficient_key: "Ngân sách còn lại không đủ 256 bit cho mã hóa. Không đệm hoặc lặp bit.", failed: "Hậu xử lý thất bại; không mã hóa thông điệp.", skipped: "Phiên không đủ điều kiện để hậu xử lý và mã hóa." };
    text("#integrated-status", reasons[post.status] || post.reason || "Chưa có khóa mô hình đủ điều kiện để mã hóa.");
  }
  const elapsed = result.timings?.total_seconds;
  text("#runtime-label", finite(elapsed) ? `${formatNumber(elapsed * 1000)} MS` : "ĐÃ HOÀN TẤT");
  $("#session-details").hidden = false;
  text("#session-details", `Phiên ${String(result.session_id || "—")} · seed ${formatNumber(result.seed)} · Ngân sách mô hình ${formatNumber(post.entropy_budget_bits)} bit${finite(post.confirmation_leak_bits) ? ` · Xác nhận tiết lộ ${formatNumber(post.confirmation_leak_bits)} bit` : ""}`);
  renderVerification(result.verification);
}

function addHistory(result) {
  // Only public summary fields are retained; plaintext and API payloads are not stored.
  history.unshift({
    session_id: String(result.session_id || ""), signals: result.signals, seed: result.seed,
    eve_fraction: result.eve_fraction, noise_probability: result.noise_probability,
    sample_fraction: result.sample_fraction, qber: result.qber, status: result.status,
    output_bits: result.postprocessing?.output_bits ?? 0,
  });
  history.splice(10);
  const body = $("#history-body");
  body.replaceChildren();
  history.forEach((row, index) => {
    const tr = document.createElement("tr");
    const values = [`#${String(history.length - index).padStart(2, "0")} · ${row.session_id.slice(0, 7)}`, `${formatNumber(row.signals)} / ${row.seed}`, `${formatPercent(row.eve_fraction)} / ${formatPercent(row.noise_probability)}`, formatPercent(row.qber), statusLabels[row.status] || row.status, `${formatNumber(row.output_bits)} bit`];
    for (const value of values) { const cell = document.createElement("td"); cell.textContent = value; tr.append(cell); }
    body.append(tr);
  });
  text("#history-count", `${history.length} PHIÊN TRONG BỘ NHỚ`);
  $("#download-history").disabled = false;
}

function downloadHistory() {
  if (!history.length) return;
  const fields = Object.keys(history[0]);
  const cell = (value) => {
    let textValue = value == null ? "" : String(value);
    if (typeof value === "string" && /^[=+\-@\t\r]/.test(textValue)) textValue = `'${textValue}`;
    return `"${textValue.replaceAll('"', '""')}"`;
  };
  const csv = [fields.join(","), ...history.map((row) => fields.map((field) => cell(row[field])).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url; link.download = "bb84-lab-public-sessions.csv";
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function runSession(event) {
  event.preventDefault();
  const button = $("#run-session");
  if (button.disabled || !$("#simulation-form").reportValidity()) return;
  setBusy(button, true);
  $("#view-simulation").setAttribute("aria-busy", "true");
  showError("#session-error", null);
  try {
    const result = await request("/api/session", {
      signals: Number($("#signals").value), eve_fraction: Number($("#eve").value),
      noise_probability: Number($("#noise").value), sample_fraction: Number($("#sample").value),
      threshold: Number($("#threshold").value), min_samples: Number($("#min-samples").value),
      seed: Number($("#seed").value), message: $("#session-message").value,
      tamper_transcript: $("#tamper-transcript").checked,
    });
    renderSession(result);
    addHistory(result);
  } catch (error) {
    resetSessionAfterError();
    showError("#session-error", error);
  } finally {
    setBusy(button, false);
    $("#view-simulation").setAttribute("aria-busy", "false");
  }
}

async function runAead(event) {
  event.preventDefault();
  const button = $("#run-aead");
  if (button.disabled) return;
  setBusy(button, true);
  const host = $("#aead-result");
  host.textContent = "Đang kiểm tra mã hóa, sửa gói và phát lại…";
  host.style.color = "";
  try {
    const result = await request("/api/aead", { message: $("#aead-message").value });
    const checks = [["Khôi phục đúng", result.roundtrip_ok], ["Từ chối sửa bản mã", result.tamper_rejected], ["Từ chối phát lại", result.replay_rejected]];
    if (checks.some(([, passed]) => !passed)) throw new Error("Có kiểm tra AEAD không đạt. Không coi demo là thành công.");
    const list = document.createElement("div");
    list.className = "check-list";
    for (const [label] of checks) { const item = document.createElement("span"); item.textContent = label; list.append(item); }
    const note = document.createElement("p");
    note.className = "input-help";
    note.textContent = `${result.implementation || result.algorithm} · khóa ${formatNumber(result.key_bytes)} byte · nonce ${formatNumber(result.nonce_bytes)} byte · AAD ${formatNumber(result.aad_bytes)} byte · tag ${formatNumber(result.tag_bytes)} byte · ${formatNumber(result.plaintext_bytes)} byte bản rõ thành ${formatNumber(result.ciphertext_bytes)} byte bản mã+tag · SHA-256 ${String(result.ciphertext_sha256 || "").slice(0, 16)}…`;
    host.replaceChildren(list, note);
  } catch (error) {
    host.textContent = error.message;
    host.style.color = "#b84242";
  } finally { setBusy(button, false); }
}

function studyRows() {
  return Array.isArray(study?.evaluation_summary) && study.evaluation_summary.length ? study.evaluation_summary : Array.isArray(study?.main_summary) ? study.main_summary : [];
}

function fillOptions(selector, values, formatter) {
  const select = $(selector);
  const old = select.value;
  select.replaceChildren();
  for (const value of values) { const option = document.createElement("option"); option.value = String(value); option.textContent = formatter(value); select.append(option); }
  if (values.some((value) => String(value) === old)) select.value = old;
}

function renderStudyChart() {
  if (!study) return;
  const rows = studyRows().filter((row) => row.signals === Number($("#study-n").value) && row.noise_probability === Number($("#study-noise").value)).sort((a, b) => a.sample_fraction - b.sample_fraction || a.eve_fraction - b.eve_fraction);
  const chart = $("#study-chart");
  chart.replaceChildren();
  const body = $("#study-table");
  body.replaceChildren();
  if (!rows.length) {
    const message = document.createElement("p"); message.className = "chart-empty"; message.textContent = "Không có cấu hình phù hợp bộ lọc."; chart.append(message);
    return;
  }
  const width = 880, height = 315;
  const left = 55, right = 30, top = 28, bottom = 65;
  const validRows = rows.filter((row) => finite(row.qber_mean) && finite(row.eve_fraction));
  const maxY = Math.max(.3, Math.ceil(Math.max(0, ...validRows.map((row) => row.qber_mean), ...rows.map((row) => finite(row.expected_qber) ? row.expected_qber : 0)) * 5) / 5);
  const x = (value) => left + value * (width - left - right);
  const y = (value) => height - bottom - value / maxY * (height - bottom - top);
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-labelledby": "study-chart-title" });
  svg.append(svgElement("title", { id: "study-chart-title" }, `QBER trung bình theo Eve, N=${$("#study-n").value}, nhiễu ${formatPercent(Number($("#study-noise").value))}. Chi tiết và độ bất định có trong bảng bên dưới.`));
  for (let index = 0; index <= 4; index++) {
    const q = maxY * index / 4;
    svg.append(svgElement("line", { x1: left, x2: width - right, y1: y(q), y2: y(q), stroke: "#e6edef", "stroke-width": 1 }));
    svg.append(svgElement("text", { x: left - 11, y: y(q) + 4, "text-anchor": "end", fill: "#8ca2ae", "font-size": 10 }, formatPercent(q)));
    const f = index / 4;
    svg.append(svgElement("text", { x: x(f), y: height - bottom + 22, "text-anchor": "middle", fill: "#8ca2ae", "font-size": 10 }, formatPercent(f)));
  }
  svg.append(svgElement("text", { x: 10, y: 15, fill: "#6e8b98", "font-size": 10 }, "QBER"));
  svg.append(svgElement("text", { x: width - right, y: height - bottom + 43, "text-anchor": "end", fill: "#829aa6", "font-size": 10 }, "Tỷ lệ Eve chặn"));
  const theoretical = [...new Map(rows.filter((row) => finite(row.expected_qber)).map((row) => [row.eve_fraction, row])).values()].sort((a, b) => a.eve_fraction - b.eve_fraction);
  if (theoretical.length) svg.append(svgElement("polyline", { points: theoretical.map((row) => `${x(row.eve_fraction)},${y(row.expected_qber)}`).join(" "), fill: "none", stroke: "#b1bdc3", "stroke-width": 2, "stroke-dasharray": "5 4" }));
  const alphas = [...new Set(validRows.map((row) => row.sample_fraction))];
  const colors = ["#087e82", "#4c76a6", "#c18c3b"];
  alphas.forEach((alpha, index) => {
    const series = validRows.filter((row) => row.sample_fraction === alpha).sort((a, b) => a.eve_fraction - b.eve_fraction);
    const color = colors[index % colors.length];
    svg.append(svgElement("polyline", { points: series.map((row) => `${x(row.eve_fraction)},${y(row.qber_mean)}`).join(" "), fill: "none", stroke: color, "stroke-width": 2 }));
    series.forEach((row) => { const dot = svgElement("circle", { cx: x(row.eve_fraction), cy: y(row.qber_mean), r: 4, fill: "white", stroke: color, "stroke-width": 2 }); dot.append(svgElement("title", {}, `Eve ${formatPercent(row.eve_fraction)}; mẫu ${formatPercent(alpha)}; QBER ${formatPercent(row.qber_mean)}`)); svg.append(dot); });
    svg.append(svgElement("line", { x1: left + index * 145, x2: left + index * 145 + 18, y1: height - 8, y2: height - 8, stroke: color, "stroke-width": 3 }));
    svg.append(svgElement("text", { x: left + index * 145 + 25, y: height - 5, fill: "#6c8996", "font-size": 10 }, `Lấy mẫu ${formatPercent(alpha)}`));
  });
  chart.append(svg);
  rows.forEach((row) => {
    const interval = Array.isArray(row.anomalous_ci95) ? ` [${formatPercent(row.anomalous_ci95[0])}; ${formatPercent(row.anomalous_ci95[1])}]` : "";
    const values = [formatPercent(row.eve_fraction), formatPercent(row.sample_fraction), formatNumber(row.sessions), formatPercent(row.qber_mean), `${formatPercent(row.anomalous_rate)}${interval}`, formatPercent(row.inconclusive_rate), formatNumber(row.y_pre_mean)];
    const tr = document.createElement("tr");
    for (const value of values) { const cell = document.createElement("td"); cell.textContent = value; tr.append(cell); }
    body.append(tr);
  });
  renderPairedTable();
}

function renderPairedTable() {
  const body = $("#paired-table");
  body.replaceChildren();
  const rows = (Array.isArray(study?.paired_summary) ? study.paired_summary : [])
    .filter((row) => row.noise_probability === Number($("#study-noise").value))
    .sort((a, b) => a.eve_fraction - b.eve_fraction || a.sample_fraction - b.sample_fraction);
  if (Number($("#study-n").value) !== 4096 || !rows.length) {
    const tr = document.createElement("tr"), cell = document.createElement("td");
    cell.colSpan = 7; cell.className = "empty-cell";
    cell.textContent = "Đối sánh ghép cặp thực hiện ở N=4.096. Chưa có dữ liệu phù hợp bộ lọc.";
    tr.append(cell); body.append(tr); return;
  }
  rows.forEach((row) => {
    const interval = Array.isArray(row.ci95) ? `[${formatNumber(row.ci95[0])}; ${formatNumber(row.ci95[1])}]` : "—";
    const values = [formatPercent(row.eve_fraction), formatPercent(row.sample_fraction), formatNumber(row.pairs), `${formatNumber(row.mean_difference)} · ${interval}`, formatNumber(row.median), `${formatNumber(row.minimum)} → ${formatNumber(row.maximum)}`, row.inference || "—"];
    const tr = document.createElement("tr");
    for (const value of values) { const cell = document.createElement("td"); cell.textContent = value; tr.append(cell); }
    body.append(tr);
  });
}

function safeLocalUrl(value) {
  if (typeof value !== "string") return null;
  try { const url = new URL(value, window.location.href); return url.origin === window.location.origin && ["http:", "https:"].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}

function renderStudy() {
  const rows = studyRows();
  $("#study-empty").hidden = Boolean(study.available && rows.length);
  $("#study-content").hidden = !study.available || !rows.length;
  if (!study.available || !rows.length) return;
  const manifest = study.manifest || {};
  const selection = study.selection || {};
  const sessions = manifest.independent_sessions ?? manifest.total_independent_sessions ?? (finite(manifest.main_sessions) && finite(manifest.evaluation_sessions) ? manifest.main_sessions + manifest.evaluation_sessions : null);
  const alpha = selection.selected_fraction ?? selection.selected_alpha ?? selection.sample_fraction ?? selection.chosen_alpha ?? selection.alpha;
  text("#study-sessions", formatNumber(sessions));
  text("#study-alpha", formatPercent(alpha));
  text("#study-evaluation", formatNumber(manifest.evaluation_sessions ?? manifest.evaluation_independent_sessions));
  text("#study-source-label", study.evaluation_summary?.length ? "BỘ ĐÁNH GIÁ ĐỘC LẬP" : "MA TRẬN CHÍNH");
  fillOptions("#study-n", [...new Set(rows.map((row) => row.signals).filter(finite))].sort((a, b) => a - b), formatNumber);
  if ([...$("#study-n").options].some((option) => option.value === "4096")) $("#study-n").value = "4096";
  fillOptions("#study-noise", [...new Set(rows.map((row) => row.noise_probability).filter(finite))].sort((a, b) => a - b), formatPercent);
  text("#study-selection-note", selection.reason || selection.conclusion || "Tỷ lệ mẫu phải được chốt trên dữ liệu hiệu chỉnh trước khi xem dữ liệu đánh giá. Kết quả không cải thiện cũng là một kết quả hợp lệ.");
  const postManifest = study.postprocessing_manifest || {};
  const postComplete = postManifest.state === "complete";
  $("#study-postprocessing").hidden = !postComplete;
  if (postComplete) {
    text("#study-post-rows", formatNumber(postManifest.rows));
    text("#study-post-ready", formatNumber(postManifest.ready_sessions));
    text("#study-post-failed", formatNumber(postManifest.failed_sessions));
  }
  const links = $("#study-downloads"); links.replaceChildren();
  for (const item of Array.isArray(study.downloads) ? study.downloads : []) {
    const url = safeLocalUrl(item.url);
    if (!url) continue;
    const link = document.createElement("a"); link.href = url; link.textContent = item.label || item.name || "Tải dữ liệu"; link.setAttribute("download", ""); links.append(link);
  }
  const figures = $("#study-figures"); figures.replaceChildren();
  for (const item of Array.isArray(study.figures) ? study.figures : []) {
    const url = safeLocalUrl(item.url);
    if (!url) continue;
    const figure = document.createElement("figure");
    const image = document.createElement("img"); image.src = url; image.alt = item.name || "Biểu đồ thí nghiệm"; image.loading = "lazy";
    const caption = document.createElement("figcaption"); caption.textContent = item.name || "Biểu đồ từ dữ liệu đã đo";
    figure.append(image, caption); figures.append(figure);
  }
  renderStudyChart();
}

async function loadStudy() {
  if (studyLoading) return;
  studyLoading = true;
  setBusy($("#refresh-study"), true);
  showError("#study-error", null);
  try { study = await request("/api/study"); renderStudy(); }
  catch (error) { showError("#study-error", error); }
  finally { studyLoading = false; setBusy($("#refresh-study"), false); }
}

async function checkConnection() {
  const host = $("#connection-status");
  try {
    await request("/api/health");
    host.querySelector(".status-dot").className = "status-dot";
    host.querySelector("span:last-child").textContent = "Máy chủ cục bộ sẵn sàng";
  } catch {
    host.querySelector(".status-dot").className = "status-dot offline";
    host.querySelector("span:last-child").textContent = "Chưa kết nối máy chủ";
  }
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelectorAll("[data-preset]").forEach((button) => button.addEventListener("click", () => choosePreset(button.dataset.preset)));
for (const id of ["signals", "eve", "noise", "sample", "threshold", "min-samples"]) $(`#${id}`).addEventListener("input", () => {
  document.querySelectorAll("[data-preset]").forEach((button) => button.classList.remove("active"));
  updateSliders();
});
$("#simulation-form").addEventListener("submit", runSession);
$("#aead-form").addEventListener("submit", runAead);
$("#download-history").addEventListener("click", downloadHistory);
$("#download-verification").addEventListener("click", downloadVerification);
$("#refresh-study").addEventListener("click", loadStudy);
$("#study-n").addEventListener("change", renderStudyChart);
$("#study-noise").addEventListener("change", renderStudyChart);
window.addEventListener("hashchange", () => setView(window.location.hash.slice(1), false));
updateSliders();
setView(window.location.hash.slice(1) || "simulation", false);
checkConnection();
