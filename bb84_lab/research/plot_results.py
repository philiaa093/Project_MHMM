"""Tạo năm nhóm biểu đồ từ dữ liệu study đã đo, không sinh số liệu giả."""

import argparse
import json
from pathlib import Path
import sys

from bb84_lab.bb84 import expected_qber


def plot_study(directory):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    directory = Path(directory)
    data = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    if not all(name in data for name in ("main_summary", "evaluation_summary", "paired_summary")):
        raise ValueError("Thiếu dữ liệu tổng hợp study")
    figures = directory / "figures"
    figures.mkdir(exist_ok=True)
    main, evaluation, paired = data["main_summary"], data["evaluation_summary"], data["paired_summary"]
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
        "axes.spines.right": False, "axes.titleweight": "bold", "figure.facecolor": "white",
        "axes.prop_cycle": plt.cycler(color=["#087f8c", "#315a90", "#e39d36", "#b44867"]),
    })
    outputs = []

    def save(fig, filename, name):
        fig.text(.01, .005, "Classical simulation; Wilson 95% monitoring intervals; no physical QKD security claim.",
                 fontsize=8, color="#555555")
        fig.tight_layout(rect=(0, .025, 1, .95))
        for extension in ("png", "svg"):
            fig.savefig(figures / f"{filename}.{extension}", dpi=160)
        plt.close(fig)
        outputs.append({"name": name, "file": f"figures/{filename}.png", "svg": f"figures/{filename}.svg"})

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("1. Sample QBER versus intercept-resend fraction", fontsize=16, fontweight="bold")
    for ax, p in zip(axes.flat, (0, .01, .03, .05)):
        for n in (1024, 4096, 16384):
            rows = sorted((r for r in main if r["signals"] == n and r["noise_probability"] == p), key=lambda r: r["eve_fraction"])
            ax.errorbar([r["eve_fraction"] for r in rows], [100 * r["qber_mean"] for r in rows],
                        yerr=[100 * (r["qber_stdev"] or 0) for r in rows], marker="o", capsize=3,
                        label=f"N={n}; mean +/- SD")
        fractions = [0, .1, .25, .5, 1]
        ax.plot(fractions, [100 * expected_qber(f, p) for f in fractions], "k--", alpha=.6, label="Model expectation")
        ax.set(title=f"Background bit-flip p={p:.0%}", xlabel="Eve fraction f", ylabel="Sample QBER (%)")
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    save(fig, "01_qber", "QBER theo mức can thiệp và nhiễu")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("2. Anomaly detection versus number of signals", fontsize=16, fontweight="bold")
    for ax, p in zip(axes.flat, (0, .01, .03, .05)):
        for f in (.1, .25, .5, 1):
            rows = sorted((r for r in main if r["eve_fraction"] == f and r["noise_probability"] == p), key=lambda r: r["signals"])
            xs, ys = [r["signals"] for r in rows], [100 * r["anomalous_rate"] for r in rows]
            ax.plot(xs, ys, "o-", label=f"f={f:g}")
            ax.fill_between(xs, [100 * r["anomalous_ci95"][0] for r in rows],
                            [100 * r["anomalous_ci95"][1] for r in rows], alpha=.1)
        ax.set(title=f"p={p:.0%}", xlabel="Signals N", ylabel="Anomalous sessions (%)", ylim=(-3, 103))
        ax.set_xscale("log", base=2)
        ax.set_xticks([1024, 4096, 16384], ["1,024", "4,096", "16,384"])
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    save(fig, "02_detection", "Phát hiện theo số tín hiệu")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("3. No-Eve alarms and inconclusive sessions", fontsize=16, fontweight="bold")
    for ax, status, title in zip(axes, ("anomalous", "inconclusive"), ("Anomalous without Eve", "Inconclusive without Eve")):
        for n in (1024, 4096, 16384):
            rows = sorted((r for r in main if r["signals"] == n and r["eve_fraction"] == 0), key=lambda r: r["noise_probability"])
            xs = [100 * r["noise_probability"] for r in rows]
            ax.plot(xs, [100 * r[f"{status}_rate"] for r in rows], "o-", label=f"N={n}")
            ax.fill_between(xs, [100 * r[f"{status}_ci95"][0] for r in rows],
                            [100 * r[f"{status}_ci95"][1] for r in rows], alpha=.1)
        ax.set(title=title, xlabel="Background bit-flip p (%)", ylabel="Sessions (%)", ylim=(-3, 103))
        ax.grid(alpha=.2)
        ax.legend()
    save(fig, "03_no_eve", "Báo động và chưa đủ bằng chứng khi không có Eve")

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.suptitle("4. Material remaining through monitoring stages", fontsize=16, fontweight="bold")
    rows = sorted((r for r in main if r["signals"] == 4096 and r["noise_probability"] == 0), key=lambda r: r["eve_fraction"])
    for field, label in (("sifted_mean", "After basis sifting"), ("remaining_mean", "After removing public sample"), ("y_pre_mean", "Y_pre; zero when aborted")):
        ax.plot([r["eve_fraction"] for r in rows], [r[field] for r in rows], "o-", label=label)
    final_rows = sorted((r for r in data.get("postprocessing_summary", [])
                         if r["dataset"] == "main" and r["signals"] == 4096 and r["noise_probability"] == 0
                         and r["sample_fraction"] == .25), key=lambda r: r["eve_fraction"])
    if final_rows:
        ax.plot([r["eve_fraction"] for r in final_rows], [r["y_final_mean"] for r in final_rows], "o-", label="Measured Y_final; educational model")
    ax.set(xlabel="Eve fraction f", ylabel="Mean bits per input session",
           title="N=4,096; p=0; sample=25%. " + ("Y_final uses the declared educational entropy budget." if final_rows else "Y_final is not measured here."))
    ax.grid(alpha=.2)
    ax.legend()
    save(fig, "04_retention", "Vật liệu khóa qua sàng lọc và giám sát")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("5. Held-out paired comparison: 10%, 25%, 50% sampling", fontsize=16, fontweight="bold")
    for ax, f, field, title, scale in (
        (axes[0, 0], 0, "y_pre_mean", "No-Eve preprocessing yield", 1),
        (axes[0, 1], .5, "anomalous_rate", "Strong interference f=0.5", 100),
        (axes[1, 0], .1, "anomalous_rate", "Weak interference f=0.1", 100),
    ):
        for alpha in (.1, .25, .5):
            rows = sorted((r for r in evaluation if r["eve_fraction"] == f and r["sample_fraction"] == alpha), key=lambda r: r["noise_probability"])
            ax.plot([100 * r["noise_probability"] for r in rows], [scale * r[field] for r in rows], "o-", label=f"sample={alpha:.0%}")
            if scale == 100:
                ax.fill_between([100 * r["noise_probability"] for r in rows],
                                [100 * r["anomalous_ci95"][0] for r in rows],
                                [100 * r["anomalous_ci95"][1] for r in rows], alpha=.1)
        ax.set(title=title, xlabel="Background p (%)", ylabel="Mean Y_pre (bits)" if scale == 1 else "Anomalous sessions (%)")
        if scale == 100:
            ax.set_ylim(-3, 103)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    ax = axes[1, 1]
    for offset, p in ((-.03, 0), (.03, .01)):
        rows = sorted((r for r in paired if r["eve_fraction"] == 0 and r["noise_probability"] == p), key=lambda r: r["sample_fraction"])
        means = [r["mean_difference"] for r in rows]
        ax.errorbar([r["sample_fraction"] + offset for r in rows], means,
                    yerr=[[max(0, r["mean_difference"] - r["ci95"][0]) for r in rows],
                          [max(0, r["ci95"][1] - r["mean_difference"]) for r in rows]],
                    fmt="o", capsize=5, label=f"f=0; p={p:.0%}")
    ax.axhline(0, color="black", linestyle="--", alpha=.5)
    ax.set(title="Paired Y_pre difference versus B0", xlabel="Sample fraction", ylabel="Difference (bits); bootstrap 95% CI")
    ax.set_xticks([.1, .25, .5], ["10%", "25%", "50%"])
    ax.grid(alpha=.2)
    ax.legend(fontsize=8)
    save(fig, "05_comparison", "Đối sánh ghép cặp trên bộ đánh giá độc lập")
    return outputs


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        figures = plot_study(args.directory)
    except (OSError, ValueError, ImportError) as error:
        parser.exit(2, f"Lỗi: {error}\n")
    print(f"Đã tạo {len(figures)} nhóm biểu đồ PNG và SVG tại {args.directory / 'figures'}")


if __name__ == "__main__":
    main()
