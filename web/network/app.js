"use strict";

const $ = (id) => document.getElementById(id);
const embeddedEve = window.location.pathname === "/eve";
const apiPrefix = embeddedEve ? "/api/eve" : "/api";
const labels = { idle: "Chờ phiên mới", connecting: "Đang kết nối", connected: "Đã kết nối", qber: "Đã đo QBER", key: "Khóa đã khớp", transferring: "Đang truyền", complete: "Hoàn tất", aborted: "Đã hủy", failed: "Thất bại", configured: "Đã đổi chế độ", attack: "Đã can thiệp" };
const decisions = { continue: "Cho phép đi tiếp", anomalous: "Bất thường", inconclusive: "Chưa đủ bằng chứng", insufficient_key: "Không đủ bit khóa", chsh_rejected: "CHSH không vượt mốc 2", chsh_inconclusive: "CHSH chưa đủ bằng chứng" };
const bellStatuses = { violation: "Vượt mốc 2", at_or_below_bound: "Trong giới hạn cổ điển", inconclusive: "Chưa đủ bằng chứng" };
const modes = { pass: "Chỉ chuyển tiếp", intercept: "Chặn–đo–gửi lại", tamper: "Sửa bản mã", replay: "Phát lại", drop: "Ngắt truyền", "tamper-public": "Sửa thảo luận công khai" };
const traceStages = { auth: "Xác thực", bb84: "BB84", e91: "E91", cascade: "Cascade", toeplitz: "Toeplitz", transfer: "Truyền dữ liệu" };
const traceStatuses = { info: "Thông tin", ok: "Đạt", stopped: "Dừng", error: "Lỗi" };
const tracePageSize = 100;
const traceStageButtons = document.querySelectorAll("[data-key-trace-stage]");
const percent = (v) => v == null ? "—" : `${(100 * v).toFixed(2)}%`;
const bellFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 4 });
const bytes = (n) => n >= 1024 ** 2 ? `${(n / 1024 ** 2).toFixed(2)} MiB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KiB` : `${n} byte`;
let state = null;
let uploading = false;
let renderedEvents = "";
let renderedTrace = null;
const traceDetail = { sessionId: null, stage: "bb84", offset: 0, page: null, request: null, error: "" };
const receivedIds = new Set();

function status(message, error = false) {
  $("form-status").textContent = message;
  $("form-status").classList.toggle("error", error);
}

function controlsDisabled() {
  const busy = uploading || !!state?.busy;
  document.querySelectorAll(".send-button, #apply-attack").forEach((button) => { button.disabled = busy; });
}

function addReceived(item) {
  if (receivedIds.has(item.id)) return;
  receivedIds.add(item.id);
  const article = document.createElement("article");
  article.className = "received-item";
  const title = document.createElement("h3");
  title.textContent = `${item.name} · ${bytes(item.size)}`;
  article.append(title);
  const url = `/api/download/${item.id}`;
  if (item.kind === "text") {
    const text = document.createElement("pre");
    text.textContent = item.text;
    article.append(text);
  } else {
    const extension = item.name.split(".").at(-1).toLowerCase();
    const type = ["png", "jpg", "jpeg", "gif", "webp"].includes(extension) ? "img"
      : ["mp4", "webm"].includes(extension) ? "video"
      : ["mp3", "wav", "ogg"].includes(extension) ? "audio" : null;
    if (type) {
      const media = document.createElement(type);
      media.src = url;
      if (type === "img") { media.alt = item.name; media.loading = "lazy"; }
      else { media.controls = true; media.preload = "metadata"; }
      article.append(media);
    }
  }
  const hash = document.createElement("p");
  hash.className = "file-hash";
  hash.textContent = `SHA-256 đã khớp: ${item.sha256}`;
  const link = document.createElement("a");
  link.href = url;
  link.download = item.name;
  link.textContent = "Tải tệp đã xác thực";
  article.append(hash, link);
  $("inbox").prepend(article);
}

function keyTraceRow(step) {
  const row = document.createElement("li");
  const time = document.createElement("time");
  time.dateTime = step.time;
  time.textContent = new Date(step.time).toLocaleTimeString("vi-VN");
  const line = document.createElement("div");
  const heading = document.createElement("div");
  heading.className = "key-terminal-line-heading";
  const stage = document.createElement("span");
  stage.className = "key-terminal-stage";
  stage.textContent = traceStages[step.stage];
  const title = document.createElement("strong");
  title.textContent = step.title;
  const outcome = document.createElement("span");
  outcome.className = "key-terminal-outcome";
  outcome.dataset.status = step.status;
  outcome.textContent = traceStatuses[step.status];
  const detail = document.createElement("p");
  detail.textContent = step.detail;
  heading.append(stage, title, outcome);
  line.append(heading, detail);
  row.append(time, line);
  return row;
}

function renderKeyTrace(trace) {
  if (!trace) return;
  const previous = renderedTrace;
  const refresh = !previous || (previous.session_id && previous.session_id !== trace.session_id) ||
    !previous.steps.every((step, index) => JSON.stringify(step) === JSON.stringify(trace.steps[index]));
  const firstNewStep = refresh ? 0 : previous.steps.length;
  if (!refresh && previous.session_id === trace.session_id && firstNewStep === trace.steps.length) return;

  const viewport = $("key-terminal-viewport");
  const list = $("key-terminal-lines");
  const follow = viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop < 24;
  if (refresh) {
    list.replaceChildren();
    $("key-terminal-feedback").textContent = "";
  }
  $("key-terminal-session").textContent = trace.session_id || "Chưa có";
  $("key-terminal-empty").hidden = trace.steps.length > 0;
  $("key-terminal-copy").disabled = trace.steps.length === 0;

  for (const step of trace.steps.slice(firstNewStep)) {
    list.append(keyTraceRow(step));
  }

  if (refresh) viewport.scrollTop = 0;
  else if (follow) viewport.scrollTop = viewport.scrollHeight;
  renderedTrace = trace;
}

async function copyKeyTrace() {
  const trace = renderedTrace;
  if (!trace?.steps.length) return;
  const title = `Terminal tạo khóa · ${state.role === "alice" ? "Alice" : "Bob"} · ${$("protocol-badge").textContent} · Phiên ${trace.session_id || "chưa có mã"}`;
  const lines = trace.steps.map((step) =>
    `[${step.time}] [${traceStages[step.stage]}] [${traceStatuses[step.status]}] ${step.title}\n${step.detail}`);
  try {
    await navigator.clipboard.writeText([title, ...lines].join("\n\n"));
    $("key-terminal-feedback").textContent = "Đã sao chép log.";
  } catch {
    $("key-terminal-feedback").textContent = "Hãy bôi đen nội dung terminal rồi nhấn Ctrl+C để sao chép.";
  }
}

function detailCounts() {
  const meta = state?.key_trace?.details?.[traceDetail.stage];
  return {
    recorded: Math.max(meta?.recorded || 0, traceDetail.page?.recorded || 0),
    omitted: Math.max(meta?.omitted || 0, traceDetail.page?.omitted || 0),
  };
}

function renderTraceDetailPage() {
  const { recorded, omitted } = detailCounts();
  const totalOnPage = traceDetail.page?.steps.length || 0;
  const label = $("key-trace-detail-status");
  const text = traceDetail.error || (!traceDetail.sessionId ? "Chưa có phiên để xem chi tiết."
    : totalOnPage ? `Dòng ${traceDetail.offset + 1}–${traceDetail.offset + totalOnPage} / ${recorded}`
    : traceDetail.request ? "Đang tải log chi tiết…" : "Giai đoạn này chưa ghi nhận bước chi tiết.");
  if (label.textContent !== text) label.textContent = text;
  const omittedLabel = $("key-trace-detail-omitted");
  omittedLabel.hidden = omitted === 0;
  omittedLabel.textContent = omitted ? `Đã lược ${omitted} dòng vì đạt giới hạn lưu của phiên.` : "";
  $("key-trace-detail-prev").disabled = traceDetail.offset === 0;
  $("key-trace-detail-next").disabled = traceDetail.offset + tracePageSize >= recorded;
  $("key-trace-detail-jump").hidden = recorded <= tracePageSize;
  $("key-trace-detail-page").max = Math.ceil(recorded / tracePageSize);
  $("key-trace-detail-retry").hidden = !traceDetail.error;
  $("key-trace-detail-viewport").hidden = totalOnPage === 0;
}

function resetTraceDetailPage(stage, offset) {
  traceDetail.request?.abort();
  Object.assign(traceDetail, { stage, offset, page: null, request: null, error: "" });
  for (const button of traceStageButtons) {
    button.setAttribute("aria-pressed", String(button.dataset.keyTraceStage === stage));
  }
  $("key-trace-detail-lines").replaceChildren();
  $("key-trace-detail-viewport").scrollTop = 0;
  $("key-trace-detail-page").value = offset / tracePageSize + 1;
}

async function loadTraceDetailPage() {
  const { sessionId, stage, offset, request, error, page } = traceDetail;
  if (!$("key-terminal-details").open || !sessionId || request || error) return;
  const length = page?.steps.length || 0;
  const expected = Math.min(tracePageSize, detailCounts().recorded - offset);
  if (length >= expected) return;

  const controller = new AbortController();
  traceDetail.request = controller;
  renderTraceDetailPage();
  try {
    const response = await fetch(`/api/key-trace/${encodeURIComponent(sessionId)}/${stage}/${offset}`, {
      cache: "no-store",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]),
    });
    if (response.status === 409) throw new Error("Phiên log đã thay đổi. Chờ terminal cập nhật phiên mới.");
    if (!response.ok) throw new Error("Không tải được log chi tiết.");
    const next = await response.json();
    if (traceDetail.request !== controller) return;
    const rows = next.steps.slice(length).map(keyTraceRow);
    $("key-trace-detail-lines").append(...rows);
    traceDetail.page = next;
  } catch (failure) {
    if (traceDetail.request === controller) {
      traceDetail.error = failure.name === "TimeoutError" ? "Tải log chi tiết quá thời gian." : failure.message;
    }
  } finally {
    if (traceDetail.request === controller) {
      traceDetail.request = null;
      renderTraceDetailPage();
    }
  }
}

function renderKeyTraceDetails(trace) {
  const panel = $("key-terminal-details");
  panel.hidden = !trace?.details;
  if (panel.hidden) return;
  if (traceDetail.sessionId !== trace.session_id) {
    traceDetail.sessionId = trace.session_id;
    resetTraceDetailPage(state.protocol === "e91" ? "e91" : "bb84", 0);
  }
  if (panel.open) {
    renderTraceDetailPage();
    loadTraceDetailPage();
  }
}

function render(next) {
  const first = state === null;
  state = next;
  const isE91 = state.protocol === "e91";
  if (first) {
    $("setup-link").hidden = !state.setup_available;
    $("eve-link").hidden = !embeddedEve && !state.eve_available;
    if (embeddedEve) {
      $("network-session-link").textContent = "Về Alice";
      $("network-session-link").removeAttribute("aria-current");
      $("eve-link").setAttribute("aria-current", "page");
    }
    const names = { alice: "Alice · Gửi dữ liệu", bob: "Bob · Nhận dữ liệu", eve: "Eve · Điều khiển can thiệp" };
    $("role-title").textContent = names[state.role];
    const protocolName = isE91 ? "E91" : "BB84";
    document.title = `${protocolName} qua mạng · BB84 Lab`;
    $("protocol-badge").textContent = protocolName;
    $("protocol-badge").hidden = false;
    if (isE91) $("key-lesson-link").textContent = "Bài học BB84";
    $("role-badge").textContent = embeddedEve ? "Cùng máy Alice" : state.role === "eve" ? "Máy thứ ba / máy ảo" : "Thiết bị độc lập";
    $("role-description").textContent = state.role === "eve" ? `Quan sát và tác động lên đường truyền mô phỏng ${protocolName}.` : `Gửi văn bản và tệp giữa hai máy với phiên ${protocolName} mô phỏng.`;
    $(`${state.role}-controls`).hidden = false;
    document.querySelector(`[data-role="${state.role}"]`).classList.add("current");
    $("inbox-section").hidden = state.role !== "bob";
    $("key-terminal").hidden = !["alice", "bob"].includes(state.role);
    $("key-terminal-description").textContent = `Nhật ký ${protocolName}, Cascade và Toeplitz của phiên trên máy này.`;
    $("decision-label").textContent = isE91 ? "Quyết định CHSH và QBER" : "Quyết định QBER";
    for (const metric of document.querySelectorAll("[data-e91-metric]")) metric.hidden = !isE91;
    for (const button of traceStageButtons) {
      const stage = button.dataset.keyTraceStage;
      if (stage === "e91" || stage === "bb84") button.hidden = stage !== (isE91 ? "e91" : "bb84");
    }
    resetTraceDetailPage(isE91 ? "e91" : "bb84", 0);
    const nextRole = state.eve_available ? "Eve" : embeddedEve ? "Bob" : "Đầu tiếp theo";
    const destination = state.target ? `${nextRole}: ${state.target.join(":")}. ` : "";
    const listen = state.listen ? `Lắng nghe: ${state.listen.join(":")}.` : "";
    $("address-note").textContent = destination + listen;
    $("file-limit").textContent = `Giới hạn tệp: ${bytes(state.max_file_bytes)}.`;
    if (state.role === "eve") {
      $("attack-mode").value = state.mode;
      $("eve-fraction").value = state.fraction;
      if (isE91) {
        $("eve-intercept-mode").textContent = "Làm mất tương quan";
        $("eve-fraction-label").textContent = "Tỷ lệ cặp bị làm mất tương quan";
        $("eve-fraction-help").textContent = "Từ 0 đến 1, áp dụng khi chọn làm mất tương quan. Trên các cặp bị chọn, phép đo của Bob cho kết quả ngẫu nhiên độc lập.";
      }
    }
  }
  $("connection").textContent = "Giao diện local đang kết nối";
  $("state").textContent = isE91 && state.state === "qber" ? "Đã đo CHSH và QBER" : labels[state.state] || state.state;
  $("state").dataset.state = state.state;
  const s = state.statistics;
  $("qber").textContent = percent(s.qber);
  $("wilson").textContent = s.ci_low == null ? "—" : `${percent(s.ci_low)} – ${percent(s.ci_high)}`;
  $("sample-count").textContent = s.sample_count ?? "—";
  $("retained").textContent = s.retained_bits ?? "—";
  $("output-bits").textContent = s.output_bits ?? "—";
  $("decision").textContent = decisions[s.status] || "—";
  if (isE91) {
    const bell = s.bell;
    $("chsh-value").textContent = bell?.abs_s == null ? "—" : bellFormat.format(bell.abs_s);
    $("chsh-interval").textContent = bell?.ci_low == null ? "—" : `${bellFormat.format(bell.ci_low)} đến ${bellFormat.format(bell.ci_high)}`;
    $("chsh-status").textContent = bellStatuses[bell?.status] || "—";
  }
  $("session-note").textContent = s.session_id ? `Phiên ${s.session_id.slice(0, 16)}…` : "Kết quả xuất hiện khi hai bên thực hiện giao thức.";
  const progress = state.progress;
  $("transfer-progress").max = Math.max(1, progress.total || 0);
  $("transfer-progress").value = progress.bytes || 0;
  $("progress-caption").textContent = progress.total ? `${bytes(progress.bytes)} / ${bytes(progress.total)}${state.state === "complete" ? " · Đã xác thực toàn bộ" : ""}` : "Chưa truyền dữ liệu hoặc tệp rỗng";
  if (!$("key-terminal").hidden) {
    renderKeyTrace(state.key_trace);
    renderKeyTraceDetails(state.key_trace);
  }
  if (state.role === "eve") {
    const name = isE91 && state.mode === "intercept" ? $("eve-intercept-mode").textContent : modes[state.mode];
    $("active-mode").textContent = `Đang dùng ${name}. Tỷ lệ ${state.fraction}.`;
  }
  const signature = JSON.stringify(state.events);
  if (signature !== renderedEvents) {
    renderedEvents = signature;
    $("events").replaceChildren();
    [...state.events].reverse().forEach((event) => {
      const row = document.createElement("li");
      const time = document.createElement("time");
      time.dateTime = event.time;
      time.textContent = new Date(event.time).toLocaleTimeString("vi-VN");
      const text = document.createElement("span");
      text.textContent = event.message;
      row.append(time, text);
      $("events").append(row);
    });
  }
  state.received.forEach(addReceived);
  $("inbox-empty").hidden = state.received.length > 0;
  controlsDisabled();
}

async function post(url, payload) {
  const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "Yêu cầu thất bại");
  return value;
}

$("message").addEventListener("input", () => {
  $("text-size").textContent = `${new TextEncoder().encode($("message").value).length} / 16.384 byte UTF-8`;
});
$("message").dispatchEvent(new Event("input"));
$("key-terminal-copy").addEventListener("click", copyKeyTrace);
$("key-terminal-details").addEventListener("toggle", () => renderKeyTraceDetails(state?.key_trace));
for (const button of traceStageButtons) {
  button.addEventListener("click", () => {
    const stage = button.dataset.keyTraceStage;
    if (traceDetail.stage === stage) return;
    resetTraceDetailPage(stage, 0);
    renderKeyTraceDetails(state.key_trace);
  });
}
for (const [button, delta] of [["key-trace-detail-prev", -tracePageSize], ["key-trace-detail-next", tracePageSize]]) {
  $(button).addEventListener("click", () => {
    resetTraceDetailPage(traceDetail.stage, traceDetail.offset + delta);
    renderKeyTraceDetails(state.key_trace);
  });
}
$("key-trace-detail-retry").addEventListener("click", () => {
  traceDetail.error = "";
  renderKeyTraceDetails(state.key_trace);
});
$("key-trace-detail-jump").addEventListener("submit", (event) => {
  event.preventDefault();
  const offset = ($("key-trace-detail-page").valueAsNumber - 1) * tracePageSize;
  if (offset === traceDetail.offset) return;
  resetTraceDetailPage(traceDetail.stage, offset);
  renderKeyTraceDetails(state.key_trace);
});

$("text-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  uploading = true; controlsDisabled();
  try {
    if (new TextEncoder().encode($("message").value).length > 16384) throw new Error("Văn bản vượt 16.384 byte UTF-8");
    await post("/api/send-text", { message: $("message").value });
    status("Đã tạo yêu cầu gửi. Theo dõi phiên và biên nhận của Bob ở mục Phiên đang quan sát.");
    await poll(false);
  } catch (error) { status(error.message, true); }
  finally { uploading = false; controlsDisabled(); }
});

$("file-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const file = $("file").files[0];
  if (!file) { status("Chọn một tệp trước khi gửi.", true); return; }
  if (file.size > state.max_file_bytes) { status("Tệp vượt giới hạn dung lượng.", true); return; }
  uploading = true; controlsDisabled();
  const request = new XMLHttpRequest();
  request.open("POST", "/api/upload");
  request.setRequestHeader("Content-Type", "application/octet-stream");
  request.setRequestHeader("X-Filename", encodeURIComponent(file.name));
  request.upload.onprogress = (progress) => status(`Chuẩn bị tệp trên máy Alice: ${bytes(progress.loaded)} / ${bytes(file.size)}`);
  request.onerror = () => { uploading = false; controlsDisabled(); status("Mất kết nối giao diện local.", true); };
  request.onload = async () => {
    uploading = false;
    try {
      const value = JSON.parse(request.responseText);
      if (request.status !== 202) throw new Error(value.error || "Không gửi được tệp");
      status("Đã chuẩn bị tệp. Đang trao đổi khóa và gửi tới Bob.");
      await poll(false);
    } catch (error) { status(error.message, true); }
    controlsDisabled();
  };
  request.send(file);
});

$("eve-controls").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await post(`${apiPrefix}/attack`, { mode: $("attack-mode").value, fraction: Number($("eve-fraction").value) });
    status("Đã áp dụng chế độ cho phiên tiếp theo.");
    await poll(false);
  } catch (error) { status(error.message, true); }
});

async function poll(schedule = true) {
  try {
    const response = await fetch(`${apiPrefix}/state`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error("Không đọc được trạng thái");
    render(await response.json());
  } catch (error) { $("connection").textContent = "Mất kết nối giao diện; kiểm tra tiến trình Python"; }
  finally { if (schedule) setTimeout(poll, 900); }
}
poll();
