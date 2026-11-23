"use strict";

const $ = (id) => document.getElementById(id);
const labels = { idle: "Chờ phiên mới", connecting: "Đang kết nối", connected: "Đã kết nối", qber: "Đã đo QBER", key: "Khóa đã khớp", transferring: "Đang truyền", complete: "Hoàn tất", aborted: "Đã hủy", failed: "Thất bại", configured: "Đã đổi chế độ", attack: "Đã can thiệp" };
const decisions = { continue: "Cho phép đi tiếp", anomalous: "Bất thường", inconclusive: "Chưa đủ bằng chứng", insufficient_key: "Không đủ bit khóa" };
const modes = { pass: "Chỉ chuyển tiếp", intercept: "Chặn–đo–gửi lại", tamper: "Sửa bản mã", replay: "Phát lại", drop: "Ngắt truyền", "tamper-public": "Sửa thảo luận công khai" };
const percent = (v) => v == null ? "—" : `${(100 * v).toFixed(2)}%`;
const bytes = (n) => n >= 1024 ** 2 ? `${(n / 1024 ** 2).toFixed(2)} MiB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KiB` : `${n} byte`;
let state = null;
let uploading = false;
let renderedEvents = "";
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

function render(next) {
  const first = state === null;
  state = next;
  if (first) {
    const names = { alice: "Alice · Gửi dữ liệu", bob: "Bob · Nhận dữ liệu", eve: "Eve · Điều khiển can thiệp" };
    $("role-title").textContent = names[state.role];
    $("role-badge").textContent = state.role === "eve" ? "Máy thứ ba / máy ảo" : "Thiết bị độc lập";
    $("role-description").textContent = state.role === "eve" ? "Quan sát và tác động lên đường truyền giữa hai thiết bị." : "Văn bản, hình ảnh, âm thanh và video giữa hai thiết bị khác mạng.";
    $(`${state.role}-controls`).hidden = false;
    document.querySelector(`[data-role="${state.role}"]`).classList.add("current");
    $("inbox-section").hidden = state.role !== "bob";
    const destination = state.target ? `Đầu tiếp theo: ${state.target.join(":")}. ` : "";
    const listen = state.listen ? `Lắng nghe: ${state.listen.join(":")}.` : "";
    $("address-note").textContent = destination + listen;
    $("file-limit").textContent = `Giới hạn tệp: ${bytes(state.max_file_bytes)}.`;
    if (state.role === "eve") {
      $("attack-mode").value = state.mode;
      $("eve-fraction").value = state.fraction;
    }
  }
  $("connection").textContent = "Giao diện local đang kết nối";
  $("state").textContent = labels[state.state] || state.state;
  $("state").dataset.state = state.state;
  const s = state.statistics;
  $("qber").textContent = percent(s.qber);
  $("wilson").textContent = s.ci_low == null ? "—" : `${percent(s.ci_low)} – ${percent(s.ci_high)}`;
  $("sample-count").textContent = s.sample_count ?? "—";
  $("retained").textContent = s.retained_bits ?? "—";
  $("output-bits").textContent = s.output_bits ?? "—";
  $("decision").textContent = decisions[s.status] || "—";
  $("session-note").textContent = s.session_id ? `Phiên ${s.session_id.slice(0, 16)}…` : "Kết quả xuất hiện khi hai bên thực hiện giao thức.";
  const progress = state.progress;
  $("transfer-progress").max = Math.max(1, progress.total || 0);
  $("transfer-progress").value = progress.bytes || 0;
  $("progress-caption").textContent = progress.total ? `${bytes(progress.bytes)} / ${bytes(progress.total)}${state.state === "complete" ? " · Đã xác thực toàn bộ" : ""}` : "Chưa truyền dữ liệu hoặc tệp rỗng";
  if (state.role === "eve") $("active-mode").textContent = `Đang dùng: ${modes[state.mode]}; tỷ lệ ${state.fraction}.`;
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
    await post("/api/attack", { mode: $("attack-mode").value, fraction: Number($("eve-fraction").value) });
    status("Đã áp dụng chế độ cho phiên tiếp theo.");
    await poll(false);
  } catch (error) { status(error.message, true); }
});

async function poll(schedule = true) {
  try {
    const response = await fetch("/api/state", { cache: "no-store", signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error("Không đọc được trạng thái");
    render(await response.json());
  } catch (error) { $("connection").textContent = "Mất kết nối giao diện; kiểm tra tiến trình Python"; }
  finally { if (schedule) setTimeout(poll, 900); }
}
poll();
