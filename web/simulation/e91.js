"use strict";

(() => {
  const form = $("#e91-form");
  const parameters = $("#e91-parameters");
  const noise = $("#e91-noise");
  const noisy = $("#e91-noisy");
  const runButton = $("#e91-run");
  const compareButton = $("#e91-compare");
  const results = $("#e91-results");
  const comparison = $("#e91-comparison-result");
  const detailFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 6 });
  const exact = (value) => detailFormat.format(value);
  const bellStatuses = {
    violation: "Khoảng 95% nằm trên mốc cổ điển 2",
    at_or_below_bound: "Khoảng 95% nằm trong giới hạn cổ điển 2",
    inconclusive: "Chưa đủ bằng chứng vượt giới hạn cổ điển",
  };
  let lastResult = null;
  let lastComparison = null;

  function readSettings(noiseProbability = noisy.checked ? Number(noise.value) : 0) {
    return {
      signals: $("#e91-signals").valueAsNumber,
      seed: $("#e91-seed").valueAsNumber,
      noise_probability: noiseProbability,
    };
  }

  function updateControls() {
    noise.style.setProperty("--range-fill", `${100 * Number(noise.value)}%`);
    text("#e91-noise-value", formatPercent(Number(noise.value)));
    if (lastResult) updateRunContext("#e91-context", readSettings(), lastResult,
      `${formatNumber(lastResult.signals)} cặp · seed ${lastResult.seed} · nhiễu ${formatPercent(lastResult.noise_probability)}`);
    if (lastComparison) {
      const { ideal, noisy } = lastComparison;
      updateRunContext("#e91-comparison-context", readSettings(Number(noise.value)), noisy,
        `${formatNumber(ideal.signals)} cặp mỗi lượt · seed ${ideal.seed} · 0% và ${formatPercent(noisy.noise_probability)} nhiễu trắng`);
    }
  }

  function updateRunContext(selector, current, result, used) {
    const stale = Object.keys(current).some((key) => current[key] !== result[key]);
    text(selector, stale ? `Kết quả lần chạy trước (${used}). Chạy lại để áp dụng cấu hình mới.` : used);
    $(selector).classList.toggle("e91-stale", stale);
  }

  function renderRows(selector, pairs, calculation) {
    const rows = pairs.map((pair) => {
      const row = document.createElement("tr");
      const heading = document.createElement("th");
      heading.scope = "row";
      heading.textContent = `${pair.alice_angle}° / ${pair.bob_angle}°`;
      row.append(heading);
      for (const value of [pair.count, pair.pp, pair.pm, pair.mp, pair.mm]) {
        const cell = document.createElement("td");
        cell.textContent = formatNumber(value);
        row.append(cell);
      }
      const cell = document.createElement("td");
      const expression = document.createElement("code");
      expression.textContent = calculation(pair);
      cell.append(expression);
      row.append(cell);
      return row;
    });
    $(selector).replaceChildren(...rows);
  }

  function renderBell(bell) {
    const measured = finite(bell.s);
    const interval = measured ? `[${exact(bell.ci_low)} đến ${exact(bell.ci_high)}]` : "";
    renderRows("#e91-bell-rows", bell.pairs, (pair) => pair.count
      ? `(${pair.pp} + ${pair.mm} − ${pair.pm} − ${pair.mp}) / ${pair.count} = ${exact(pair.correlation)}`
      : "Không có mẫu");

    const terms = bell.pairs.map((pair, i) => {
      const sign = pair.sign < 0 ? "− " : i > 0 ? "+ " : "";
      return `${sign}(${finite(pair.correlation) ? exact(pair.correlation) : "thiếu mẫu"})`;
    });
    text("#e91-s-equation", measured
      ? `S ≈ ${terms.join(" ")} = ${exact(bell.s)} · |S| ≈ ${exact(bell.abs_s)}`
      : `S = ${terms.join(" ")} → chưa tính được`);
    text("#e91-s-interval", measured
      ? `Mỗi nhóm n lượt có bán kính Hoeffding √(2 ln(8/0,05) / n). Chặn từng khoảng trong [−1 đến 1], áp dấu của mỗi hạng, cộng các cận rồi quy về |S| ${interval}. Chặn hợp cho độ phủ đồng thời ít nhất 95%.`
      : "Cần dữ liệu của cả bốn tổ hợp góc để tính S và khoảng 95%.");
  }

  function renderQber(key) {
    const interval = key.count ? `[${formatPercent(key.ci_low)} đến ${formatPercent(key.ci_high)}]` : "";
    renderRows("#e91-key-rows", key.pairs, (pair) => `${pair.pp} + ${pair.mm} = ${pair.errors}`);

    const errors = key.pairs.map((pair) => pair.errors).join(" + ");
    const counts = key.pairs.map((pair) => pair.count).join(" + ");
    text("#e91-qber-equation", key.count
      ? `QBER = (${errors}) / (${counts}) = ${key.errors} / ${key.count} ≈ ${formatPercent(key.qber)}`
      : "QBER chưa xác định vì mẫu số bằng 0.");
    text("#e91-qber-interval", key.count
      ? `Khoảng Wilson 95% từ ${formatNumber(key.errors)} lỗi trên ${formatNumber(key.count)} cặp là ${interval}.`
      : "Cần ít nhất một cặp đo cùng hướng để tính khoảng Wilson.");
  }

  function renderLogs(result) {
    text("#e91-log-context", `${formatNumber(result.signals)} cặp · seed ${result.seed} · nhiễu ${formatPercent(result.noise_probability)}`);
    renderBell(result.bell);
    renderQber(result.key);
    $("#e91-logs").hidden = false;
  }

  function renderResult(result) {
    const { bell, key } = result;
    const bellCount = bell.pairs.reduce((sum, pair) => sum + pair.count, 0);
    text("#e91-s", formatNumber(bell.abs_s));
    text("#e91-s-expected", `Kỳ vọng |S| = ${formatNumber(Math.abs(bell.expected_s))}`);
    text("#e91-s-ci", finite(bell.s) ? `Khoảng 95% cho |S| [${exact(bell.ci_low)} đến ${exact(bell.ci_high)}]`
      : "Thiếu mẫu ở ít nhất một tổ hợp đo CHSH");
    text("#e91-s-status", bellStatuses[bell.status]);
    $("#e91-s-status").dataset.status = bell.status;
    text("#e91-qber", formatPercent(key.qber));
    text("#e91-qber-expected", `Kỳ vọng QBER = ${formatPercent(key.expected_qber)}`);
    text("#e91-qber-ci", key.count ? `Khoảng Wilson 95% [${formatPercent(key.ci_low)} đến ${formatPercent(key.ci_high)}]`
      : "Chưa có lượt đo cùng hướng");
    text("#e91-counts", `${formatNumber(bellCount)} cặp CHSH · ${formatNumber(key.count)} cặp cùng hướng · ${formatNumber(result.discarded_count)} cặp bỏ qua`);
    $("#e91-summary").hidden = false;
    $("#e91-counts").hidden = false;
    renderLogs(result);
    lastResult = result;
    updateControls();
  }

  function renderBar(id, value, format, note) {
    const bar = $(`#${id}`);
    const available = finite(value);
    const formattedValue = format(value);
    bar.hidden = !available;
    bar.value = available ? value : 0;
    bar.setAttribute("aria-valuetext", formattedValue);
    text(`#${id}-value`, formattedValue);
    text(`#${id}-note`, note);
  }

  function renderComparison(ideal, noisy) {
    for (const [mode, result] of Object.entries({ ideal, noisy })) {
      const { bell, key } = result;
      renderBar(`e91-compare-s-${mode}`, bell.abs_s, formatNumber, finite(bell.abs_s)
        ? `Khoảng 95% từ ${formatNumber(bell.ci_low)} đến ${formatNumber(bell.ci_high)}`
        : "Thiếu mẫu CHSH");
      renderBar(`e91-compare-qber-${mode}`, key.qber, formatPercent, key.count
        ? `${formatNumber(key.errors)} lỗi trên ${formatNumber(key.count)} cặp`
        : "Chưa có cặp đo cùng hướng");
    }
    comparison.hidden = false;
    lastComparison = { ideal, noisy };
    updateControls();
  }

  function setE91Busy(button, region, busy) {
    parameters.disabled = busy;
    (button === runButton ? compareButton : runButton).disabled = busy;
    region.setAttribute("aria-busy", String(busy));
    setBusy(button, busy);
  }

  form.addEventListener("input", updateControls);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (runButton.disabled) return;
    const settings = readSettings();
    showError("#e91-error", null);
    setE91Busy(runButton, results, true);
    try {
      renderResult(await request("/api/e91/simulate", settings));
    } catch (error) {
      showError("#e91-error", error);
    } finally {
      setE91Busy(runButton, results, false);
    }
  });
  compareButton.addEventListener("click", async () => {
    if (compareButton.disabled || !form.reportValidity()) return;
    const settings = readSettings(Number(noise.value));
    const region = $("#e91-comparison-context");
    showError("#e91-comparison-error", null);
    setE91Busy(compareButton, region, true);
    try {
      const [ideal, noisy] = await Promise.all([
        request("/api/e91/simulate", { ...settings, noise_probability: 0 }),
        request("/api/e91/simulate", settings),
      ]);
      renderComparison(ideal, noisy);
      region.focus();
    } catch (error) {
      showError("#e91-comparison-error", error);
      $("#e91-comparison-error").scrollIntoView({ block: "nearest" });
    } finally {
      setE91Busy(compareButton, region, false);
    }
  });
  for (const mode of ["ideal", "noisy"]) {
    $(`#e91-compare-log-${mode}`).addEventListener("click", () => {
      if (!lastComparison) return;
      renderLogs(lastComparison[mode]);
      $("#e91-log-context").focus();
    });
  }
  updateControls();
})();
