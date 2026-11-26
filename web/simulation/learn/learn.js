(() => {
  "use strict";
  const course = window.BB84_COURSE;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const normalize = value => String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replaceAll("đ", "d").replaceAll("Đ", "D").toLowerCase();
  const pct = value => value == null ? "Không xác định" : `${(value * 100).toLocaleString("vi-VN", {maximumFractionDigits: 2})}%`;
  const num = value => Number(value).toLocaleString("vi-VN");
  const sourceHref = (path, symbol = "") => `#/code/${path}${symbol ? `?symbol=${encodeURIComponent(symbol)}` : ""}`;
  const sourceLink = (path, symbol = "", label = "") => `<a class="source-link" href="${esc(sourceHref(path, symbol))}"><span aria-hidden="true">&lt;/&gt;</span>${esc(label || symbol || path)}</a>`;
  const main = $("#main");
  const storageKey = "bb84-project-learning-v1";
  let storageAvailable = true;
  let state = {completed: [], notes: {}, answers: {}, lastLesson: "big-picture"};
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (saved && typeof saved === "object") {
      state.completed = Array.isArray(saved.completed) ? [...new Set(saved.completed.filter(id => course.lessons.some(l => l.id === id)))] : [];
      for (const key of ["notes", "answers"]) {
        if (saved[key] && typeof saved[key] === "object" && !Array.isArray(saved[key])) state[key] = saved[key];
      }
      if (course.lessons.some(l => l.id === saved.lastLesson)) state.lastLesson = saved.lastLesson;
    }
  } catch { storageAvailable = false; }
  function persist() {
    try { localStorage.setItem(storageKey, JSON.stringify(state)); return true; }
    catch { storageAvailable = false; return false; }
  }
  let toastTimer;
  function toast(text) {
    const el = $("#toast");
    el.textContent = text;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 3200);
  }
  function errorBox(text) { return `<div class="widget-error" role="alert">${esc(text)}</div>`; }
  const backendHelp = "Không kết nối được backend. Chạy .\\.venv\\Scripts\\python.exe -m bb84_lab.local --learn từ gốc project rồi mở trang qua địa chỉ server. Nếu đang dùng server cũ, khởi động lại để có trang học và API mới.";
  async function request(path, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(path, {
        method: payload === undefined ? "GET" : "POST",
        headers: payload === undefined ? {} : {"Content-Type": "application/json"},
        body: payload === undefined ? undefined : JSON.stringify(payload),
        signal: controller.signal,
      });
      const contentType = response.headers.get("Content-Type") || "";
      if (!contentType.includes("application/json")) throw new Error(backendHelp);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}: yêu cầu chưa hoàn tất.`);
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("Backend chưa trả lời sau 45 giây. Giảm số tín hiệu hoặc kiểm tra terminal đang chạy server rồi thử lại.");
      if (error instanceof TypeError) throw new Error(backendHelp);
      throw error;
    } finally { clearTimeout(timer); }
  }
  async function health() {
    const el = $("#server-status");
    try {
      const data = await request("/api/health");
      if (!data.ok || data.application !== "BB84 Lab") throw new Error("Wrong server");
      el.className = "server-status online";
      el.innerHTML = '<span aria-hidden="true">●</span> Backend sẵn sàng';
    } catch {
      el.className = "server-status offline";
      el.innerHTML = '<span aria-hidden="true">●</span> Backend chưa kết nối';
      el.title = backendHelp;
    }
  }
  let catalogPromise;
  const sourceCache = new Map();
  const getCatalog = () => catalogPromise ||= request("/api/learn/sources").then(data => data.sources).catch(error => { catalogPromise = null; throw error; });
  function getSource(path) {
    if (!sourceCache.has(path)) sourceCache.set(path, request(`/api/learn/source/${path}`).catch(error => { sourceCache.delete(path); throw error; }));
    return sourceCache.get(path);
  }

  function renderNav(active = "home") {
    const done = new Set(state.completed);
    $("#course-nav").innerHTML = `<a class="nav-item ${active === "home" ? "active" : ""}" href="#/" ${active === "home" ? 'aria-current="page"' : ""}><span class="nav-tool-icon" aria-hidden="true">⌂</span>Lộ trình của bạn</a>` + course.groups.map(group => `<p class="nav-group-title">${esc(group.short)}</p>${course.lessons.filter(l => l.group === group.id).map(lesson => {
      const index = course.lessons.indexOf(lesson) + 1;
      return `<a class="nav-item ${active === lesson.id ? "active" : ""}" href="#/lesson/${lesson.id}" ${active === lesson.id ? 'aria-current="page"' : ""}><span class="nav-index ${done.has(lesson.id) ? "done" : ""}" aria-label="${done.has(lesson.id) ? "Đã học" : `Bài ${index}`}">${done.has(lesson.id) ? "✓" : index}</span><span>${esc(lesson.title)}</span></a>`;
    }).join("")}`).join("") + `<p class="nav-group-title">Tra cứu khi cần</p>${[["map", "◇", "Bản đồ project"], ["code", "⌘", "Đọc code có chỉ dẫn"], ["glossary", "Aa", "Từ điển dễ hiểu"], ["abbreviations", "Ab", "Từ viết tắt & ký hiệu"]].map(([id, icon, title]) => `<a class="nav-item ${active === id ? "active" : ""}" href="#/${id}" ${active === id ? 'aria-current="page"' : ""}><span class="nav-tool-icon" aria-hidden="true">${icon}</span>${title}</a>`).join("")}`;
    $("#progress-text").textContent = `${done.size}/${course.lessons.length}`;
    $("#course-progress").max = course.lessons.length;
    $("#course-progress").value = done.size;
  }
  function setBreadcrumb(text, group) {
    $("#breadcrumb").innerHTML = group ? `${esc(group)} <span aria-hidden="true">/</span> ${esc(text)}` : esc(text);
  }
  function closeMenu() {
    $("#sidebar").classList.remove("open");
    $("#sidebar-scrim").hidden = true;
    $("#menu-toggle").setAttribute("aria-expanded", "false");
    if (window.matchMedia("(max-width:760px)").matches) $("#sidebar").inert = true;
  }
  $("#menu-toggle").addEventListener("click", () => {
    const isOpen = $("#sidebar").classList.toggle("open");
    $("#sidebar-scrim").hidden = !isOpen;
    $("#sidebar").inert = !isOpen;
    $("#menu-toggle").setAttribute("aria-expanded", String(isOpen));
    if (isOpen) $(".search-launch").focus();
  });
  $("#sidebar-scrim").addEventListener("click", closeMenu);
  const mobileQuery = window.matchMedia("(max-width:760px)");
  mobileQuery.addEventListener("change", () => { $("#sidebar").inert = mobileQuery.matches && !$("#sidebar").classList.contains("open"); });
  $("#sidebar").inert = mobileQuery.matches;
  $("#focus-toggle").addEventListener("click", () => {
    const enabled = document.body.classList.toggle("focus-mode");
    $("#focus-toggle").setAttribute("aria-pressed", String(enabled));
    $("#focus-toggle").textContent = enabled ? "Hiện mục lục" : "Chế độ tập trung";
  });

  function renderHome() {
    renderNav(); setBreadcrumb("Không gian học tập");
    document.title = "Hiểu project từ đầu · BB84 Lab";
    const last = course.lessons.find(l => l.id === state.lastLesson) || course.lessons[0];
    const done = new Set(state.completed);
    main.innerHTML = `<div class="home-wrap"><section class="home-intro"><div><h1>Hiểu project,<br>từng bước một.</h1><p class="lead">Bắt đầu từ một lời nhắn của Alice. Theo nó qua từng bước tạo khóa, mã hóa và truyền đến Bob, rồi mở đúng đoạn code để xem chuyện gì đang xảy ra.</p><div class="actions"><a class="button primary" href="#/lesson/${done.size || state.lastLesson !== "big-picture" ? last.id : "big-picture"}">${done.size || state.lastLesson !== "big-picture" ? "Tiếp tục bài đang đọc" : "Bắt đầu từ bức tranh lớn"}</a><a class="button" href="#/map">Xem bản đồ project</a></div><div class="home-meta"><span>14 bài theo thứ tự</span><span>Ví dụ tương tác</span><span>Code thật trong repo</span></div></div><aside class="welcome-note"><h2>Chưa biết lượng tử? Vẫn học được.</h2><p>Mỗi khái niệm đều có ví dụ nhỏ. Chưa cần hiểu cả project cùng lúc; chỉ cần giải thích được bước đang đứng.</p></aside></section><section data-widget="journey" aria-label="Luồng một lời nhắn qua project"></section><section aria-labelledby="roadmap-title"><div class="section-heading"><div><h2 id="roadmap-title">Học theo lộ trình này</h2><p class="small-text">Đọc ý chính, thử ví dụ, rồi tự trả lời trước khi sang bài tiếp.</p></div></div>${course.groups.map((group, index) => `<div class="course-phase"><div class="phase-heading"><span class="phase-number">Chặng ${index + 1}</span><h3>${esc(group.title)}</h3><p>${esc(group.description)}</p></div><div>${course.lessons.filter(l => l.group === group.id).map(l => `<a class="lesson-row" href="#/lesson/${l.id}"><span class="row-number ${done.has(l.id) ? "done" : ""}">${done.has(l.id) ? "✓" : course.lessons.indexOf(l) + 1}</span><span><span class="row-title">${esc(l.title)}</span><span class="row-summary">${esc(l.summary)}</span></span><span class="row-time">${l.minutes} phút</span></a>`).join("")}</div></div>`).join("")}</section><div class="tool-links"><a class="tool-link" href="#/map"><strong>Bản đồ project</strong><p>Chưa biết mở file nào? Chọn một module để xem vai trò, đầu vào và đầu ra.</p></a><a class="tool-link" href="#/code"><strong>Đọc code có chỉ dẫn</strong><p>Xem mã nguồn hiện tại, chọn hàm và đối chiếu với từng bài học.</p></a><a class="tool-link" href="#/glossary"><strong>Từ điển dễ hiểu</strong><p>Tra QBER, PSK, nonce, Toeplitz… bằng lời giải thích ngắn.</p></a></div><p class="scope-note"><strong>Học đúng phạm vi:</strong> đây là mô phỏng BB84/E91 trên máy cổ điển. Các ví dụ giúp hiểu triển khai; không chứng minh QKD vật lý hay bảo vệ dữ liệu thật. Tiến độ và ghi chú chỉ lưu trên trình duyệt này.</p><div class="reset-section"><button class="text-button" id="reset-progress">Đặt lại bài đã học và câu trả lời</button><p>Giữ nguyên ghi chú riêng của bạn. Thao tác này cần xác nhận.</p></div></div>`;
    $(".home-meta > span", main).textContent = `${course.lessons.length} bài theo thứ tự`;
    $(".home-intro", main).insertAdjacentHTML("afterend", `<nav class="learning-additions" aria-label="Học đọc hình và thuật ngữ"><a href="#/lesson/graphs"><strong>Đọc hiểu đồ thị của project</strong><span>Trục, SD, CI 95% và diễn giải trên dữ liệu thật.</span></a><a href="#/abbreviations"><strong>Từ viết tắt &amp; ký hiệu</strong><span>${course.abbreviations.length} mục có tên đầy đủ, nghĩa tiếng Việt và ví dụ.</span></a></nav>`);
    $("#reset-progress").addEventListener("click", () => {
      if (window.confirm("Đặt lại dấu đã học và các câu trả lời? Ghi chú của bạn vẫn được giữ.")) {
        state.completed = []; state.answers = {}; state.lastLesson = "big-picture"; persist(); renderHome(); toast("Đã đặt lại tiến độ; ghi chú vẫn được giữ.");
      }
    });
    mountWidgets(main);
  }

  let tocObserver;
  function quizHtml(lesson, index) {
    const quiz = lesson.quizzes[index];
    const saved = state.answers[lesson.id];
    const selected = Array.isArray(saved) && Number.isInteger(saved[index]) ? saved[index] : undefined;
    const answered = selected !== undefined && selected >= 0 && selected < quiz.choices.length;
    return `<fieldset class="quiz-question" data-quiz="${index}"><legend>${index + 1}. ${esc(quiz.question)}</legend>${quiz.choices.map((choice, n) => `<button type="button" class="quiz-option ${answered && selected === n ? (n === quiz.answer ? "correct" : "incorrect") : ""}" data-answer="${n}" aria-pressed="${selected === n}"><span class="choice-letter" aria-hidden="true">${String.fromCharCode(65 + n)}</span><span>${choice}</span></button>`).join("")}<div class="quiz-feedback ${answered ? selected === quiz.answer ? "good" : "retry" : ""}" role="status" ${answered ? "" : "hidden"}>${answered ? `<strong>${selected === quiz.answer ? "Đúng rồi." : "Chưa đúng, thử lại nhé."}</strong> ${esc(quiz.explanation)}` : ""}</div></fieldset>`;
  }
  function correctCount(lesson) {
    const answers = state.answers[lesson.id];
    return lesson.quizzes.filter((q, i) => Array.isArray(answers) && answers[i] === q.answer).length;
  }
  function renderLesson(id) {
    const lesson = course.lessons.find(l => l.id === id);
    if (!lesson) return renderNotFound();
    const index = course.lessons.indexOf(lesson), group = course.groups.find(g => g.id === lesson.group);
    state.lastLesson = id; persist();
    renderNav(id); setBreadcrumb(`Bài ${index + 1}`, group.short);
    document.title = `${lesson.title} · Hiểu project`;
    const complete = state.completed.includes(id);
    main.innerHTML = `<div class="lesson-layout"><article class="lesson-main"><header class="lesson-header"><div class="lesson-meta"><span class="lesson-number">Bài ${index + 1} / ${course.lessons.length}</span><span>${esc(group.short)}</span><span>Khoảng ${lesson.minutes} phút</span></div><h1>${esc(lesson.title)}</h1><p class="lesson-summary">${esc(lesson.summary)}</p><div class="goals"><h2>Sau bài này, bạn sẽ làm được</h2><ul>${lesson.goals.map(goal => `<li>${esc(goal)}</li>`).join("")}</ul></div></header>${lesson.sections.map(s => `<section class="lesson-section" id="section-${s.id}" aria-labelledby="heading-${s.id}"><h2 id="heading-${s.id}">${esc(s.title)}</h2>${s.body}</section>`).join("")}<section class="quiz-section" id="section-quiz" aria-labelledby="quiz-title"><div class="quiz-heading"><h2 id="quiz-title">Bạn đã hiểu đến đâu?</h2><span class="quiz-count" id="quiz-count">${correctCount(lesson)}/${lesson.quizzes.length} câu đúng</span></div><p class="muted small-text">Chọn câu trả lời để xem giải thích. Bạn có thể thử lại.</p><div id="quizzes">${lesson.quizzes.map((_, i) => quizHtml(lesson, i)).join("")}</div></section><section class="task-block" id="section-notes"><h2>Thử tự làm</h2><p>${esc(lesson.task)}</p><label class="notes-label" for="lesson-notes">Ghi chú bằng lời của bạn</label><textarea class="notes-input" id="lesson-notes" maxlength="20000" placeholder="Mình đã hiểu… / Mình còn thắc mắc…" rows="5">${esc(typeof state.notes[id] === "string" ? state.notes[id] : "")}</textarea><p class="notes-status" id="notes-status">${storageAvailable ? "Chỉ lưu trên trình duyệt này, không gửi lên server." : "Trình duyệt đang chặn lưu dữ liệu. Ghi chú chỉ giữ trong lần mở trang này."}</p></section><div class="lesson-bottom"><div class="actions"><button class="button ${complete ? "success" : "primary"}" id="complete-lesson" aria-pressed="${complete}">${complete ? "✓ Đã học bài này" : "Đánh dấu đã học bài này"}</button><button class="text-button" id="print-lesson">In / lưu bài thành PDF</button></div><p class="complete-note">Đánh dấu khi bạn tự giải thích được ý chính. Bạn có thể bỏ đánh dấu để học lại.</p><nav class="lesson-bottom-nav" aria-label="Bài liền trước và tiếp theo">${index > 0 ? `<a href="#/lesson/${course.lessons[index - 1].id}"><small>Bài trước</small>${esc(course.lessons[index - 1].title)}</a>` : `<a href="#/"><small>Quay về</small>Lộ trình của bạn</a>`}${index < course.lessons.length - 1 ? `<a href="#/lesson/${course.lessons[index + 1].id}"><small>Bài tiếp theo</small>${esc(course.lessons[index + 1].title)}</a>` : `<a href="#/"><small>Xem lại</small>Toàn bộ lộ trình</a>`}</nav></div></article><aside class="lesson-toc" aria-label="Mục lục trong bài"><p>Trong bài này</p>${lesson.sections.map(s => `<a class="toc-link" href="#/lesson/${id}?section=${s.id}" data-toc="${s.id}">${esc(s.title)}</a>`).join("")}<a class="toc-link" href="#/lesson/${id}?section=quiz" data-toc="quiz">Tự kiểm tra</a><a class="toc-link" href="#/lesson/${id}?section=notes" data-toc="notes">Ghi chú của bạn</a><div class="toc-help"><p>Đang vướng một thuật ngữ?</p><a href="#/glossary">Mở từ điển dễ hiểu</a><a href="#/map">Xem bản đồ project</a><button class="text-button" data-search-open>Tìm nhanh trong bài học</button></div></aside></div>`;
    $("#quizzes").addEventListener("click", event => {
      const button = event.target.closest("[data-answer]"); if (!button) return;
      const field = button.closest("[data-quiz]"), q = Number(field.dataset.quiz), answer = Number(button.dataset.answer);
      if (!Array.isArray(state.answers[id])) state.answers[id] = [];
      state.answers[id][q] = answer; persist();
      const focusedChoice = answer;
      field.outerHTML = quizHtml(lesson, q);
      $(`[data-quiz="${q}"] [data-answer="${focusedChoice}"]`).focus({preventScroll: true});
      $("#quiz-count").textContent = `${correctCount(lesson)}/${lesson.quizzes.length} câu đúng`;
    });
    $("#lesson-notes").addEventListener("input", event => {
      state.notes[id] = event.target.value;
      const ok = persist();
      $("#notes-status").textContent = ok ? "Đã lưu trên trình duyệt này. Không gửi lên server." : "Chưa lưu được vào trình duyệt. Hãy sao chép ghi chú trước khi đóng trang.";
    });
    $("#complete-lesson").addEventListener("click", event => {
      const wasComplete = state.completed.includes(id);
      state.completed = wasComplete ? state.completed.filter(item => item !== id) : [...state.completed, id];
      const saved = persist();
      event.currentTarget.className = `button ${wasComplete ? "primary" : "success"}`;
      event.currentTarget.textContent = wasComplete ? "Đánh dấu đã học bài này" : "✓ Đã học bài này";
      event.currentTarget.setAttribute("aria-pressed", String(!wasComplete));
      renderNav(id);
      toast(saved ? wasComplete ? "Đã bỏ đánh dấu bài này." : "Đã lưu bài học vào tiến độ của bạn." : "Đã cập nhật trong lần mở này; trình duyệt chưa cho lưu tiến độ.");
    });
    $("#print-lesson").addEventListener("click", () => window.print());
    annotateAbbreviations($(".lesson-main", main));
    mountWidgets(main);
    if ("IntersectionObserver" in window) {
      tocObserver = new IntersectionObserver(entries => {
        for (const entry of entries) if (entry.isIntersecting) {
          $$("[data-toc]").forEach(a => a.classList.toggle("active", `section-${a.dataset.toc}` === entry.target.id));
        }
      }, {rootMargin: "-95px 0px -65% 0px", threshold: 0});
      $$(".lesson-section,.quiz-section,.task-block", main).forEach(s => tocObserver.observe(s));
    }
  }
  function renderMap() {
    renderNav("map"); setBreadcrumb("Bản đồ project", "Tra cứu"); document.title = "Bản đồ project · BB84 Lab";
    main.innerHTML = `<div class="tool-wrap"><header class="tool-header"><h1>Biết mình đang ở đâu trong code.</h1><p>Chọn một vùng để xem nó nhận gì, trả gì và nên đọc file nào. Luồng cục bộ: web → local → simulation → core. Luồng mạng đi từ UI vai trò → network → core; hạ tầng dùng shared.</p></header><div data-widget="architecture"></div><div class="callout"><strong>Đọc theo câu hỏi, không theo số lượng file</strong><p>“Vì sao dừng?” → monitor/postprocess. “File lưu lúc nào?” → receive_transfer. “Nút web gọi gì?” → app.js rồi server.py.</p></div><a class="button primary" href="#/lesson/architecture">Học bài kiến trúc từng bước</a></div>`;
    mountWidgets(main);
  }
  function renderGlossary() {
    renderNav("glossary"); setBreadcrumb("Từ điển dễ hiểu", "Tra cứu"); document.title = "Từ điển dễ hiểu · BB84 Lab";
    main.innerHTML = `<div class="tool-wrap"><header class="tool-header"><h1>Gặp từ lạ, tra ở đây.</h1><p>${course.glossary.length} thuật ngữ theo đúng cách dùng trong project. Có thể tìm không dấu hoặc theo một từ trong lời giải thích.</p></header><div class="glossary-filter"><label class="sr-only" for="glossary-query">Tìm thuật ngữ</label><input id="glossary-query" type="search" placeholder="Ví dụ: khoa, co so, QBER, PSK…" autocomplete="off"></div><p id="glossary-count" class="muted small-text" role="status"></p><div id="glossary-list" class="glossary-list"></div></div>`;
    const draw = () => {
      const query = normalize($("#glossary-query").value).trim();
      const items = course.glossary.filter(g => normalize(`${g.term} ${g.definition}`).includes(query));
      $("#glossary-count").textContent = `${items.length} thuật ngữ`;
      $("#glossary-list").innerHTML = items.length ? items.map(item => `<article class="glossary-entry"><h2>${esc(item.term)}</h2><p>${esc(item.definition)}</p><a href="#/lesson/${item.lesson}">Học trong bài liên quan</a></article>`).join("") : '<p class="empty-state">Chưa có từ khớp. Thử một phần tên như “key”, “bit” hoặc “mẫu”.</p>';
    };
    $("#glossary-query").addEventListener("input", draw); draw();
  }
  const abbreviationGroups = {protocol: "Giao thức & lượng tử", statistics: "Thống kê", crypto: "Mật mã", implementation: "Thuật toán", software: "Phần mềm", network: "Mạng", format: "Định dạng", performance: "Hiệu năng", units: "Đơn vị", symbols: "Ký hiệu"};
  function abbreviationBody(item) {
    return `<p class="abbreviation-full" lang="en">${esc(item.full || item.symbol)}</p><p><strong>${esc(item.meaning)}</strong></p><dl class="term-explanation"><dt>Cách dùng trong project</dt><dd>${esc(item.usage)}</dd>${item.example ? `<dt>Ví dụ / lưu ý</dt><dd>${esc(item.example)}</dd>` : ""}</dl><a href="#/lesson/${esc(item.lesson)}">Đọc bài liên quan</a>`;
  }
  function openAbbreviation(short) {
    const item = course.abbreviations.find(a => a.short === short);
    if (!item) return;
    $("#abbreviation-title").textContent = item.short;
    $("#abbreviation-detail").innerHTML = abbreviationBody(item) + `<p class="abbreviation-reference"><a href="#/abbreviations?term=${encodeURIComponent(item.short)}">Mở trong bảng tra cứu</a></p>`;
    const dialog = $("#abbreviation-dialog");
    if (!dialog.open) dialog.showModal();
  }
  function annotateAbbreviations(root) {
    const names = course.abbreviations.map(a => a.short).sort((a, b) => b.length - a.length);
    const pattern = new RegExp(`(?<![\\p{L}\\p{N}_])(${names.map(name => name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})(?![\\p{L}\\p{N}_])`, "gu");
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode(node) {
      return node.parentElement.closest("a,button,input,textarea,select,pre,code,abbr,svg,h1,h2,h3,h4,[data-widget],.quiz-section,.task-block,.lesson-bottom,.lesson-pagination") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    }});
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const matches = [...node.textContent.matchAll(pattern)];
      if (!matches.length) continue;
      const fragment = document.createDocumentFragment(); let last = 0;
      for (const match of matches) {
        fragment.append(node.textContent.slice(last, match.index));
        const button = document.createElement("button");
        const item = course.abbreviations.find(a => a.short === match[0]);
        button.type = "button"; button.className = "abbreviation-inline";
        button.dataset.abbreviation = item.short; button.textContent = item.short;
        button.title = `${item.full}: ${item.meaning}`;
        button.setAttribute("aria-label", `Giải nghĩa ${item.short}: ${item.meaning}`);
        button.setAttribute("aria-haspopup", "dialog");
        fragment.append(button); last = match.index + match[0].length;
      }
      fragment.append(node.textContent.slice(last)); node.replaceWith(fragment);
    }
  }
  function renderAbbreviations(params) {
    renderNav("abbreviations"); setBreadcrumb("Từ viết tắt & ký hiệu", "Tra cứu");
    document.title = "Từ viết tắt & ký hiệu · BB84 Lab";
    main.innerHTML = `<div class="tool-wrap"><header class="tool-header"><h1>Đọc tên đầy đủ, hiểu đúng cách dùng.</h1><p>${course.abbreviations.length} từ viết tắt và ${course.symbols.length} ký hiệu trong project. Tìm theo tên tiếng Anh, nghĩa tiếng Việt hoặc ví dụ; có thể gõ không dấu.</p></header><div class="reference-filters"><div class="field"><label for="abbreviation-query">Tìm từ viết tắt hoặc ký hiệu</label><input id="abbreviation-query" type="search" placeholder="Ví dụ: QBER, khoang tin cay, Y_pre…" autocomplete="off"></div><div class="field"><label for="abbreviation-group">Nhóm nội dung</label><select id="abbreviation-group"><option value="">Tất cả nhóm</option>${Object.entries(abbreviationGroups).map(([id, label]) => `<option value="${id}">${esc(label)}</option>`).join("")}</select></div></div><p id="abbreviation-count" class="small-text muted" role="status"></p><div id="abbreviation-list" class="reference-list"></div></div>`;
    const queryInput = $("#abbreviation-query"), groupInput = $("#abbreviation-group");
    queryInput.value = params.get("term") || params.get("q") || "";
    const entries = [...course.abbreviations, ...course.symbols.map(s => ({...s, short: s.symbol, group: "symbols"}))];
    const draw = () => {
      const words = normalize(queryInput.value).trim().split(/\s+/).filter(Boolean);
      const entriesFound = entries.filter(item => (!groupInput.value || item.group === groupInput.value) && words.every(word => normalize([item.short, item.full, item.meaning, item.usage, item.example].filter(Boolean).join(" ")).includes(word)));
      $("#abbreviation-count").textContent = `${entriesFound.length} / ${entries.length} mục`;
      $("#abbreviation-list").innerHTML = entriesFound.length ? entriesFound.map(item => `<article class="reference-entry"><header><h2>${esc(item.short)}</h2><span class="tag">${esc(abbreviationGroups[item.group])}</span></header>${abbreviationBody(item)}</article>`).join("") : '<p class="empty-state">Chưa có mục khớp. Thử tên ngắn như “CI”, nghĩa như “bộ nhớ”, hoặc chọn tất cả nhóm.</p>';
    };
    queryInput.addEventListener("input", draw); groupInput.addEventListener("change", draw); draw();
  }
  function highlightedLine(text) {
    const regex = /("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#[^\n]*|\b(?:async|await|def|class|return|if|elif|else|for|while|in|not|and|or|is|None|True|False|from|import|as|with|try|except|finally|raise|yield|lambda|nonlocal|break|continue|assert|const|let|function|new|throw)\b|\b\d+(?:\.\d+)?\b)/g;
    let result = "", last = 0;
    for (const match of text.matchAll(regex)) {
      result += esc(text.slice(last, match.index));
      const token = match[0];
      const style = token.startsWith("#") ? "comment" : /^["']/.test(token) ? "string" : /^\d/.test(token) ? "number" : "keyword";
      result += `<span class="tok-${style}">${esc(token)}</span>`; last = match.index + token.length;
    }
    return result + esc(text.slice(last));
  }
  async function renderCode(path = "bb84_lab/core/bb84.py", symbol = "") {
    renderNav("code"); setBreadcrumb("Đọc code có chỉ dẫn", "Tra cứu"); document.title = "Đọc code có chỉ dẫn · BB84 Lab";
    main.innerHTML = `<div class="tool-wrap"><header class="tool-header"><h1>Từ lời giải thích đến code thật.</h1><p>Mã nguồn đọc trực tiếp từ checkout hiện tại qua danh sách cho phép. Chọn file, rồi chọn hàm; vùng xanh là nơi bạn cần nhìn trước. Chỉ xem, không sửa file tại đây.</p></header><div class="code-layout"><aside class="code-sidebar" aria-label="Tệp mã nguồn"><label class="sr-only" for="code-filter">Lọc tên file hoặc chức năng</label><input id="code-filter" class="code-filter" type="search" placeholder="Tìm file / chức năng…"><nav class="code-files" id="code-files" aria-label="Danh sách file"><p class="small-text muted">Đang đọc danh sách…</p></nav><p class="source-hint">Mẹo đọc hàm:<br>Đầu vào → kiểm tra → tính toán → đầu ra → nhánh dừng.</p></aside><section class="code-panel" id="code-panel" aria-label="Nội dung mã nguồn"><div class="source-loader" role="status">Đang đọc mã nguồn…</div></section></div></div>`;
    const panel = $("#code-panel"), files = $("#code-files"), filter = $("#code-filter");
    try {
      const catalog = await getCatalog(); if (!panel.isConnected) return;
      const drawFiles = () => {
        const query = normalize(filter.value), groups = [...new Set(catalog.map(c => c.group))];
        const filtered = catalog.filter(c => normalize(`${c.path} ${c.description}`).includes(query));
        files.innerHTML = filtered.length ? groups.map(group => {
          const list = filtered.filter(c => c.group === group); if (!list.length) return "";
          return `<p class="code-group">${esc(group)}</p>${list.map(item => `<a class="code-file ${item.path === path ? "active" : ""}" href="${esc(sourceHref(item.path))}" title="${esc(item.description)}" ${item.path === path ? 'aria-current="page"' : ""}>${esc(item.path.replace(/^bb84_lab\//, ""))}</a>`).join("")}`;
        }).join("") : '<p class="small-text muted">Không có file khớp.</p>';
      };
      filter.addEventListener("input", drawFiles); drawFiles();
      if (!catalog.some(c => c.path === path)) { panel.innerHTML = errorBox("Tệp này không nằm trong danh sách mã nguồn học tập. Chọn một tệp ở danh sách bên cạnh."); return; }
      const data = await getSource(path); if (!panel.isConnected) return;
      const target = data.symbols.find(s => s.name === symbol);
      panel.innerHTML = `<header class="code-panel-head"><h2>${esc(data.path)}</h2><p>${esc(data.description)}</p></header><div class="code-toolbar"><label for="symbol-select">Đi đến hàm</label><select id="symbol-select"><option value="">Toàn bộ file (${data.line_count} dòng)</option>${data.symbols.map(s => `<option value="${esc(s.name)}" ${s.name === symbol ? "selected" : ""}>${esc(s.name)} · dòng ${s.start}–${s.end}</option>`).join("")}</select><button class="text-button" id="copy-source">Sao chép code</button></div>${symbol && !target ? '<p class="source-symbol-note">Tên hàm trong liên kết không còn tồn tại; đang hiển thị file hiện tại. Chọn lại hàm trong danh sách.</p>' : target ? `<p class="source-symbol-note">Đang xem <strong>${esc(target.name)}</strong>, dòng ${target.start}–${target.end}. Các dòng bên ngoài được giữ để bạn thấy ngữ cảnh.</p>` : '<p class="source-symbol-note">Chọn hàm để đánh dấu đúng vùng triển khai. Cuộn ngang nếu một dòng dài.</p>'}<pre class="source-code" id="source-code" tabindex="0" aria-label="Mã nguồn có số dòng"><code>${data.text.replace(/\n$/, "").split("\n").map((line, index) => `<span class="code-line ${target && index + 1 >= target.start && index + 1 <= target.end ? "target" : ""}" id="code-line-${index + 1}"><span class="line-number" aria-hidden="true">${index + 1}</span><span class="line-content">${highlightedLine(line.replace(/\r$/, "")) || " "}</span></span>`).join("")}</code></pre><footer class="source-foot"><strong>Nguồn: file đang có trên máy bạn.</strong> ${num(data.line_count)} dòng. SHA-256 dùng đối chiếu nội dung:<br>${esc(data.sha256)}<br>Nếu vừa sửa file ở editor, tải lại trang để đọc bản mới. Trang học không đọc PSK, tệp nhận hoặc outputs.</footer>`;
      $("#symbol-select").addEventListener("change", event => { location.hash = sourceHref(path, event.target.value); });
      $("#copy-source").addEventListener("click", () => copyText(data.text));
      if (target) {
        const pre = $("#source-code"), targetLine = $(`#code-line-${target.start}`);
        pre.scrollTop = targetLine.offsetTop - pre.offsetTop - 50;
      }
    } catch (error) {
      if (panel.isConnected) { panel.innerHTML = errorBox(error.message); files.innerHTML = '<p class="small-text muted">Danh sách nguồn chưa sẵn sàng. Kiểm tra server rồi tải lại trang.</p>'; }
    }
  }
  function renderNotFound() {
    renderNav(); setBreadcrumb("Không tìm thấy trang");
    main.innerHTML = '<div class="tool-wrap"><header class="tool-header"><h1>Chưa tìm thấy bài này.</h1><p>Liên kết có thể đã bị đổi. Quay lại lộ trình để chọn bài, hoặc dùng tìm kiếm.</p></header><a class="button primary" href="#/">Về lộ trình học</a></div>';
  }

  function journeyWidget(root) {
    root.innerHTML = `<div class="journey-board"><div class="journey-heading"><div><h2>Một lời nhắn đi qua project thế nào?</h2><p>Bấm từng bước để nối ý tưởng với hàm triển khai.</p></div><div class="message-slip"><span aria-hidden="true">▤</span> “Xin chào Bob”</div></div><div class="journey-stops" role="group" aria-label="Chọn bước của luồng dữ liệu">${course.journey.map((step, i) => `<button type="button" class="journey-stop" data-step="${i}" aria-pressed="${i === 0}"><span class="stop-number" aria-hidden="true">${i + 1}</span><span>${esc(step.title)}</span></button>`).join("")}</div><div class="journey-detail" aria-live="polite"></div></div>`;
    const draw = index => {
      const step = course.journey[index];
      $$(".journey-stop", root).forEach((button, i) => { button.classList.toggle("active", i === index); button.setAttribute("aria-pressed", String(i === index)); });
      $(".journey-detail", root).innerHTML = `<div><h3>${index + 1}. ${esc(step.title)}</h3><p>${esc(step.plain)}</p></div><div class="journey-output"><span>Kết quả ở bước này</span><strong>${esc(step.output)}</strong>${sourceLink(step.file, step.symbol)}</div>`;
    };
    root.addEventListener("click", event => { const button = event.target.closest("[data-step]"); if (button) draw(Number(button.dataset.step)); }); draw(0);
  }
  function architectureWidget(root) {
    root.innerHTML = `<div class="module-map" role="group" aria-label="Chọn module">${course.modules.map((mod, index) => `<button type="button" class="module-node ${mod.color}" data-module="${index}" aria-pressed="${index === 0}"><strong>${esc(mod.name)}</strong><span>${esc(mod.role)}</span></button>`).join("")}</div><section class="module-detail" aria-live="polite"></section>`;
    const draw = index => {
      const mod = course.modules[index];
      $$("[data-module]", root).forEach((b, i) => b.setAttribute("aria-pressed", String(i === index)));
      $(".module-detail", root).innerHTML = `<h3>${esc(mod.name)} ${esc(mod.role)}</h3><p>${esc(mod.description)}</p><div class="module-io"><div><strong>Nhận vào</strong>${esc(mod.receives)}</div><div><strong>Trả ra</strong>${esc(mod.returns)}</div></div><div class="module-files">${mod.files.map(file => sourceLink(file)).join("")}</div><a class="button small" href="#/lesson/${mod.lesson}">Học phần này theo từng bước</a>`;
    };
    root.addEventListener("click", event => { const b = event.target.closest("[data-module]"); if (b) draw(Number(b.dataset.module)); }); draw(0);
  }
  function basisWidget(root) {
    root.innerHTML = `<header class="widget-header"><h3>Thử đổi bit và cơ sở</h3><p>Xác suất lý thuyết của mô hình sạch, không Eve, không nhiễu.</p></header><div class="widget-body"><div class="widget-controls"><div class="field"><label for="basis-bit">Bit Alice</label><select id="basis-bit"><option value="0">0</option><option value="1">1</option></select></div><div class="field"><label for="basis-alice">Cơ sở Alice</label><select id="basis-alice"><option value="0">Z</option><option value="1">X</option></select></div><div class="field"><label for="basis-bob">Cơ sở Bob</label><select id="basis-bob"><option value="0">Z</option><option value="1">X</option></select></div></div><div class="basis-output" aria-live="polite"></div></div>`;
    const draw = () => {
      const bit = Number($("#basis-bit", root).value), a = Number($("#basis-alice", root).value), b = Number($("#basis-bob", root).value), match = a === b;
      const probOne = match ? bit : .5, states = [["|0⟩", "|1⟩"], ["|+⟩", "|−⟩"]];
      $(".basis-output", root).innerHTML = `<span class="tag">Alice chuẩn bị ${states[a][bit]}</span><div class="probability-pair">${[1 - probOne, probOne].map((p, i) => `<div class="probability"><span>Bob đo được bit ${i}</span><strong>${pct(p)}</strong><progress max="1" value="${p}" aria-label="Xác suất Bob nhận ${i}"></progress></div>`).join("")}</div><div class="widget-result"><p><strong>${match ? "Cùng cơ sở: giữ khi sàng lọc." : "Khác cơ sở: loại khi sàng lọc."}</strong> ${match ? "Trong mô hình sạch, Bob nhận lại đúng bit Alice đã chuẩn bị." : "Một kết quả ngẫu nhiên vẫn có thể tình cờ trùng bit; điều đó không thay đổi quy tắc loại theo cơ sở."}</p></div>`;
    };
    root.addEventListener("change", draw); draw();
  }
  function wilson(errors, total) {
    if (!total) return [null, null];
    const z = 1.959963984540054, q = errors / total, denominator = 1 + z * z / total;
    const center = (q + z * z / (2 * total)) / denominator;
    const radius = z * Math.sqrt(q * (1 - q) / total + z * z / (4 * total * total)) / denominator;
    return [Math.max(0, center - radius), Math.min(1, center + radius)];
  }
  function intervalChart(low, high, observed, threshold) {
    if (low == null) return "";
    const max = Math.min(1, Math.max(.1, high * 1.16, threshold * 1.35));
    const x = value => 28 + value / max * 504;
    return `<svg class="interval-chart" viewBox="0 0 560 116" role="img" aria-label="Khoảng Wilson từ ${esc(pct(low))} đến ${esc(pct(high))}, QBER ${esc(pct(observed))}, ngưỡng ${esc(pct(threshold))}"><line x1="28" x2="532" y1="73" y2="73" stroke="#c9d5e6"/><line class="chart-threshold" x1="${x(threshold)}" x2="${x(threshold)}" y1="22" y2="78"/><text x="${x(threshold)}" y="14" text-anchor="middle">Ngưỡng ${esc(pct(threshold))}</text><line x1="${x(low)}" x2="${x(high)}" y1="48" y2="48" stroke="#2859a7" stroke-width="7" stroke-linecap="round"/><circle cx="${x(observed)}" cy="48" r="6" fill="#16756b" stroke="#fff" stroke-width="2"/>${[0, .25, .5, .75, 1].map(r => `<line x1="${x(max * r)}" x2="${x(max * r)}" y1="73" y2="78" stroke="#aebfd5"/><text x="${x(max * r)}" y="98" text-anchor="middle">${pct(max * r)}</text>`).join("")}</svg>`;
  }
  const pill = (text, kind = "") => `<span class="status-pill ${kind}">${esc(text)}</span>`;
  const statusKind = status => status === "continue" || status === "ready" || status === "violation" ? "good" : ["inconclusive", "insufficient_key", "chsh_inconclusive"].includes(status) ? "warn" : "bad";
  const metric = (label, value, caption = "") => `<div class="data-metric"><span>${esc(label)}</span><strong>${esc(value)}</strong>${caption ? `<small>${esc(caption)}</small>` : ""}</div>`;
  function wilsonWidget(root) {
    root.innerHTML = `<header class="widget-header"><h3>Tự thay số vào quy tắc monitor</h3><p>Bộ tính chạy trong trình duyệt với cùng công thức trong core/bb84.py. Không phải kết quả phiên mô phỏng.</p></header><div class="widget-body"><div class="widget-controls"><div class="field"><label for="wilson-total">Số bit mẫu</label><input id="wilson-total" type="number" min="0" max="1000000" value="100" step="1"></div><div class="field"><label for="wilson-errors">Số lỗi</label><input id="wilson-errors" type="number" min="0" max="100" value="0" step="1"></div><div class="field"><label for="wilson-threshold">Ngưỡng</label><select id="wilson-threshold"><option value="0.03">3%</option><option value="0.05" selected>5%</option><option value="0.08">8%</option></select></div></div><div class="actions"><button class="button small secondary" data-wilson-preset="10">0 / 10</button><button class="button small secondary" data-wilson-preset="100">0 / 100</button><button class="button small secondary" data-wilson-preset="1000">0 / 1.000</button></div><div class="wilson-output" aria-live="polite"></div></div>`;
    const draw = () => {
      const total = Number($("#wilson-total", root).value), errors = Number($("#wilson-errors", root).value), threshold = Number($("#wilson-threshold", root).value), output = $(".wilson-output", root);
      $("#wilson-errors", root).max = total;
      if (!Number.isInteger(total) || !Number.isInteger(errors) || total < 0 || total > 1000000 || errors < 0 || errors > total || $("#wilson-total", root).value === "" || $("#wilson-errors", root).value === "") { output.innerHTML = errorBox("Nhập số nguyên: 0 ≤ số lỗi ≤ số mẫu ≤ 1.000.000."); return; }
      const [low, high] = wilson(errors, total), observed = total ? errors / total : null;
      let status, reason;
      if (total < 100) { status = "inconclusive"; reason = "Chưa đủ 100 mẫu tối thiểu, dù có thể chưa quan sát thấy lỗi."; }
      else if (high <= threshold) { status = "continue"; reason = "Cận trên không vượt ngưỡng. Cho phép hậu xử lý tiếp; chưa phát hành khóa."; }
      else if (low > threshold) { status = "anomalous"; reason = "Cận dưới vượt ngưỡng. Dừng vì kênh bất thường."; }
      else { status = "inconclusive"; reason = "Khoảng Wilson còn cắt ngưỡng. Dừng vì chưa đủ bằng chứng."; }
      output.innerHTML = `<div class="data-metrics">${metric("QBER quan sát", pct(observed))}${metric("Cận dưới 95%", pct(low))}${metric("Cận trên 95%", pct(high))}</div>${intervalChart(low, high, observed, threshold)}<div class="status-line">${pill(status, statusKind(status))}<span>Tối thiểu 100 mẫu</span></div><div class="widget-result"><p>${esc(reason)}</p></div>`;
    };
    root.addEventListener("input", draw); root.addEventListener("change", draw);
    root.addEventListener("click", event => { const b = event.target.closest("[data-wilson-preset]"); if (b) { $("#wilson-total", root).value = b.dataset.wilsonPreset; $("#wilson-errors", root).value = "0"; draw(); } }); draw();
  }
  function parityWidget(root) {
    const alice = [1, 0, 1, 1, 0, 1, 0, 0], bob = [...alice];
    root.innerHTML = `<header class="widget-header"><h3>Lật bit của Bob, quan sát parity</h3><p>Đây là phép kiểm tra một khối, không phải toàn bộ Cascade. Hai lỗi có thể che nhau.</p></header><div class="widget-body"><div class="bit-label"><span>Alice</span><strong class="alice-parity"></strong></div><div class="bit-strip">${alice.map(bit => `<span class="bit-static">${bit}</span>`).join("")}</div><div class="bit-label"><span>Bob · bấm một bit để lật</span><strong class="bob-parity"></strong></div><div class="bit-strip">${bob.map((bit, i) => `<button class="bit-button" data-parity-bit="${i}" aria-label="Lật bit Bob vị trí ${i + 1}" aria-pressed="false">${bit}</button>`).join("")}</div><button class="button small" data-parity-reset>Đưa về chuỗi giống nhau</button><div class="parity-result widget-result" aria-live="polite"></div></div>`;
    const draw = () => {
      const pa = alice.reduce((a, b) => a ^ b, 0), pb = bob.reduce((a, b) => a ^ b, 0), errors = bob.filter((v, i) => v !== alice[i]).length;
      $(".alice-parity", root).textContent = `Parity = ${pa}`; $(".bob-parity", root).textContent = `Parity = ${pb}`;
      $$("[data-parity-bit]", root).forEach((button, i) => { button.textContent = bob[i]; button.classList.toggle("flipped", bob[i] !== alice[i]); button.setAttribute("aria-pressed", String(bob[i] !== alice[i])); });
      $(".parity-result", root).innerHTML = `<p><strong>${errors} vị trí đang khác nhau.</strong> ${pa !== pb ? "Parity khác: có số lỗi lẻ, có thể khoanh vùng bằng cách chia đôi khối." : errors ? "Parity trùng nhưng chuỗi vẫn sai: số lỗi chẵn không bị phép kiểm tra một khối này phát hiện." : "Hai chuỗi hiện giống nhau. Hãy lật một bit rồi lật thêm bit thứ hai."}</p>`;
    };
    root.addEventListener("click", event => { const bit = event.target.closest("[data-parity-bit]"); if (bit) { bob[Number(bit.dataset.parityBit)] ^= 1; draw(); } if (event.target.closest("[data-parity-reset]")) { bob.splice(0, bob.length, ...alice); draw(); } }); draw();
  }
  function toeplitzWidget(root) {
    let bits = [1, 1, 0, 1], seed = [1, 0, 1, 1, 0, 1], row = 0;
    root.innerHTML = `<header class="widget-header"><h3>Tự nhân Toeplitz 3 × 4</h3><p>Ví dụ bit công khai cố định, chỉ để tập tính. Không tạo khóa mã hóa.</p></header><div class="widget-body"><span class="bit-label">Đầu vào x · bấm để đổi bit</span><div class="bit-strip input-bits"></div><span class="bit-label">Seed 6 bit · bấm để đổi ma trận</span><div class="bit-strip seed-bits"></div><div class="matrix-layout" aria-label="Ma trận T nhân đầu vào bằng đầu ra"></div><div class="row-selectors" role="group" aria-label="Chọn hàng để giải thích">${[0, 1, 2].map(i => `<button class="button small" data-toeplitz-row="${i}" aria-pressed="${i === 0}">Hàng ${i + 1}</button>`).join("")}</div><div class="toeplitz-detail widget-result" aria-live="polite"></div></div>`;
    const draw = () => {
      $(".input-bits", root).innerHTML = bits.map((b, i) => `<button class="bit-button ${b ? "selected" : ""}" data-input-bit="${i}" aria-label="Đổi bit đầu vào ${i + 1}" aria-pressed="${Boolean(b)}">${b}</button>`).join("");
      $(".seed-bits", root).innerHTML = seed.map((b, i) => `<button class="bit-button ${b ? "selected" : ""}" data-seed-bit="${i}" aria-label="Đổi bit seed ${i + 1}" aria-pressed="${Boolean(b)}">${b}</button>`).join("");
      const matrix = [0, 1, 2].map(i => bits.map((_, j) => seed[bits.length - 1 + i - j]));
      const output = matrix.map(coefficients => coefficients.reduce((acc, c, j) => acc ^ (c & bits[j]), 0));
      $(".matrix-layout", root).innerHTML = `<table class="matrix-table" aria-label="Ma trận Toeplitz"><caption>T (3 hàng × 4 cột)</caption><tbody>${matrix.map((r, i) => `<tr class="${i === row ? "active" : ""}">${r.map((b, j) => `<td class="${b && bits[j] ? "participates" : ""}">${b}</td>`).join("")}</tr>`).join("")}</tbody></table><span class="matrix-operator" aria-hidden="true">×</span><div class="matrix-output" aria-label="Vector đầu vào">${bits.map(b => `<span>${b}</span>`).join("")}</div><span class="matrix-operator" aria-hidden="true">=</span><div class="matrix-output" aria-label="Vector đầu ra">${output.map((b, i) => `<span class="${row === i ? "active" : ""}">${b}</span>`).join("")}</div>`;
      $$("[data-toeplitz-row]", root).forEach((b, i) => b.setAttribute("aria-pressed", String(i === row)));
      const and = matrix[row].map((c, j) => c & bits[j]);
      $(".toeplitz-detail", root).innerHTML = `<p><strong>Hàng ${row + 1}:</strong> (${matrix[row].join(" ")}) AND (${bits.join(" ")}) = (${and.join(" ")}).<br>XOR: ${and.join(" ⊕ ")} = <strong>${output[row]}</strong>.</p>`;
    };
    root.addEventListener("click", event => {
      const input = event.target.closest("[data-input-bit]"), s = event.target.closest("[data-seed-bit]"), r = event.target.closest("[data-toeplitz-row]");
      let selector;
      if (input) { bits[Number(input.dataset.inputBit)] ^= 1; selector = `[data-input-bit="${input.dataset.inputBit}"]`; }
      if (s) { seed[Number(s.dataset.seedBit)] ^= 1; selector = `[data-seed-bit="${s.dataset.seedBit}"]`; }
      if (r) row = Number(r.dataset.toeplitzRow);
      if (input || s || r) { draw(); if (selector) $(selector, root).focus({preventScroll: true}); }
    }); draw();
  }

  function jsonDetails(data) { return `<details class="json-details"><summary>Xem JSON công khai backend trả về</summary><pre><code>${esc(JSON.stringify(data, null, 2))}</code></pre></details>`; }
  function busy(button, label) {
    const old = button.textContent; button.disabled = true; button.textContent = label; return () => { button.disabled = false; button.textContent = old; };
  }
  function bb84Widget(root) {
    root.innerHTML = `<header class="widget-header"><h3>16 tín hiệu, nhìn theo từng bước</h3><p>Gọi /api/lesson của project. Ví dụ công khai riêng, không tạo khóa ứng dụng.</p></header><div class="widget-body"><form class="widget-controls"><div class="field"><label for="bb84-scenario">Kịch bản</label><select id="bb84-scenario"><option value="clean">Kênh sạch</option><option value="eve">Eve chặn toàn bộ</option><option value="noise">Nhiễu 10%</option><option value="weak">Eve chặn 10%</option></select></div><div class="field"><label for="bb84-seed">Seed công khai</label><input id="bb84-seed" type="number" value="2026" min="0" max="2147483647" step="1" required></div><button class="button primary small" type="submit">Tạo ví dụ thật</button></form><div class="bb84-error"></div><div class="bb84-results"><p class="widget-status">Chưa chạy. Bấm tạo ví dụ để lấy 16 dòng từ cùng hàm simulate() của backend.</p></div></div>`;
    let data = null, step = 0;
    const titles = ["Alice chuẩn bị", "Bob đo", "Sàng lọc", "Công khai mẫu", "Bỏ mẫu"];
    const descriptions = ["Bit và cơ sở Alice là hai thông tin khác nhau. Tín hiệu được đánh số từ 1 trên bảng.", "Khác cơ sở có thể trùng bit tình cờ. Nếu có Eve/nhiễu, ngay cả vị trí trùng cơ sở cũng có thể sai bit.", "Chỉ giữ vị trí có cơ sở Alice/Bob trùng nhau. Dòng khác cơ sở được ghi rõ là loại.", "Mẫu chọn từ chuỗi đã sàng lọc; những bit này được công khai để đếm lỗi.", "Loại mọi bit mẫu khỏi phần giữ lại. Ví dụ 16 tín hiệu không tạo khóa ứng dụng."];
    const draw = () => {
      const s = data.summary, names = ["Z", "X"];
      const scenarioName = {clean: "Kênh sạch", eve: "Eve chặn toàn bộ", noise: "Nhiễu 10%", weak: "Eve chặn 10%"}[data.scenario];
      const headers = ["Vị trí", "Bit Alice", "Cơ sở Alice", ...(step >= 1 ? ["Cơ sở Bob", "Bit Bob"] : []), ...(step >= 2 ? ["Sàng lọc"] : []), ...(step >= 3 ? ["Mẫu"] : []), ...(step >= 4 ? ["Giữ lại"] : [])];
      $(".bb84-results", root).innerHTML = `<div class="step-picker" role="group" aria-label="Các bước của bài học">${titles.map((title, i) => `<button class="button small" data-bb84-step="${i}" aria-pressed="${i === step}">${i + 1}. ${title}</button>`).join("")}</div><p class="widget-status" role="status">${descriptions[step]}</p><div class="table-scroll" tabindex="0" role="region" aria-label="16 tín hiệu công khai, có thể cuộn ngang"><table class="bb84-table"><caption>Dữ liệu từ backend · seed nhập ${esc(data.seed)} · ${esc(scenarioName)}</caption><thead><tr>${headers.map(h => `<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${data.signals.map(row => `<tr class="${step >= 2 && !row.sifted ? "dropped" : step >= 3 && row.sampled ? "sampled" : ""}"><td>${row.index + 1}</td><td>${row.alice_bit}</td><td>${names[row.alice_basis]}</td>${step >= 1 ? `<td>${names[row.bob_basis]}</td><td class="${row.error ? "error-bit" : ""}">${row.bob_bit}${row.error ? " ≠" : ""}</td>` : ""}${step >= 2 ? `<td>${row.sifted ? "Giữ" : "Loại"}</td>` : ""}${step >= 3 ? `<td>${row.sampled ? "Công khai" : "—"}</td>` : ""}${step >= 4 ? `<td>${row.retained ? "✓" : "Bỏ"}</td>` : ""}</tr>`).join("")}</tbody></table></div><div class="data-metrics">${metric("Sau sàng lọc", step >= 2 ? `${s.sifted_count} bit` : "Chưa xét")}${metric("Mẫu công khai", step >= 3 ? `${s.sample_count} bit` : "Chưa xét")}${metric("Giữ sau loại mẫu", step >= 4 ? `${s.remaining_count} bit` : "Chưa xét")}</div>${step >= 3 ? `<div class="widget-result"><p>QBER mẫu = ${s.sample_errors}/${s.sample_count} = <strong>${pct(s.qber)}</strong>. Monitor: ${esc(s.status)} (mặc định cần ${s.min_samples} mẫu). Các bit hiển thị không dùng mã hóa.</p></div>` : ""}`;
    };
    $("form", root).addEventListener("submit", async event => {
      event.preventDefault(); const button = $("button[type=submit]", root), finish = busy(button, "Đang tạo…");
      $(".bb84-error", root).innerHTML = "";
      try { data = await request("/api/lesson", {scenario: $("#bb84-scenario", root).value, seed: Number($("#bb84-seed", root).value)}); if (!root.isConnected) return; step = 0; draw(); }
      catch (error) { if (root.isConnected) $(".bb84-error", root).innerHTML = errorBox(error.message); }
      finally { finish(); }
    });
    root.addEventListener("click", event => { const b = event.target.closest("[data-bb84-step]"); if (b && data) { step = Number(b.dataset.bb84Step); draw(); $(`[data-bb84-step="${step}"]`, root).focus({preventScroll: true}); } });
  }
  function e91Widget(root) {
    root.innerHTML = `<header class="widget-header"><h3>Thực hành E91 với số liệu backend</h3><p>Nhiễu ở đây là trộn nhiễu trắng của dashboard, khác xác suất lật bit ở demo mạng.</p></header><div class="widget-body"><form><div class="widget-controls"><div class="field"><label for="e91-count">Số cặp</label><select id="e91-count"><option value="4096">4.096</option><option value="16384" selected>16.384</option><option value="65536">65.536</option></select></div><div class="field"><label for="e91-seed">Seed</label><input id="e91-seed" type="number" min="0" max="2147483647" step="1" value="2026" required></div><div class="field range-field"><label for="e91-noise">Trộn nhiễu trắng <output class="range-value" id="e91-noise-value">0%</output></label><input id="e91-noise" type="range" min="0" max="1" value="0" step="0.05"></div></div><button class="button small primary" type="submit">Chạy và xem CHSH</button></form><div class="e91-output" aria-live="polite"><p class="widget-status">Chưa chạy. Thử mức 0% trước, rồi 50% để đối chiếu kỳ vọng và quan sát.</p></div></div>`;
    $("#e91-noise", root).addEventListener("input", event => { $("#e91-noise-value", root).textContent = pct(Number(event.target.value)); });
    $("form", root).addEventListener("submit", async event => {
      event.preventDefault(); const button = $("button[type=submit]", root), finish = busy(button, "Đang mô phỏng…"), output = $(".e91-output", root);
      output.innerHTML = '<p class="widget-status">Đang đếm kết quả các phép đo trong backend…</p>';
      try {
        const data = await request("/api/e91/simulate", {signals: Number($("#e91-count", root).value), seed: Number($("#e91-seed", root).value), noise_probability: Number($("#e91-noise", root).value)});
        if (!root.isConnected) return;
        const b = data.bell, k = data.key, fixed = value => value == null ? "Chưa có" : value.toFixed(4);
        output.innerHTML = `<div class="data-metrics">${metric("|S| quan sát", fixed(b.abs_s), `Kỳ vọng ${fixed(Math.abs(b.expected_s))}`)}${metric("Khoảng 95% của |S|", `${fixed(b.ci_low)} – ${fixed(b.ci_high)}`, "So cận dưới với 2")}${metric("QBER nhóm khóa", pct(k.qber), `Kỳ vọng ${pct(k.expected_qber)}`)}</div><div class="status-line">${pill(b.status, statusKind(b.status))}<span>${b.status === "violation" ? "Cận dưới |S| vượt 2 trong mô hình." : b.status === "at_or_below_bound" ? "Cận trên |S| không vượt 2." : "Thiếu bằng chứng hoặc khoảng còn cắt mốc 2."}</span></div><div class="table-scroll" tabindex="0" role="region" aria-label="Các hạng CHSH"><table><caption>Bốn nhóm Bell và dấu ghép vào S</caption><thead><tr><th scope="col">Góc</th><th scope="col">Số cặp</th><th scope="col">E quan sát</th><th scope="col">Dấu</th></tr></thead><tbody>${b.pairs.map(p => `<tr><td>${p.alice_angle}° / ${p.bob_angle}°</td><td>${p.count}</td><td>${fixed(p.correlation)}</td><td>${p.sign === 1 ? "+" : "−"}</td></tr>`).join("")}</tbody></table></div><p class="widget-scope">Đã chạy N = ${num(data.signals)}, seed = ${data.seed}, nhiễu trắng ${pct(data.noise_probability)}. Đây là thống kê E91 tổng hợp; endpoint này không phát hành khóa hoặc mã hóa dữ liệu.</p>${jsonDetails(data)}`;
      } catch (error) { if (root.isConnected) output.innerHTML = errorBox(error.message); } finally { finish(); }
    });
  }
  function packetWidget(root) {
    let token = null;
    root.innerHTML = `<header class="widget-header"><h3>Sửa gói → nhận gói gốc → phát lại</h3><p>Dùng /api/packet và /api/packet/action của backend. Chỉ nhập thông điệp demo công khai.</p></header><div class="widget-body"><form><label class="bit-label" for="packet-message">Thông điệp gửi cho Bob</label><textarea id="packet-message" class="widget-input packet-text" maxlength="4096">Xin chào Bob, mình đang học project!</textarea><div class="actions"><button class="button small primary" type="submit">Tạo phiên và gói mới</button></div></form><div class="packet-error"></div><div class="packet-info"></div><div class="actions packet-actions" hidden><button class="button small" data-packet-action="tamper">1. Thử sửa một bit</button><button class="button small" data-packet-action="decrypt">2. Bob nhận gói gốc</button><button class="button small" data-packet-action="replay" disabled>3. Thử phát lại</button></div><ol class="packet-log" aria-live="polite"></ol><p class="widget-scope">Gói được giữ trong RAM có thời hạn 600 giây và giới hạn số lượng. Tạo gói mới nếu server khởi động lại, gói hết hạn hoặc bị thay thế. Trang học không lưu token/bản rõ vào localStorage.</p></div>`;
    const log = (text, kind) => { const li = document.createElement("li"); li.className = kind; li.textContent = text; $(".packet-log", root).append(li); };
    const setActions = (received, disabled = false) => {
      $$("[data-packet-action]", root).forEach(b => { b.disabled = disabled || (b.dataset.packetAction === "replay" ? !received : received); });
    };
    $("form", root).addEventListener("submit", async event => {
      event.preventDefault(); const button = $("button[type=submit]", root), finish = busy(button, "Đang tạo khóa…");
      token = null; $(".packet-actions", root).hidden = true; $(".packet-error", root).innerHTML = ""; $(".packet-info", root).innerHTML = ""; $(".packet-log", root).innerHTML = "";
      try {
        const data = await request("/api/packet", {message: $("#packet-message", root).value}); if (!root.isConnected) return;
        if (!data.packet) { $(".packet-error", root).innerHTML = errorBox(`Phiên chưa tạo gói: ${data.postprocessing?.status || data.status}. Hãy tạo lại một phiên sạch.`); return; }
        const p = data.packet; token = p.token;
        $(".packet-info", root).innerHTML = `<div class="data-metrics">${metric("Bản rõ UTF-8", `${p.plaintext_bytes} byte`)}${metric("Bản mã + tag", `${p.ciphertext_bytes} byte`)}${metric("Tag / nonce", `${p.tag_bytes} / ${p.nonce_bytes} byte`)}</div><p class="small-text muted">Bản mã (hex, tối đa 128 byte phần thân; chưa kèm tag):</p><code class="packet-code">${esc(p.ciphertext_preview_hex || "(Bản rõ rỗng, không có phần thân)")}</code><p class="widget-status">Đã tạo gói sequence ${p.sequence}. Thử sửa trước khi Bob nhận; bản gốc không bị thay đổi bởi phép thử sửa gói.</p>`;
        $(".packet-actions", root).hidden = false; setActions(false); log("Đã tạo khóa mô hình và gói có xác thực. Chưa gửi gói gốc cho Bob.", "");
      } catch (error) { if (root.isConnected) $(".packet-error", root).innerHTML = errorBox(error.message); } finally { finish(); }
    });
    let received = false;
    root.addEventListener("click", async event => {
      const button = event.target.closest("[data-packet-action]"); if (!button || !token || button.disabled) return;
      const action = button.dataset.packetAction;
      const createButton = $("button[type=submit]", root);
      createButton.disabled = true;
      setActions(received, true); $(".packet-error", root).innerHTML = "";
      try {
        const data = await request("/api/packet/action", {token, action}); if (!root.isConnected) return;
        received = Boolean(data.received);
        if (action === "tamper") log(`Sửa gói: ${data.status}, reason = ${data.reason}. Không phát hành bản rõ.`, "rejected");
        else if (action === "decrypt") log(`Gói gốc: ${data.status}. Bob đọc được: “${data.plaintext}”.`, "accepted");
        else log(`Phát lại: ${data.status}, reason = ${data.reason}. Không phát hành lại bản rõ.`, "rejected");
      } catch (error) { if (root.isConnected) $(".packet-error", root).innerHTML = errorBox(error.message); }
      finally { setActions(received); createButton.disabled = false; }
    });
    $("form", root).addEventListener("submit", () => { received = false; });
  }
  function sessionWidget(root) {
    const scenarios = {clean: {}, eve: {eve_fraction: 1}, weak: {eve_fraction: .1}, small: {signals: 16}, noise: {noise_probability: .1}};
    root.innerHTML = `<header class="widget-header"><h3>Chạy phiên và tìm đúng lớp dừng</h3><p>Gọi /api/session. Mọi số liệu bên dưới là kết quả backend của lần bấm, không phải dữ liệu mẫu viết sẵn.</p></header><div class="widget-body"><form class="widget-controls"><div class="field"><label for="session-scenario">Kịch bản</label><select id="session-scenario"><option value="clean">Kênh sạch</option><option value="eve">Eve chặn toàn phần</option><option value="weak">Eve chặn 10%</option><option value="small">Chỉ 16 tín hiệu</option><option value="noise">Chỉ nhiễu 10%</option></select></div><button class="button small primary" type="submit">Chạy phiên</button></form><div class="session-output" aria-live="polite"><p class="widget-status">Dự đoán: dừng ở thống kê, hậu xử lý hay đã đến mã hóa?</p></div></div>`;
    $("form", root).addEventListener("submit", async event => {
      event.preventDefault(); const button = $("button[type=submit]", root), finish = busy(button, "Đang chạy…"), output = $(".session-output", root);
      output.innerHTML = '<p class="widget-status">Đang thực hiện phiên với seed mô phỏng 2026…</p>';
      try {
        const data = await request("/api/session", {seed: 2026, message: "Thong diep demo hoc project", ...scenarios[$("#session-scenario", root).value]}); if (!root.isConnected) return;
        const p = data.postprocessing;
        output.innerHTML = `<div class="data-metrics">${metric("QBER quan sát", pct(data.qber), `${data.sample_errors}/${data.sample_count} lỗi/mẫu`)}${metric("Bit sau loại mẫu", num(data.remaining_count))}${metric("Đầu ra hậu xử lý", `${p.output_bits} bit`)}</div>${intervalChart(data.ci_low, data.ci_high, data.qber, data.threshold)}<div class="status-line"><span>Monitor</span>${pill(data.status, statusKind(data.status))}<span>Hậu xử lý</span>${pill(p.status, statusKind(p.status))}</div><div class="widget-result"><p><strong>reason:</strong> ${esc(data.reason)}<br><strong>Hậu xử lý:</strong> ${esc(p.reason)}<br><strong>Mã hóa:</strong> ${data.encryption ? `Đã chạy; roundtrip_ok = ${data.encryption.roundtrip_ok}, tamper_rejected = ${data.encryption.tamper_rejected}, replay_rejected = ${data.encryption.replay_rejected}.` : "Chưa chạy, encryption = null."}</p></div><p class="widget-scope">N = ${num(data.signals)}, seed ${data.seed}, f = ${pct(data.eve_fraction)}, p = ${pct(data.noise_probability)}. Kỳ vọng mô hình ${pct(data.noise_probability + data.eve_fraction / 4 - data.noise_probability * data.eve_fraction / 2)}; không phải chính QBER quan sát.</p>${jsonDetails(data)}`;
      } catch (error) { if (root.isConnected) output.innerHTML = errorBox(error.message); } finally { finish(); }
    });
  }
  function networkWidget(root) {
    const phases = [
      ["Kết nối đến Bob qua Eve", "Alice kết nối cổng 9101 của Eve. Eve mở kết nối tiếp đến 9100 của Bob. Đây là đường TCP, không phải dashboard HTTP.", "alice", "transport", "configure_socket"],
      ["Bắt tay và xác thực", "Bob gửi challenge; hai phía gắn mã phiên với thử thách đó và dùng cùng PSK để xác thực thảo luận. Eve chỉ chuyển tiếp, không có PSK.", "bob", "session", "hello_alice"],
      ["Tạo và xác nhận khóa", "BB84 hoặc E91 tạo vật liệu. Qua giám sát, Cascade, xác nhận và Toeplitz mới có kênh ứng dụng. Không đủ điều kiện thì dừng ở đây.", "alice", "session", "finish_alice_channel"],
      ["Metadata rồi các khối AEAD", "Alice gửi tên/size/hash mã hóa, sau đó từng khối nội dung 64 KiB, rồi thông điệp end. Mỗi gói có sequence riêng.", "alice", "transfer", "send_transfer"],
      ["Kiểm tra, lưu và biên nhận", "Bob xác thực từng khối, kiểm tra size/hash/end rồi đổi .part thành tệp hoàn tất. Receipt có HMAC trở về Alice để xác nhận.", "bob", "transfer", "receive_transfer"],
    ];
    let phase = 0;
    root.innerHTML = `<header class="widget-header"><h3>Theo thứ tự một lượt truyền</h3><p>Sơ đồ giải thích trình tự trong code, không mở socket hoặc gửi tệp thật.</p></header><div class="widget-body"><div class="network-topology"><div class="network-person" data-person="alice"><strong>Alice</strong><small>UI 8772</small></div><div class="network-wire">TCP 9101<span aria-hidden="true">→</span></div><div class="network-person eve"><strong>Eve</strong><small>UI 8771</small></div><div class="network-wire">TCP 9100<span aria-hidden="true">→</span></div><div class="network-person" data-person="bob"><strong>Bob</strong><small>UI 8770</small></div></div><div class="network-phase" aria-live="polite"></div><div class="actions"><button class="button small" data-network-prev>Bước trước</button><button class="button small primary" data-network-next>Bước tiếp</button><span class="small-text muted network-counter"></span></div></div>`;
    const draw = () => {
      const [title, description, person, file, symbol] = phases[phase];
      $(".network-phase", root).innerHTML = `<h4>${phase + 1}. ${esc(title)}</h4><p>${esc(description)}</p>${sourceLink(`bb84_lab/network/${file}.py`, symbol)}`;
      $$("[data-person]", root).forEach(el => el.classList.toggle("active", el.dataset.person === person));
      $("[data-network-prev]", root).disabled = phase === 0; $("[data-network-next]", root).disabled = phase === phases.length - 1;
      $(".network-counter", root).textContent = `${phase + 1} / ${phases.length}`;
    };
    $("[data-network-prev]", root).addEventListener("click", () => { if (phase > 0) { phase--; draw(); } });
    $("[data-network-next]", root).addEventListener("click", () => { if (phase < phases.length - 1) { phase++; draw(); } }); draw();
  }
  async function graphReaderWidget(root) {
    root.innerHTML = `<header class="widget-header"><h3>Tập đọc trên study đã đo</h3><p>Dữ liệu lấy từ /api/study. Mỗi điểm là thống kê của một cấu hình, không phải một phiên.</p></header><div class="widget-body graph-body"><p role="status">Đang tải dữ liệu…</p></div>`;
    const body = $(".graph-body", root);
    try {
      const data = await request("/api/study");
      if (!root.isConnected) return;
      if (!data.available) {
        body.innerHTML = `<p class="widget-status" role="status">${data.reason === "study_incomplete" ? "Study đang chọn chưa hoàn tất." : "Server chưa có study hoàn tất để đọc."} Bạn vẫn có thể học cách đọc năm nhóm hình ở phần dưới. Chọn một thư mục study hoàn tất bằng tham số <code>--study-dir</code> khi khởi động server.</p>`;
        return;
      }
      const mainRows = Array.isArray(data.main_summary) ? data.main_summary : [];
      const evaluation = Array.isArray(data.evaluation_summary) ? data.evaluation_summary : [];
      const paired = Array.isArray(data.paired_summary) ? data.paired_summary : [];
      const finalRows = data.postprocessing_manifest?.state === "complete" && Array.isArray(data.postprocessing_summary) ? data.postprocessing_summary : [];
      const allRows = [...mainRows, ...evaluation];
      if (!allRows.length) { body.innerHTML = '<p class="widget-status" role="status">Study đã hoàn tất nhưng chưa có bảng tổng hợp phù hợp cho bộ đọc này.</p>'; return; }
      const values = (rows, field) => [...new Set(rows.map(r => r[field]).filter(Number.isFinite))].sort((a, b) => a - b);
      const options = (rows, field, format) => values(rows, field).map(v => `<option value="${v}">${esc(format(v))}</option>`).join("");
      const fixed = value => Number(value).toLocaleString("vi-VN", {maximumFractionDigits: 2});
      body.innerHTML = `<p class="graph-provenance">Nguồn: study ${esc(data.manifest?.mode || "đã lưu")}${data.manifest?.created_utc ? ` · tạo ${esc(data.manifest.created_utc)}` : ""}. Chọn điểm để đọc cấu hình và mẫu số.</p><div class="widget-controls"><div class="field"><label for="graph-kind">Nhóm hình</label><select id="graph-kind">${Object.entries(course.chartGuides).map(([id, g]) => `<option value="${id}">${id.slice(0, 2)} · ${esc(g.title)}</option>`).join("")}</select></div></div><div class="widget-controls"><div class="field" id="graph-panel-field"><label for="graph-panel">Ô / đại lượng</label><select id="graph-panel"></select></div><div class="field" id="graph-noise-field"><label for="graph-noise">Nhiễu nền p</label><select id="graph-noise">${options(allRows, "noise_probability", pct)}</select></div><div class="field" id="graph-n-field"><label for="graph-n">Số tín hiệu N</label><select id="graph-n">${options(allRows, "signals", num)}</select></div><div class="field" id="graph-alpha-field"><label for="graph-alpha">Lấy mẫu α</label><select id="graph-alpha">${options(allRows, "sample_fraction", pct)}</select></div></div><div class="graph-guide"></div><div class="graph-result"></div>`;
      const kindInput = $("#graph-kind", root), panelInput = $("#graph-panel", root);
      const nInput = $("#graph-n", root), noiseInput = $("#graph-noise", root), alphaInput = $("#graph-alpha", root);
      if (values(allRows, "signals").includes(4096)) nInput.value = "4096";
      const baseline = data.selection?.baseline_fraction;
      if (Number.isFinite(baseline) && values(allRows, "sample_fraction").includes(baseline)) alphaInput.value = String(baseline);
      const colors = ["#2859a7", "#16756b", "#895a17", "#7052a3", "#ad3b49", "#4d6279"];
      const draw = () => {
        const kind = kindInput.value, panel = panelInput.value;
        const noise = Number(noiseInput.value), n = Number(nInput.value), alpha = Number(alphaInput.value);
        const isComparison = kind === "05_comparison", isPaired = isComparison && panel === "paired";
        $("#graph-panel-field", root).hidden = !["03_no_eve", "05_comparison"].includes(kind);
        $("#graph-noise-field", root).hidden = kind === "03_no_eve" || (isComparison && !isPaired);
        $("#graph-n-field", root).hidden = !["04_retention", "05_comparison"].includes(kind) || isPaired;
        $("#graph-alpha-field", root).hidden = isComparison;
        const guide = course.chartGuides[kind];
        $(".graph-guide", root).innerHTML = `<h4>${esc(guide.title)}</h4><p>${esc(guide.read)}</p><p class="small-text muted">Lưu ý: ${esc(guide.avoid)}</p>`;
        let series = [], xLabel = "Tỷ lệ can thiệp f (%)", yLabel = "QBER mẫu (%)", percentY = true, logX = false, reference = false;
        let uncertainty = "Không vẽ thanh sai số cho đại lượng này.", source = "main_summary";
        const point = (row, x, y, extra = {}) => ({row, x, y, ...extra});
        const groupRows = (rows, group, xField, yField, label, extra = () => ({})) => values(rows, group).map(v => ({label: label(v), points: rows.filter(r => r[group] === v && Number.isFinite(r[yField])).sort((a, b) => a[xField] - b[xField]).map(r => point(r, r[xField], r[yField], extra(r)))}));
        if (kind === "01_qber") {
          const rows = mainRows.filter(r => r.noise_probability === noise && r.sample_fraction === alpha);
          series = groupRows(rows, "signals", "eve_fraction", "qber_mean", v => `N = ${num(v)}`, r => ({low: Number.isFinite(r.qber_stdev) ? r.qber_mean - r.qber_stdev : null, high: Number.isFinite(r.qber_stdev) ? r.qber_mean + r.qber_stdev : null, expected: r.expected_qber}));
          uncertainty = "Thanh dọc: mean ± SD của QBER giữa các phiên; không phải Wilson CI 95%. SD không có thì không vẽ thanh.";
        } else if (kind === "02_detection" || kind === "03_no_eve") {
          const noEve = kind === "03_no_eve", status = noEve ? panel : "anomalous";
          const rows = mainRows.filter(r => r.sample_fraction === alpha && (noEve ? r.eve_fraction === 0 : r.noise_probability === noise && r.eve_fraction > 0));
          xLabel = noEve ? "Nhiễu nền p (%) · f = 0" : "Số tín hiệu N · thang log₂";
          yLabel = `${status === "anomalous" ? "Phiên bất thường" : "Phiên chưa đủ bằng chứng"} (%)`; logX = !noEve;
          series = groupRows(rows, noEve ? "signals" : "eve_fraction", noEve ? "noise_probability" : "signals", `${status}_rate`, v => noEve ? `N = ${num(v)}` : `f = ${pct(v)}`, r => ({low: r[`${status}_ci95`]?.[0], high: r[`${status}_ci95`]?.[1], count: r[`${status}_count`]}));
          uncertainty = "Mảng màu và thanh dọc: Wilson 95% của tỷ lệ phiên. Mẫu số là số phiên thử, khác số bit mẫu QBER.";
        } else if (kind === "04_retention") {
          const rows = mainRows.filter(r => r.signals === n && r.noise_probability === noise && r.sample_fraction === alpha).sort((a, b) => a.eve_fraction - b.eve_fraction);
          percentY = false; yLabel = "Bit trung bình / mọi phiên đầu vào";
          series = [["sifted_mean", "Sau sàng lọc"], ["remaining_mean", "Sau loại mẫu"], ["y_pre_mean", "Y_pre"]].map(([field, label]) => ({label, points: rows.filter(r => Number.isFinite(r[field])).map(r => point(r, r.eve_fraction, r[field]))}));
          const measured = finalRows.filter(r => r.dataset === "main" && r.signals === n && r.noise_probability === noise && r.sample_fraction === alpha).sort((a, b) => a.eve_fraction - b.eve_fraction);
          if (measured.length) series.push({label: "Y_final đã đo", points: measured.filter(r => Number.isFinite(r.y_final_mean)).map(r => point(r, r.eve_fraction, r.y_final_mean))});
          uncertainty += measured.length ? " Y_final lấy từ postprocessing_summary đã hoàn tất." : " Y_final chưa có số liệu hậu xử lý phù hợp, nên không vẽ đường này.";
        } else if (isPaired) {
          source = "paired_summary"; percentY = false; reference = true;
          xLabel = "Tỷ lệ lấy mẫu α (%)"; yLabel = `Chênh lệch Y_pre so với B0${Number.isFinite(baseline) ? ` (${pct(baseline)})` : ""} (bit)`;
          series = [{label: `f = 0; p = ${pct(noise)}`, points: paired.filter(r => r.eve_fraction === 0 && r.noise_probability === noise && Number.isFinite(r.mean_difference)).sort((a, b) => a.sample_fraction - b.sample_fraction).map(r => point(r, r.sample_fraction, r.mean_difference, {low: r.ci95?.[0], high: r.ci95?.[1]}))}];
          uncertainty = "Thanh dọc: bootstrap 95% của chênh lệch trung bình ghép cặp. Mỗi cặp dùng chung phiên; đường đứt là chênh lệch 0.";
        } else if (isComparison) {
          source = "evaluation_summary";
          const yieldView = panel === "yield", f = yieldView ? 0 : panel === "strong" ? .5 : .1;
          percentY = !yieldView; xLabel = "Nhiễu nền p (%)"; yLabel = yieldView ? "Y_pre trung bình / mọi phiên (bit)" : "Phiên bất thường (%)";
          const rows = evaluation.filter(r => r.signals === n && r.eve_fraction === f);
          series = groupRows(rows, "sample_fraction", "noise_probability", yieldView ? "y_pre_mean" : "anomalous_rate", v => `α = ${pct(v)}`, r => yieldView ? {} : {low: r.anomalous_ci95?.[0], high: r.anomalous_ci95?.[1], count: r.anomalous_count});
          uncertainty = `Tập evaluation, N = ${num(n)}, f = ${pct(f)}. ` + (yieldView ? uncertainty : "Mảng màu và thanh dọc: Wilson 95% của tỷ lệ phiên anomalous.");
        }
        series = series.filter(s => s.points.length).map((s, i) => ({...s, color: colors[i % colors.length]}));
        const result = $(".graph-result", root);
        const points = series.flatMap((s, si) => s.points.map((p, pi) => ({...p, si, pi, label: s.label, color: s.color})));
        if (!points.length) { result.innerHTML = '<p class="empty-state" role="status">Không có số liệu cho bộ lọc này. Hãy chọn ô, N, p hoặc α khác; không thay bằng dữ liệu giả.</p>'; return; }
        const xs = [...new Set(points.map(p => p.x))].sort((a, b) => a - b);
        const extents = points.flatMap(p => [p.y, p.low, p.high, p.expected]).filter(Number.isFinite);
        const yMin = Math.min(0, ...extents), rawMax = Math.max(0, ...extents);
        const yMax = percentY && kind !== "01_qber" ? 1 : Math.max(percentY ? .05 : 1, rawMax + (rawMax - yMin) * .12);
        const xMin = logX ? Math.log2(xs[0]) : xs[0], xMax = logX ? Math.log2(xs.at(-1)) : xs.at(-1);
        const x = v => xMax === xMin ? 380 : 82 + ((logX ? Math.log2(v) : v) - xMin) / (xMax - xMin) * 596;
        const y = v => 292 - (v - yMin) / (yMax - yMin) * 240;
        const valueLabel = v => percentY ? pct(v) : fixed(v);
        const xValue = v => logX ? num(v) : pct(v);
        const line = list => list.map((p, i) => `${i ? "L" : "M"}${x(p.x)},${y(p.y)}`).join(" ");
        const graphId = "study-reading-plot";
        let svg = `<svg class="reading-chart" viewBox="0 0 740 376" role="img" aria-labelledby="${graphId}-title ${graphId}-desc"><title id="${graphId}-title">${esc(guide.title)}</title><desc id="${graphId}-desc">${esc(xLabel)}; ${esc(yLabel)}. ${esc(uncertainty)} Bảng số liệu và các nút chọn điểm nằm sau hình.</desc><text x="18" y="23" class="reading-axis-title">${esc(yLabel)}</text>`;
        for (let i = 0; i <= 4; i++) { const v = yMin + (yMax - yMin) * i / 4; svg += `<line x1="82" x2="678" y1="${y(v)}" y2="${y(v)}" class="reading-grid"/><text x="72" y="${y(v) + 4}" text-anchor="end">${esc(valueLabel(v))}</text>`; }
        const ticks = xs.filter((_, i) => xs.length <= 7 || i % Math.ceil((xs.length - 1) / 6) === 0 || i === xs.length - 1);
        svg += ticks.map(v => `<text x="${x(v)}" y="320" text-anchor="middle">${esc(xValue(v))}</text>`).join("");
        svg += `<text x="380" y="359" text-anchor="middle" class="reading-axis-title">${esc(xLabel)}</text>`;
        if (reference) svg += `<line x1="82" x2="678" y1="${y(0)}" y2="${y(0)}" class="reading-reference"/>`;
        for (const s of series) {
          const band = s.points.filter(p => Number.isFinite(p.low) && Number.isFinite(p.high));
          if (band.length > 1 && percentY && kind !== "01_qber") svg += `<path d="${band.map((p, i) => `${i ? "L" : "M"}${x(p.x)},${y(p.high)}`).join(" ")} ${[...band].reverse().map(p => `L${x(p.x)},${y(p.low)}`).join(" ")} Z" fill="${s.color}" opacity=".12"/>`;
          svg += `<path d="${line(s.points)}" stroke="${s.color}" fill="none" stroke-width="2"/>`;
          svg += band.map(p => `<path d="M${x(p.x)},${y(p.low)} V${y(p.high)} M${x(p.x) - 4},${y(p.low)} h8 M${x(p.x) - 4},${y(p.high)} h8" stroke="${s.color}" fill="none"/>`).join("");
        }
        const expected = series[0].points.filter(p => Number.isFinite(p.expected)).map(p => ({...p, y: p.expected}));
        if (expected.length) svg += `<path d="${line(expected)}" class="reading-reference" fill="none"/>`;
        svg += points.map((p, index) => `<circle cx="${x(p.x)}" cy="${y(p.y)}" r="5" fill="${p.color}" stroke="white" stroke-width="2" data-graph-point="${index}"><title>${esc(p.label)}; ${esc(xValue(p.x))}; ${esc(valueLabel(p.y))}</title></circle>`).join("") + "</svg>";
        result.innerHTML = `<p class="graph-uncertainty">${esc(uncertainty)}</p><ul class="reading-legend">${series.map(s => `<li><svg class="legend-swatch" viewBox="0 0 24 12" aria-hidden="true"><path d="M0 6 H24" stroke="${s.color}" stroke-width="3"/></svg>${esc(s.label)}</li>`).join("")}${expected.length ? '<li><span class="legend-swatch reference"></span>Kỳ vọng mô hình</li>' : ""}${reference ? '<li><span class="legend-swatch reference"></span>Chênh lệch 0</li>' : ""}</ul><div class="reading-chart-scroll" tabindex="0" role="region" aria-label="Đồ thị study, có thể cuộn ngang">${svg}</div><div class="field graph-point-picker"><label for="graph-point-select">Chọn điểm để giải thích (cũng có thể bấm chấm trên hình)</label><select id="graph-point-select">${points.map((p, i) => `<option value="${i}">${esc(p.label)} · ${logX ? "N" : kind === "03_no_eve" || (isComparison && !isPaired) ? "p" : isPaired ? "α" : "f"} = ${esc(xValue(p.x))}</option>`).join("")}</select></div><div class="graph-point-detail widget-result" aria-live="polite"></div><details class="graph-data"><summary>Xem bảng số liệu đã vẽ (${points.length} điểm)</summary><div class="table-scroll" tabindex="0" role="region" aria-label="Bảng số liệu study"><table><caption>Nguồn: ${source}; mỗi dòng là một cấu hình.</caption><thead><tr><th scope="col">Nhóm</th><th scope="col">${esc(xLabel)}</th><th scope="col">${esc(yLabel)}</th><th scope="col">Thanh / khoảng</th><th scope="col">Phiên / cặp</th></tr></thead><tbody>${points.map(p => `<tr><th scope="row">${esc(p.label)}</th><td>${esc(xValue(p.x))}</td><td>${esc(valueLabel(p.y))}</td><td>${Number.isFinite(p.low) && Number.isFinite(p.high) ? `${esc(valueLabel(p.low))} → ${esc(valueLabel(p.high))}` : "Không có"}</td><td>${esc(p.row.sessions ?? p.row.pairs ?? "Không ghi")}</td></tr>`).join("")}</tbody></table></div></details>`;
        const choosePoint = index => {
          const p = points[index], r = p.row;
          $("#graph-point-select", root).value = String(index);
          $$("[data-graph-point]", root).forEach(dot => dot.classList.toggle("selected", Number(dot.dataset.graphPoint) === index));
          let explanation;
          if (kind === "01_qber") explanation = `QBER trung bình ${pct(p.y)} trên ${num(r.qber_observations ?? r.sessions)} phiên có QBER. SD giữa phiên ${Number.isFinite(r.qber_stdev) ? pct(r.qber_stdev) : "chưa có"}; kỳ vọng mô hình ${pct(r.expected_qber)}. Thanh SD không phải khoảng Wilson của tỷ lệ phiên.`;
          else if (isPaired) explanation = `Chênh lệch trung bình ${fixed(p.y)} bit trên ${num(r.pairs)} cặp phiên so với B0. ` + (Number.isFinite(p.low) && Number.isFinite(p.high) ? `Bootstrap 95%: [${fixed(p.low)}; ${fixed(p.high)}] bit. ${p.low > 0 ? "Khoảng hoàn toàn trên 0, hỗ trợ Y_pre cao hơn B0 trong mô hình." : p.high < 0 ? "Khoảng hoàn toàn dưới 0, hỗ trợ Y_pre thấp hơn B0 trong mô hình." : "Khoảng chứa 0, chưa đủ bằng chứng về chênh lệch theo cách tóm tắt này."}` : "Chưa có khoảng bootstrap.");
          else if (Number.isFinite(p.count)) explanation = `${num(p.count)} / ${num(r.sessions)} phiên, tức ${pct(p.y)}. ${Number.isFinite(p.low) && Number.isFinite(p.high) ? `Wilson 95% của tỷ lệ phiên: [${pct(p.low)}; ${pct(p.high)}].` : "Chưa có khoảng Wilson."} Mẫu số là phiên thử, không phải số bit mẫu; đây không phải QBER.`;
          else explanation = `${p.label}: trung bình ${fixed(p.y)} bit trên ${num(r.sessions)} phiên đầu vào. ${p.label.startsWith("Y_final") ? "Đây là đầu ra hậu xử lý đã đo trong mô hình giáo dục." : "Sản lượng vật liệu trước hậu xử lý chưa phải khóa cuối."}`;
          const config = [Number.isFinite(r.signals) ? `N = ${num(r.signals)}` : "", Number.isFinite(r.eve_fraction) ? `f = ${pct(r.eve_fraction)}` : "", Number.isFinite(r.noise_probability) ? `p = ${pct(r.noise_probability)}` : "", Number.isFinite(r.sample_fraction) ? `α = ${pct(r.sample_fraction)}` : ""].filter(Boolean).join("; ");
          $(".graph-point-detail", root).innerHTML = `<h4>${esc(p.label)}</h4><p>${esc(config)}.</p><p>${esc(explanation)}</p>`;
        };
        $("#graph-point-select", root).addEventListener("change", event => choosePoint(Number(event.target.value)));
        $(".reading-chart", result).addEventListener("click", event => { const dot = event.target.closest("[data-graph-point]"); if (dot) choosePoint(Number(dot.dataset.graphPoint)); });
        choosePoint(0);
      };
      const changeKind = () => {
        const panels = kindInput.value === "03_no_eve" ? [["anomalous", "Phiên bất thường · anomalous"], ["inconclusive", "Chưa đủ bằng chứng · inconclusive"]] : [["yield", "Không Eve: Y_pre"], ["strong", "Can thiệp mạnh f = 50%"], ["weak", "Can thiệp yếu f = 10%"], ["paired", "Chênh lệch ghép cặp so B0 · f = 0"]];
        panelInput.innerHTML = panels.map(([v, label]) => `<option value="${v}">${esc(label)}</option>`).join(""); draw();
      };
      kindInput.addEventListener("change", changeKind);
      for (const input of [panelInput, nInput, noiseInput, alphaInput]) input.addEventListener("change", draw);
      changeKind();
    } catch (error) { if (root.isConnected) body.innerHTML = errorBox(error.message); }
  }
  const widgetFactories = {journey: journeyWidget, architecture: architectureWidget, basis: basisWidget, wilson: wilsonWidget, parity: parityWidget, toeplitz: toeplitzWidget, bb84: bb84Widget, e91: e91Widget, packet: packetWidget, session: sessionWidget, network: networkWidget, "graph-reader": graphReaderWidget};
  function mountWidgets(root) { $$("[data-widget]", root).forEach(el => widgetFactories[el.dataset.widget]?.(el)); }

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {
        const textarea = document.createElement("textarea"); textarea.value = text; textarea.className = "sr-only"; document.body.append(textarea); textarea.select();
        const ok = document.execCommand("copy"); textarea.remove(); if (!ok) throw new Error("Copy unavailable");
      }
      toast("Đã sao chép.");
    } catch { toast("Trình duyệt chưa cho sao chép tự động. Bạn có thể chọn nội dung rồi nhấn Ctrl+C."); }
  }
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-copy-command]");
    if (button) copyText($("pre code", button.closest(".command-block")).textContent);
    if (event.target.closest("[data-search-open]")) openSearch();
    const abbreviation = event.target.closest("[data-abbreviation]");
    if (abbreviation) openAbbreviation(abbreviation.dataset.abbreviation);
    const anchor = event.target.closest("a[href^='#/']");
    if (anchor) {
      closeMenu();
      if ($("#search-dialog").open) $("#search-dialog").close();
      if ($("#abbreviation-dialog").open) $("#abbreviation-dialog").close();
      if (anchor.hash === location.hash) { event.preventDefault(); route(); }
    }
  });
  const stripHtml = html => { const div = document.createElement("div"); div.innerHTML = html; return div.textContent || ""; };
  const searchEntries = [
    ...course.lessons.map(l => ({kind: "Bài học", title: l.title, description: l.summary, text: `${l.title} ${l.summary} ${l.sections.map(s => `${s.title} ${stripHtml(s.body)}`).join(" ")}`, href: `#/lesson/${l.id}`})),
    ...course.glossary.map(g => ({kind: "Thuật ngữ", title: g.term, description: g.definition, text: `${g.term} ${g.definition}`, href: `#/lesson/${g.lesson}`})),
    ...course.abbreviations.map(a => ({kind: "Từ viết tắt", title: a.short, description: `${a.full} · ${a.meaning}`, text: `${a.short} ${a.full} ${a.meaning} ${a.usage} ${a.example}`, href: `#/abbreviations?term=${encodeURIComponent(a.short)}`})),
    ...course.symbols.map(s => ({kind: "Ký hiệu", title: s.symbol, description: s.meaning, text: `${s.symbol} ${s.meaning} ${s.usage}`, href: `#/abbreviations?term=${encodeURIComponent(s.symbol)}`})),
    ...course.modules.map(m => ({kind: "Module", title: m.name, description: m.role, text: `${m.name} ${m.description} ${m.files.join(" ")}`, href: "#/map"})),
  ];
  const seenSourceLinks = new Set();
  for (const lesson of course.lessons) for (const section of lesson.sections) {
    const template = document.createElement("template"); template.innerHTML = section.body;
    for (const a of $$("a[href^='#/code/']", template.content)) if (!seenSourceLinks.has(a.getAttribute("href"))) {
      seenSourceLinks.add(a.getAttribute("href"));
      searchEntries.push({kind: "Hàm / mã nguồn", title: a.textContent.replace("</>", "").trim(), description: lesson.title, text: `${a.textContent} ${a.getAttribute("href")} ${lesson.title}`, href: a.getAttribute("href")});
    }
  }
  function drawSearch() {
    const query = normalize($("#global-search").value).trim(), words = query.split(/\s+/).filter(Boolean);
    let entries = query ? searchEntries.filter(entry => words.every(word => normalize(entry.text).includes(word))).sort((a, b) => Number(normalize(b.title).includes(query)) - Number(normalize(a.title).includes(query))).slice(0, 24) : searchEntries.filter(e => e.kind === "Bài học").slice(0, 7);
    $("#search-results").innerHTML = entries.length ? entries.map(entry => `<a class="search-result" href="${esc(entry.href)}"><small>${esc(entry.kind)}</small><strong>${esc(entry.title)}</strong><p>${esc(entry.description)}</p></a>`).join("") : '<p class="empty-state">Chưa có kết quả. Thử “QBER”, “nonce”, “truyền tệp” hoặc tên hàm như “monitor”.</p>';
  }
  function openSearch() { if ($("#abbreviation-dialog").open) $("#abbreviation-dialog").close(); const dialog = $("#search-dialog"); if (!dialog.open) dialog.showModal(); drawSearch(); $("#global-search").focus(); }
  $("#global-search").addEventListener("input", drawSearch);
  $("#search-close").addEventListener("click", () => $("#search-dialog").close());
  $("#abbreviation-close").addEventListener("click", () => $("#abbreviation-dialog").close());
  $("#abbreviation-dialog").addEventListener("click", event => { if (event.target === event.currentTarget) { const r = event.currentTarget.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.currentTarget.close(); } });
  $("#search-dialog").addEventListener("click", event => { if (event.target === $("#search-dialog")) { const r = event.target.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close(); } });
  document.addEventListener("keydown", event => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(event.target.tagName) || event.target.isContentEditable;
    if (event.key === "/" && !typing && !event.ctrlKey && !event.altKey && !event.metaKey) { event.preventDefault(); openSearch(); }
    if (event.key === "Escape") {
      if ($("#abbreviation-dialog").open) {
        event.preventDefault(); $("#abbreviation-dialog").close();
      } else if ($("#search-dialog").open) {
        event.preventDefault();
        $("#search-dialog").close();
      } else {
        const menuWasOpen = $("#sidebar").classList.contains("open");
        closeMenu();
        if (menuWasOpen) $("#menu-toggle").focus();
      }
    }
  });
  let currentPage = "";
  function route() {
    let path, params;
    try { const [raw, query] = (location.hash.slice(1) || "/").split("?"); path = decodeURIComponent(raw); params = new URLSearchParams(query || ""); }
    catch { renderNotFound(); return; }
    const base = path + (path.startsWith("/code") || path === "/abbreviations" ? `?${params.toString()}` : "");
    if (tocObserver && currentPage !== base) { tocObserver.disconnect(); tocObserver = null; }
    const samePage = currentPage === base;
    closeMenu();
    if (!samePage) {
      currentPage = base;
      if (path === "/" || path === "") renderHome();
      else if (path.startsWith("/lesson/")) renderLesson(path.slice(8));
      else if (path === "/map") renderMap();
      else if (path === "/glossary") renderGlossary();
      else if (path === "/abbreviations") renderAbbreviations(params);
      else if (path === "/code" || path.startsWith("/code/")) renderCode(path.slice(6) || "bb84_lab/core/bb84.py", params.get("symbol") || "");
      else renderNotFound();
      window.scrollTo({top: 0, behavior: "instant"});
      main.focus({preventScroll: true});
    }
    const anchor = params.get("section");
    if (anchor && path.startsWith("/lesson/")) {
      const target = document.getElementById(`section-${anchor}`);
      if (target) { target.scrollIntoView({behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start"}); const heading = $("h2", target); if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({preventScroll: true}); } }
    }
  }
  window.addEventListener("hashchange", route);
  route(); health();
})();
