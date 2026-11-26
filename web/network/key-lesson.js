"use strict";

// A worked example with public bits. The lesson never loads data from a peer session.
const signals = [
  [1, "Z", "Z", 1], [0, "X", "X", 0], [1, "Z", "X", 0], [0, "X", "X", 0],
  [1, "Z", "Z", 1], [0, "X", "Z", 1], [1, "X", "X", 1], [0, "Z", "Z", 1],
  [1, "X", "Z", 1], [1, "Z", "Z", 1], [1, "Z", "X", 1], [1, "X", "X", 1],
].map(([alice, aliceBasis, bobBasis, bob], index) => ({
  number: index + 1, alice, aliceBasis, bob, bobBasis,
}));
const sampleNumbers = new Set([2, 10]);
const sifted = signals.filter(({ aliceBasis, bobBasis }) => aliceBasis === bobBasis);
const sample = sifted.filter(({ number }) => sampleNumbers.has(number));
const retained = sifted.filter(({ number }) => !sampleNumbers.has(number));
const sampleErrors = sample.filter(({ alice, bob }) => alice !== bob).length;
const xor = (bits) => bits.reduce((result, bit) => result ^ bit, 0);

function makeCascadeTrace(block) {
  const queries = [];
  function compare(group) {
    const alice = group.map((signal) => signal.alice);
    const bob = group.map((signal) => signal.bob);
    const different = xor(alice) !== xor(bob);
    queries.push({ group, alice, bob, different });
    return different;
  }

  // This block has one error. Search the odd half in each division.
  compare(block);
  let group = block;
  while (group.length > 1) {
    const middle = Math.floor(group.length / 2);
    const left = group.slice(0, middle);
    group = compare(left) ? left : group.slice(middle);
    queries.at(-1).remaining = group;
  }
  const correctedNumber = group[0].number;
  const corrected = block.map(({ bob, number }) => bob ^ Number(number === correctedNumber));
  return { queries, corrected, correctedNumber };
}

const cascade = makeCascadeTrace(retained);
const toeplitzSeed = [1, 0, 1, 1, 0, 1, 0, 0];
const outputLength = toeplitzSeed.length - retained.length + 1;
const matrix = Array.from({ length: outputLength }, (_, i) =>
  retained.map((_, j) => toeplitzSeed[retained.length - 1 + i - j]));
const aliceToeplitz = matrix.map((row) => xor(row.map((bit, i) => bit * retained[i].alice)));
const bobToeplitz = matrix.map((row) => xor(row.map((bit, i) => bit * cascade.corrected[i])));

const bb84Steps = [
  {
    title: "Alice chuẩn bị tín hiệu",
    description: "Với mỗi bit, Alice chọn cơ sở Z hoặc X. Cơ sở và bit cùng xác định trạng thái được gửi.",
    note: "Cơ sở Z dùng |0⟩ và |1⟩. Cơ sở X dùng |+⟩ và |−⟩.",
  },
  {
    title: "Bob đo tín hiệu",
    description: "Bob tự chọn cơ sở đo. Khi khác cơ sở chuẩn bị, kết quả đo lý tưởng là ngẫu nhiên. Trong ví dụ này, đường truyền làm sai thêm một bit ở tín hiệu 8.",
    note: "Mỗi hàng ghép bit với cơ sở, ví dụ 1 / X là bit 1 ở cơ sở X.",
  },
  {
    title: "Sàng lọc theo cơ sở",
    description: "Alice và Bob công khai cơ sở rồi giữ các vị trí có cùng cơ sở. Các vị trí khác cơ sở bị bỏ kể cả khi hai bit tình cờ trùng nhau.",
  },
  {
    title: "Công khai mẫu và tính QBER",
    description: "Hai bên chọn một phần các vị trí đã sàng lọc, so bit để ước tính tỷ lệ lỗi rồi loại các mẫu khỏi vật liệu khóa.",
    note: "Trong phiên mạng, mẫu nhỏ như ví dụ này không đạt điều kiện để tiếp tục. Các bước sau dùng những bit còn lại để minh họa phép tính.",
  },
];
const steps = [
  ...bb84Steps.map((step, index) => ({ ...step, stage: "bb84", draw: () => drawBB84(index) })),
  ...cascade.queries.map((query, index) => ({
    stage: "cascade",
    title: index === 0 ? "So parity của cả khối" : "Thu hẹp tới bit sai",
    description: index === 0
      ? "Parity là XOR của các bit trong cùng khối. Hai parity khác nhau cho biết khối chứa số sai khác lẻ."
      : "Cascade chia đôi vùng đang xét và so parity nửa đầu. Nếu hai parity khác nhau thì giữ nửa đầu. Nếu chúng bằng nhau thì xét nửa còn lại.",
    draw: () => drawCascade(query),
  })),
  {
    stage: "cascade",
    title: "Sửa rồi xác nhận",
    description: "Bob lật bit tại vị trí tìm được. Hai phía cần xác nhận chuỗi đã khớp trước khi chuyển sang Toeplitz.",
    note: "Phiên mạng dùng bốn lượt Cascade. Từ lượt hai, hoán vị và kích thước khối thay đổi. Sau mỗi lần sửa, Cascade kiểm tra lại các khối đã gặp có chứa vị trí đó.",
    draw: () => drawCascade(),
  },
  {
    stage: "toeplitz",
    title: "Lập ma trận Toeplitz",
    description: "Từ seed công khai, hai bên dựng cùng ma trận. Giá trị trên mỗi đường chéo hướng xuống phải giống nhau.",
    note: "Với chỉ số bắt đầu từ 0, phần tử T[i,j] lấy bit seed ở vị trí n − 1 + i − j, trong đó n là chiều dài chuỗi đầu vào.",
    draw: () => drawToeplitz(),
  },
  ...matrix.map((_, index) => ({
    stage: "toeplitz",
    title: `Tính bit đầu ra thứ ${index + 1}`,
    description: "Nhân từng bit đầu vào với hệ số ở cùng cột của hàng đang xét, rồi XOR các tích. Kết quả của mỗi hàng là một bit.",
    draw: () => drawToeplitz(index),
  })),
  {
    stage: "toeplitz",
    title: "Đối chiếu đầu ra",
    description: "Alice và Bob dùng cùng ma trận trên hai chuỗi đã khớp, nên thu được cùng ba bit minh họa.",
    note: "Phiên mạng tính riêng số bit có thể rút ngắn theo ngân sách khóa và dùng HKDF để dẫn xuất khóa ứng dụng gắn với phiên.",
    draw: () => drawToeplitz(matrix.length),
  },
];

const byId = (name) => document.getElementById(name);
const stageButtons = [...document.querySelectorAll("[data-lesson-stage]")];
const display = byId("key-lesson-display");
const back = byId("key-lesson-back");
const next = byId("key-lesson-next");
const restart = byId("key-lesson-restart");
let current = 0;

function element(tag, value, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
}

function table(label, columns, rows) {
  const wrapper = element("div", undefined, "table-scroll");
  wrapper.setAttribute("role", "region");
  wrapper.setAttribute("aria-label", label);
  wrapper.tabIndex = 0;
  const grid = element("table", undefined, "key-lesson-table");
  grid.createCaption().append(element("span", label, "sr-only"));
  const heading = grid.createTHead().insertRow();
  for (const column of columns) {
    const cell = element("th", column);
    cell.scope = "col";
    heading.append(cell);
  }
  const body = grid.createTBody();
  for (const { cells, className, marked } of rows) {
    const row = body.insertRow();
    row.className = className || "";
    cells.forEach((value, i) => {
      const cell = element(i === 0 ? "th" : "td", value, marked?.[i]);
      if (i === 0) cell.scope = "row";
      row.append(cell);
    });
  }
  wrapper.append(grid);
  return wrapper;
}

function line(label, content, className = "key-lesson-detail") {
  const paragraph = element("p", undefined, className);
  paragraph.append(element("strong", label), " ", element("code", content));
  return paragraph;
}

function drawBB84(index) {
  const rows = signals.map((signal) => {
    const { number, alice, aliceBasis, bob, bobBasis } = signal;
    const state = aliceBasis === "Z" ? `|${alice}⟩` : alice === 0 ? "|+⟩" : "|−⟩";
    const keep = aliceBasis === bobBasis;
    const sampled = index >= 3 && sampleNumbers.has(number);
    const className = index < 2 ? "" : sampled ? "is-sample" : keep ? "is-active" : "is-discarded";
    const cells = [number, `${alice} / ${aliceBasis}`, state];
    if (index >= 1) cells.push(`${bob} / ${bobBasis}`);
    if (index >= 2) cells.push(sampled ? "Mẫu đã loại" : keep ? "Giữ" : "Loại");
    return { cells, className };
  });
  const columns = ["Tín hiệu", "Alice", "Trạng thái"];
  if (index >= 1) columns.push("Bob");
  if (index >= 2) columns.push("Sàng lọc");
  if (index >= 3) {
    const percent = new Intl.NumberFormat("vi-VN", { style: "percent" }).format(sampleErrors / sample.length);
    display.append(
      line("QBER mẫu", `${sampleErrors} / ${sample.length} = ${percent}`, "key-lesson-formula"),
      element("p", `Giữ ${retained.length} bit sau khi bỏ mẫu ${[...sampleNumbers].join(" và ")}.`, "key-lesson-detail"),
    );
  }
  display.append(table("Các tín hiệu của bài học BB84", columns, rows));
  if (index === 2) display.append(line("Cùng cơ sở", `${sifted.length} / ${signals.length} tín hiệu`));
}

function parityEquation(bits) {
  return `${bits.join(" ⊕ ")} = ${xor(bits)}`;
}

function drawCascade(query) {
  const activeNumbers = query?.group.map(({ number }) => number);
  const rows = retained.map(({ number, alice, bob }, i) => ({
    cells: query ? [number, alice, bob] : [number, alice, bob, cascade.corrected[i]],
    className: activeNumbers?.includes(number) ? "is-active"
      : !query && number === cascade.correctedNumber ? "is-corrected" : "",
    marked: !query && number === cascade.correctedNumber ? { 2: "is-mismatch", 3: "is-highlighted" } : null,
  }));
  const columns = query ? ["Tín hiệu", "Alice", "Bob"] : ["Tín hiệu", "Alice", "Bob trước", "Bob sau"];
  display.append(table("Các bit còn lại sau khi loại mẫu", columns, rows));
  if (query) {
    display.append(
      line("Vị trí đang so", activeNumbers.join(", ")),
      line("Parity Alice", parityEquation(query.alice)),
      line("Parity Bob", parityEquation(query.bob)),
    );
    if (query.remaining) {
      const remainingNumbers = query.remaining.map(({ number }) => number).join(", ");
      display.append(line(query.different ? "Khác parity → giữ nửa đầu" : "Cùng parity → giữ nửa còn lại", remainingNumbers, "key-lesson-formula"));
    } else {
      display.append(element("p", "Khác parity. Bắt đầu chia đôi khối.", "key-lesson-formula"));
    }
  } else {
    const alice = retained.map((signal) => signal.alice).join("");
    const bob = cascade.corrected.join("");
    const matches = alice === bob;
    display.append(line("Chuỗi đối soát", `Alice ${alice} · Bob ${bob}`, "key-lesson-formula"));
    display.append(element("p", matches ? "Hai chuỗi minh họa đã khớp." : "Hai chuỗi minh họa còn khác nhau.", "key-lesson-detail"));
  }
}

function drawToeplitz(index = -1) {
  const done = index === matrix.length;
  const rows = matrix.map((row, i) => ({
    cells: [`Hàng ${i + 1}`, ...row, i <= index ? bobToeplitz[i] : "—"],
    className: i === index ? "is-active" : "",
    marked: i === index ? { [row.length + 1]: "is-highlighted" } : null,
  }));
  const columns = ["Ma trận T", ...retained.map(({ number }) => String(number)), "Đầu ra"];
  display.append(
    line("Seed công khai", toeplitzSeed.join(" ")),
    line("Đầu vào theo thứ tự cột", cascade.corrected.join(" ")),
    table("Ma trận Toeplitz với cột ghi số hiệu tín hiệu", columns, rows),
  );
  if (done) {
    display.append(line("Đầu ra", `Alice ${aliceToeplitz.join("")} · Bob ${bobToeplitz.join("")}`, "key-lesson-formula"));
    return;
  }
  if (index >= 0) {
    const products = matrix[index].map((bit, j) => `(${bit} × ${cascade.corrected[j]})`);
    display.append(line(`Bit ${index + 1}`, `${products.join(" ⊕ ")} = ${bobToeplitz[index]}`, "key-lesson-formula"));
  }
}

function render() {
  const step = steps[current];
  const label = `Bước ${current + 1} / ${steps.length}`;
  byId("key-lesson-counter").textContent = label;
  byId("key-lesson-step").textContent = step.title;
  byId("key-lesson-description").textContent = step.description;
  byId("key-lesson-note").textContent = step.note || "";
  byId("key-lesson-announcement").textContent = `${label}. ${step.title}.`;
  display.replaceChildren();
  step.draw();
  for (const button of stageButtons) {
    if (button.dataset.lessonStage === step.stage) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
  }
  back.disabled = restart.disabled = current === 0;
  next.disabled = current === steps.length - 1;
}

for (const button of stageButtons) {
  button.addEventListener("click", () => {
    current = steps.findIndex(({ stage }) => stage === button.dataset.lessonStage);
    render();
  });
}
back.addEventListener("click", () => { current -= 1; render(); });
next.addEventListener("click", () => { current += 1; render(); });
restart.addEventListener("click", () => { current = 0; render(); });
render();
