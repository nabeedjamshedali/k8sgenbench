"""Paper figures from evaluation/analysis/configs.csv (written by stats.py). Run stats.py first.

Usage: python evaluation/figures.py
  paper/figures/fig_dimensions_neutral.pdf     RQ1/RQ3: one panel per headline metric, one row per source
  paper/figures/fig_dimensions_production.pdf  same for the production prompt
  paper/figures/fig_prompt_effect.pdf          RQ5: neutral -> production per model (dumbbell)
Binary metrics: proportion with a 95% Wilson interval. Continuous: median with the interquartile range.
Palette: reference categorical slots 1-5 in fixed order (validated light: CVD worst adjacent dE 9.1, all checks
pass; contrast < 3:1 for 3 slots, so every row carries a text label and identity is never color-alone).
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(os.path.dirname(HERE), "paper", "figures")
SOURCES = ["human", "claude", "deepseek", "gemini", "gpt", "qwen"]
LABEL = {"human": "Human (shipped)", "claude": "Claude", "deepseek": "DeepSeek", "gemini": "Gemini",
         "gpt": "GPT", "qwen": "Qwen"}
COLOR = {"human": "#5f5e5a", "claude": "#2a78d6", "deepseek": "#eb6834", "gemini": "#1baf7a",
         "gpt": "#eda100", "qwen": "#e87ba4"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a65", "#e4e3df"
# (column, title, kind, higher_is_better)
PANELS = [("d1_accept_pct", "D1 correctness\nobjects accepted (%)", "cont", True),
          ("d2_kubescape_compliance", "D2 security\nKubescape score (%)", "cont", True),
          ("d2_pss_baseline", "D2 security\npasses PSS baseline (%)", "bin", True),
          ("d3_checklist_pct", "D3 reliability\nchecklist met (%)", "cont", True),
          ("d3_zhang_density_kloc", "D3 smells per KLOC\n(lower = better)", "cont", False),
          ("d4_pct", "D4 requirements\nmet (%)", "cont", True),
          ("d5_smoke", "D5 deployment\nsmoke passes (%)", "bin", True),
          ("d6_availability_mean", "D6 resilience\navailability (%)", "cont", True)]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": INK, "axes.titlesize": 8, "axes.titlecolor": INK})


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan, np.nan
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return 100 * p, 100 * (c - h), 100 * (c + h)


def summary(s, col, kind):
    v = s[col].dropna()
    if kind == "bin":
        v = v.astype(str).str.lower().map({"true": 1, "false": 0}).dropna()
        return (*wilson(int(v.sum()), len(v)), len(v))
    v = v.astype(float)
    if v.empty:
        return np.nan, np.nan, np.nan, 0
    return v.median(), v.quantile(.25), v.quantile(.75), len(v)


def style(ax):
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0)


def fig_dimensions(df, variant):
    sub = df[(df.prompt_variant == variant) | (df.source == "human")]
    present = [s for s in SOURCES if (sub.source == s).any()]
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.8), sharey=True)
    for ax, (col, title, kind, better) in zip(axes.flat, PANELS):
        for i, s in enumerate(present):
            mid, lo, hi, n = summary(sub[sub.source == s], col, kind)
            if n == 0 or np.isnan(mid):
                continue
            ax.plot([lo, hi], [i, i], color=COLOR[s], linewidth=2, solid_capstyle="round")
            ax.scatter([mid], [i], s=28, color=COLOR[s], edgecolor="white", linewidth=1.5, zorder=3)
        ax.set_title(title, loc="left", linespacing=1.3)
        ax.set_yticks(range(len(present)), [LABEL[s] for s in present])
        ax.set_ylim(len(present) - 0.5, -0.5)
        if kind == "bin" or col.endswith("pct") or "compliance" in col or "availability" in col:
            ax.set_xlim(-3, 103)
        else:
            ax.set_xlim(left=0)
        style(ax)
    fig.suptitle(f"Six-dimension results, {variant} prompt (dot = median or proportion; bar = IQR or 95% Wilson CI)",
                 x=0.01, ha="left", fontsize=8.5, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = os.path.join(FIG, f"fig_dimensions_{variant}.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"), dpi=200)
    plt.close(fig)
    return out


def fig_prompt_effect(df):
    llm = df[df.source.isin(SOURCES[1:])]
    present = [s for s in SOURCES[1:] if (llm.source == s).any()]
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.6), sharey=True)
    for ax, (col, title, kind, better) in zip(axes.flat, PANELS):
        for i, s in enumerate(present):
            pts = [summary(llm[(llm.source == s) & (llm.prompt_variant == v)], col, kind)[0]
                   for v in ("neutral", "production")]
            if any(np.isnan(p) for p in pts):
                continue
            ax.plot(pts, [i, i], color=GRID, linewidth=2, zorder=1)
            ax.scatter([pts[0]], [i], s=26, facecolor="white", edgecolor=COLOR[s], linewidth=1.5, zorder=3)
            ax.scatter([pts[1]], [i], s=26, color=COLOR[s], edgecolor="white", linewidth=1.5, zorder=3)
        ax.set_title(title, loc="left", linespacing=1.3)
        ax.set_yticks(range(len(present)), [LABEL[s] for s in present])
        ax.set_ylim(len(present) - 0.5, -0.5)
        if kind == "bin" or col.endswith("pct") or "compliance" in col or "availability" in col:
            ax.set_xlim(-3, 103)
        else:
            ax.set_xlim(left=0)
        style(ax)
    fig.suptitle("Prompt effect per model: open dot = neutral, filled dot = production (median or proportion)",
                 x=0.01, ha="left", fontsize=8.5, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = os.path.join(FIG, "fig_prompt_effect.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"), dpi=200)
    plt.close(fig)
    return out


def main():
    os.makedirs(FIG, exist_ok=True)
    df = pd.read_csv(os.path.join(HERE, "analysis", "configs.csv"))
    for out in (fig_dimensions(df, "neutral"), fig_dimensions(df, "production"), fig_prompt_effect(df)):
        print(out)


if __name__ == "__main__":
    main()
