"""Export print-friendly latency figures in vector PDF and 300 DPI PNG."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

STYLE = {
    "rule_based": ("Java rule-based", "o", "-"),
    "llm": ("Local Qwen LLM", "s", "--"),
}
COLORS = dict(zip(STYLE, sns.color_palette("colorblind", 2)))


def save(fig, path):
    for suffix in (".pdf", ".png"):
        fig.savefig(Path(path).with_suffix(suffix), dpi=300, bbox_inches="tight")


def create_figures(evaluation, summary, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    paths = [output_dir / "fig1_latency_vs_load", output_dir / "fig2_distribution_boxplot"]

    fig, ax = plt.subplots(figsize=(7.4, 4.6), layout="constrained")
    for system, (label, marker, linestyle) in STYLE.items():
        rows = summary.loc[
            summary["scope"].eq("matched_load") & summary["system"].eq(system)
        ].sort_values("concurrency")
        point = rows["median_ms"].to_numpy()
        bounds = rows[["median_ci_low_ms", "median_ci_high_ms"]].to_numpy().T
        errors = np.maximum(0, np.array([point - bounds[0], bounds[1] - point]))
        ax.errorbar(rows["concurrency"], point, yerr=errors, color=COLORS[system],
                    label=label, marker=marker, linestyle=linestyle, capsize=5)
    ax.set(yscale="log", xlabel="Concurrent requests (count)", ylabel="Median latency (ms)",
           title="Response latency by concurrent load", xticks=[1, 2])
    ax.legend(title="Median with 95% bootstrap CI")
    fig.text(0.02, -0.025, "Same 24 queries at both loads. Timings include successful requests only.", fontsize=9)
    save(fig, paths[0])
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.4, 4.6), layout="constrained")
    primary = evaluation.loc[evaluation["concurrency"].eq(1) & evaluation["success"]]
    for index, (system, (label, marker, linestyle)) in enumerate(STYLE.items(), 1):
        values = primary.loc[primary["system"].eq(system), "latency_ms"]
        row = summary.loc[summary["scope"].eq("primary") & summary["system"].eq(system)].iloc[0]
        ax.boxplot(values, positions=[index], widths=0.32, manage_ticks=False,
                   boxprops={"color": COLORS[system], "linestyle": linestyle},
                   medianprops={"color": "black"},
                   flierprops={"marker": marker, "markersize": 3,
                               "markeredgecolor": COLORS[system], "alpha": 0.6})
        point = row["median_ms"]
        ax.errorbar(index + 0.23, point,
                    yerr=[[max(0, point - row["median_ci_low_ms"])],
                          [max(0, row["median_ci_high_ms"] - point)]],
                    color=COLORS[system], marker=marker, capsize=4, linestyle="none")
    ax.set(yscale="log", ylabel="Response latency (ms)", xlabel="Assistant (category)",
           title="Distribution of response times at concurrency 1")
    ax.set_xticks([1, 2], [style[0] for style in STYLE.values()])
    ax.set_xlim(0.55, 2.55)
    fig.text(0.02, -0.045,
             "Boxes show Q1–Q3. Whiskers use 1.5 × IQR. Side markers show medians with 95% CIs.",
             fontsize=9)
    save(fig, paths[1])
    plt.close(fig)
    return [path.with_suffix(".png") for path in paths]


if __name__ == "__main__":
    from process_data import ROOT, load_evaluation, summarize

    _, data = load_evaluation(ROOT / "data/raw/test_run.jsonl")
    create_figures(data, summarize(data), ROOT / "reports/figures")
