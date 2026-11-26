"use strict";

const keyStatus = document.querySelector("#setup-key-status");
const keyPath = document.querySelector("#setup-key-path");
const keyActions = document.querySelector("#setup-key-actions");
const keyInvalid = document.querySelector("#setup-key-invalid");
const keyFeedback = document.querySelector("#setup-key-feedback");
const createKey = document.querySelector("#setup-create-psk");
const importKey = document.querySelector("#setup-import-psk");
const keyFile = document.querySelector("#setup-psk-file");
const roleForm = document.querySelector("#setup-role-form");
const roleOptions = document.querySelector("#setup-role-options");
const host = document.querySelector("#setup-host");
const hostLabel = document.querySelector("#setup-host-label");
const hostHelp = document.querySelector("#setup-host-help");
const port = document.querySelector("#setup-port");
const start = document.querySelector("#setup-start");
const startHint = document.querySelector("#setup-start-hint");
const active = document.querySelector("#setup-active");
const activeRole = document.querySelector("#setup-active-role");
const roleFeedback = document.querySelector("#setup-status");

let setup = null;
let pending = false;

function roleName(role) {
  return role === "alice" ? "Alice" : "Bob";
}

function showStatus(element, message, failed = false) {
  element.textContent = message;
  element.classList.toggle("error", failed);
}

function render() {
  const role = roleForm.elements.role.value;
  const alice = role === "alice";
  hostLabel.textContent = alice ? "IPv4 đích" : "IPv4 của máy này";
  if (alice) {
    hostHelp.textContent = "Nhập IPv4 và cổng đang hiển thị trên máy Bob. Nếu demo qua Eve, nhập địa chỉ và cổng của Eve.";
  } else {
    const command = document.createElement("code");
    command.textContent = "ipconfig";
    hostHelp.replaceChildren("Chạy ", command, " trên máy Bob. Dùng địa chỉ IPv4 của Wi‑Fi, Ethernet hoặc VPN đang kết nối hai máy.");
  }
  start.textContent = `Khởi động ${roleName(role)}`;

  if (setup) {
    keyStatus.textContent = setup.psk_ready ? "PSK đã sẵn sàng" : "Chưa có PSK hợp lệ";
    keyStatus.dataset.ready = setup.psk_ready;
    keyPath.textContent = setup.psk_path;
    keyActions.hidden = setup.psk_ready || setup.psk_exists || Boolean(setup.role);
    keyInvalid.hidden = !setup.psk_exists || setup.psk_ready;
    roleForm.hidden = Boolean(setup.role);
    active.hidden = !setup.role;
    if (setup.role) {
      activeRole.textContent = `${roleName(setup.role)} đang chạy trên máy này.`;
    }
  }

  createKey.disabled = pending;
  importKey.disabled = pending;
  roleOptions.disabled = !setup || pending;
  host.disabled = !setup || pending;
  port.disabled = !setup || pending;
  start.disabled = !setup?.psk_ready || pending;
  startHint.hidden = Boolean(setup?.psk_ready);
}

async function requestSetup(path, options = {}) {
  let response;
  let data;
  try {
    response = await fetch(path, { cache: "no-store", ...options });
    data = await response.json();
  } catch {
    throw new Error("Không đọc được phản hồi. Kiểm tra trình khởi động rồi tải lại trang.");
  }
  if (!response.ok) {
    throw new Error(data.error || "Không thực hiện được yêu cầu.");
  }
  return data;
}

function postOptions(contentType, body) {
  return { method: "POST", headers: { "Content-Type": contentType }, body };
}

async function submit(path, options, { feedback, working, success, redirect = false }) {
  if (pending) return;
  pending = true;
  showStatus(feedback, working);
  render();
  try {
    setup = await requestSetup(path, options);
    if (redirect) {
      window.location.assign("/");
    } else {
      showStatus(feedback, success);
    }
  } catch (error) {
    showStatus(feedback, error.message, true);
    try {
      setup = await requestSetup("/api/setup");
    } catch {
      // Keep the last known setup state if the server is unreachable.
    }
  } finally {
    pending = false;
    render();
  }
}

createKey.addEventListener("click", () => {
  submit("/api/setup/psk", postOptions("application/json", "{}"), {
    feedback: keyFeedback,
    working: "Đang tạo PSK…",
    success: "Đã tạo PSK. Dùng tệp ở đường dẫn trên để nhập vào máy còn lại.",
  });
});

importKey.addEventListener("click", () => keyFile.click());
keyFile.addEventListener("change", () => {
  const file = keyFile.files[0];
  keyFile.value = "";
  if (!file) return;
  if (file.size !== 32) {
    showStatus(keyFeedback, "Chọn tệp PSK đúng 32 byte đã tạo trên máy kia.", true);
    return;
  }
  submit("/api/setup/psk-import", postOptions("application/octet-stream", file), {
    feedback: keyFeedback,
    working: "Đang nhập tệp PSK…",
    success: "Đã nhập tệp PSK.",
  });
});

roleOptions.addEventListener("change", render);
roleForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!setup?.psk_ready || setup.role || pending) return;
  const role = roleForm.elements.role.value;
  const address = host.value.trim();
  const listenPort = port.valueAsNumber;
  if (!address) {
    showStatus(roleFeedback, "Nhập địa chỉ IPv4 để khởi động.", true);
    host.focus();
    return;
  }
  submit("/api/setup/start", postOptions("application/json", JSON.stringify({ role, host: address, port: listenPort })), {
    feedback: roleFeedback,
    working: `Đang khởi động ${roleName(role)}…`,
    redirect: true,
  });
});

async function loadSetup() {
  try {
    setup = await requestSetup("/api/setup");
    port.value = setup.port;
    render();
  } catch (error) {
    keyStatus.textContent = "Chưa đọc được trạng thái PSK";
    showStatus(keyFeedback, error.message, true);
  }
}

loadSetup();
