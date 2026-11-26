"""Plots derived exclusively from saved operational-comparison observations."""

import argparse
import json
from pathlib import Path


COLORS = {"bb84": "#2463a6", "e91": "#c16728"}
MODE_LABELS = {"equal_signals": "Cùng số tín hiệu/cặp", "equal_measurements": "Cùng số phép đo hai đầu"}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def plot_comparison(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = Path(output)
    manifest = _load(output / "manifest.json")
    rows = [row for row in _load(output / "summary.json") if row["policy"] != "qber_only_ablation"]
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.grid": True, "grid.alpha": .2,
                         "svg.fonttype": "none"})
    files = []

    def save(fig, name):
        if manifest["mode"] == "smoke":
            fig.suptitle("KIỂM TRA NHANH — KHÔNG DÙNG KẾT LUẬN NGHIÊN CỨU", color="#a32727", fontsize=10)
        fig.tight_layout()
        for extension in ("png", "svg"):
            path = figures / f"{name}.{extension}"
            fig.savefig(path, dpi=200, bbox_inches="tight")
            files.append(str(path.relative_to(output)).replace("\\", "/"))
        plt.close(fig)

    budgets = sorted({row["budget"] for row in rows if row["experiment"] == "key_yield"})
    fig, axes = plt.subplots(2, len(budgets), figsize=(5 * len(budgets), 7), squeeze=False)
    for mode_index, mode in enumerate(MODE_LABELS):
        for index, budget in enumerate(budgets):
            ax = axes[mode_index, index]
            for protocol in COLORS:
                group = sorted((r for r in rows if r["experiment"] == "key_yield" and r["budget_mode"] == mode
                                and r["budget"] == budget and r["protocol"] == protocol), key=lambda r: r["noise_probability"])
                values = [r["y_final_mean"] for r in group]
                low = [max(0., v - r["y_final_ci95"][0]) for v, r in zip(values, group)]
                high = [max(0., r["y_final_ci95"][1] - v) for v, r in zip(values, group)]
                ax.errorbar([100 * r["noise_probability"] for r in group], values, yerr=[low, high],
                            marker="o", capsize=3, color=COLORS[protocol], label=protocol.upper())
            ax.set(title=f"{MODE_LABELS[mode]} · B={budget:,}", xlabel="QBER kỳ vọng khi không can thiệp (%)",
                   ylabel="Toeplitz (bit / mọi phiên thử)", ylim=(0, None))
            ax.legend()
    save(fig, "key_yield")

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    detection_noise = min(r["noise_probability"] for r in rows if r["experiment"] == "detection")
    for ax, metric, title in zip(axes.flat,
                                ("alarm", "missed_intervention", "aborted", "ready"),
                                ("Báo bất thường", "Can thiệp nhưng qua giám sát", "Dừng trước cấp khóa", "Cấp khóa thành công")):
        for protocol in COLORS:
            group = sorted((r for r in rows if r["experiment"] == "detection" and r["protocol"] == protocol
                            and r["noise_probability"] == detection_noise and r[metric + "_rate"] is not None),
                           key=lambda r: r["disturbance_fraction"])
            values = [r[metric + "_rate"] * 100 for r in group]
            interval = [r[metric + "_ci95"] for r in group]
            ax.errorbar([100 * r["disturbance_fraction"] for r in group], values,
                        yerr=[[max(0., value - 100 * ci[0]) for value, ci in zip(values, interval)],
                              [max(0., 100 * ci[1] - value) for value, ci in zip(values, interval)]],
                        marker="o", capsize=3, label=protocol.upper(), color=COLORS[protocol])
        ax.set(title=title, xlabel="Tỷ lệ can thiệp của từng mô hình (%)", ylabel="Tỷ lệ phiên (%)", ylim=(-2, 102))
        ax.legend()
    fig.text(.5, -.01, "f không biểu diễn hai tấn công tương đương; thanh sai số: Wilson 95%.", ha="center")
    save(fig, "detection")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, mode in zip(axes, MODE_LABELS):
        for protocol in COLORS:
            group = sorted((r for r in rows if r["experiment"] == "noise" and r["protocol"] == protocol
                            and r["budget_mode"] == mode), key=lambda r: r["noise_probability"])
            for metric, style in (("monitor_pass", "--"), ("ready", "-")):
                ax.plot([100 * r["noise_probability"] for r in group], [100 * r[metric + "_rate"] for r in group],
                        style, marker="o", color=COLORS[protocol], label=f"{protocol.upper()} · {'qua giám sát' if metric == 'monitor_pass' else 'có khóa'}")
        ax.set(title=MODE_LABELS[mode], xlabel="QBER kỳ vọng (%)", ylabel="Tỷ lệ phiên (%)", ylim=(-2, 102))
        ax.legend(fontsize=8)
    save(fig, "noise_tolerance")

    target_budget = 8192 if 8192 in budgets else budgets[0]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, mode in zip(axes, MODE_LABELS):
        for protocol in COLORS:
            row = next(r for r in rows if r["experiment"] == "key_yield" and r["budget"] == target_budget
                       and r["noise_probability"] == 0 and r["protocol"] == protocol and r["budget_mode"] == mode)
            fields = ("sifted_bits_mean", "retained_bits_mean", "after_cascade_bits_per_attempt_mean",
                      "after_confirmation_bits_per_attempt_mean", "y_final_mean")
            ax.plot(range(5), [row[field] for field in fields], marker="o", color=COLORS[protocol], label=protocol.upper())
        ax.set_xticks(range(5), ("Sàng lọc", "Loại mẫu", "Cascade", "Xác nhận", "Toeplitz"), rotation=20)
        ax.set(title=f"{MODE_LABELS[mode]} · B={target_budget:,} · p=0", ylabel="Bit trung bình / mọi phiên thử", ylim=(0, None))
        ax.legend()
    fig.text(.5, -.03, "Cascade và xác nhận giữ nguyên độ dài chuỗi; parity/digest bị trừ vào ngân sách entropy.\nGiai đoạn chưa chạy tính 0; không diễn giải là khóa bí mật đã chứng minh.", ha="center", fontsize=9)
    save(fig, "key_stages")

    ablations = _load(output / "chsh_ablation.json")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, mode in zip(axes, MODE_LABELS):
        group = sorted((r for r in ablations if r["experiment"] == "key_yield" and r["budget_mode"] == mode
                        and r["noise_probability"] == 0), key=lambda r: r["budget"])
        ax.bar([str(r["budget"]) for r in group], [100 * r["additional_monitor_aborts"] / r["paired_sessions"] for r in group], color=COLORS["e91"])
        ax.set(title=f"E91 · {MODE_LABELS[mode]} · p=0", xlabel="Ngân sách B", ylabel="Dừng giám sát thêm do CHSH (%)", ylim=(0, 100))
    save(fig, "chsh_ablation")
    return files


def plot_system(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = Path(output)
    rows = _load(output / "summary.json")
    size = max(row["payload_bytes"] for row in rows)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, field, title in zip(axes.flat,
                                ("key_setup_seconds", "payload_mib_per_second", "combined_cpu_one_core_percent", "combined_rss_sampled_peak_bytes"),
                                ("Thiết lập khóa (s)", "Thông lượng sau cấp khóa (MiB/s)", "CPU hai tiến trình (% một lõi)", "Đỉnh RSS lấy mẫu (MiB)")):
        for offset, protocol in ((-.18, "bb84"), (.18, "e91")):
            group = [next(r for r in rows if r["protocol"] == protocol and r["budget_mode"] == mode and r["payload_bytes"] == size)
                     for mode in MODE_LABELS]
            values = [r[field + "_median"] for r in group]
            values = [v / (1024 ** 2) if field.endswith("bytes") and v is not None else v for v in values]
            ax.bar([i + offset for i in range(2)], values, width=.34, color=COLORS[protocol], label=protocol.upper())
        ax.set_xticks([0, 1], list(MODE_LABELS.values()))
        ax.set(title=title, ylim=(0, None))
        ax.legend()
        ax.grid(axis="y", alpha=.2)
    fig.suptitle(f"TCP vòng lặp, hai tiến trình · tệp {size / 1024 ** 2:g} MiB · trung vị")
    fig.tight_layout()
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    files = []
    for extension in ("png", "svg"):
        path = figures / f"system_performance.{extension}"
        fig.savefig(path, dpi=200, bbox_inches="tight")
        files.append(str(path.relative_to(output)))
    plt.close(fig)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--system", action="store_true")
    args = parser.parse_args()
    print("\n".join(plot_system(args.output) if args.system else plot_comparison(args.output)))


if __name__ == "__main__":
    main()
