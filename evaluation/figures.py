"""Paper figures from evaluation/analysis/configs.csv (written by stats.py). Run stats.py first.

Usage: python evaluation/figures.py
  paper/figures/fig_dimensions_neutral.pdf  RQ1: one panel per headline metric, one row per source (neutral prompt)
  paper/figures/fig_attrition.pdf           RQ4: share of configurations surviving each pipeline stage, per model
  paper/figures/fig_tradeoff.pdf            RQ5: static security vs smoke-test pass rate, neutral -> production
  paper/figures/fig_static_runtime.pdf      RQ4: smoke-test pass rate by quintile of a static score, per prompt
Binary metrics: proportion with a 95% Wilson interval. Continuous: median with the interquartile range.
Palette: reference categorical slots 1-5 in fixed order (validated light: CVD worst adjacent dE 9.1, all checks
pass; contrast < 3:1 for 3 slots, so every series carries a text label and identity is never color-alone).
Prompt is encoded by marker fill (open = neutral, filled = production), never by a sixth hue.
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
MODELS = SOURCES[1:]
LABEL = {"human": "Human (shipped)", "claude": "Claude", "deepseek": "DeepSeek", "gemini": "Gemini",
         "gpt": "GPT", "qwen": "Qwen"}
COLOR = {"human": "#5f5e5a", "claude": "#2a78d6", "deepseek": "#eb6834", "gemini": "#1baf7a",
         "gpt": "#eda100", "qwen": "#e87ba4"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a65", "#e4e3df"
# (column, title, kind) -- D1 and D4 are omitted: every source's median is 96-100%, so their panels carry no contrast
PANELS = [("d2_kubescape_compliance", "D2 Kubescape compliance (%)", "cont"),
          ("d3_checklist_pct", "D3 reliability checklist (%)", "cont"),
          ("d3_zhang_density_kloc", "D3 smells/KLOC (lower = better)", "cont"),
          ("d5_ready", "D5 fully Ready (%)", "bin"),
          ("d5_smoke", "D5 smoke test passes (%)", "bin"),
          ("d6_recovery_time_mean", "D6 recovery time (s)", "cont")]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": INK, "axes.titlesize": 8, "axes.titlecolor": INK})


def boolcol(s):
    return s.astype(str).str.lower().map({"true": 1, "false": 0, "1": 1, "0": 0, "1.0": 1, "0.0": 0})


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
        v = boolcol(v).dropna()
        return (*wilson(int(v.sum()), len(v)), len(v))
    v = v.astype(float)
    if v.empty:
        return np.nan, np.nan, np.nan, 0
    return v.median(), v.quantile(.25), v.quantile(.75), len(v)


def style(ax, grid="x"):
    ax.grid(axis=grid, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if grid == "x":
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0)


def save(fig, name):
    out = os.path.join(FIG, name)
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"), dpi=200)
    plt.close(fig)
    return out


def fig_dimensions(df, variant):
    sub = df[(df.prompt_variant == variant) | (df.source == "human")]
    present = [s for s in SOURCES if (sub.source == s).any()]
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 3.9), sharey=True)
    for ax, (col, title, kind) in zip(axes.flat, PANELS):
        lo_all, hi_all = [], []
        for i, s in enumerate(present):
            mid, lo, hi, n = summary(sub[sub.source == s], col, kind)
            if n == 0 or np.isnan(mid):
                continue
            ax.plot([lo, hi], [i, i], color=COLOR[s], linewidth=2, solid_capstyle="round")
            ax.scatter([mid], [i], s=30, color=COLOR[s], edgecolor="white", linewidth=1.5, zorder=3)
            lo_all.append(lo); hi_all.append(hi)
            if s == "human":  # reference line: the shipped manifests' value
                ax.axvline(mid, color=MUTED, linewidth=0.8, linestyle=(0, (3, 2)), zorder=0)
        ax.set_title(title, loc="left")
        ax.set_yticks(range(len(present)), [LABEL[s] for s in present])
        ax.set_ylim(len(present) - 0.5, -0.5)
        if kind == "bin":
            ax.set_xlim(-3, 103)
        else:  # metric-specific range, so differences between sources are not compressed into a few pixels
            pad = 0.08 * (max(hi_all) - min(lo_all) or 1)
            ax.set_xlim(max(0, min(lo_all) - pad), max(hi_all) + pad)
        style(ax)
    fig.tight_layout()
    return save(fig, f"fig_dimensions_{variant}.pdf")


STAGES = [("generated", "Generated"), ("d1_parse_ok", "Parses"), ("d1_schema_ok", "Schema\nvalid"),
          ("d1_server_ok", "API\naccepted"), ("d5_ready", "Fully\nReady"), ("d5_smoke", "Smoke\ntest"),
          ("both", "Ready +\nsmoke")]


def fig_attrition(df):
    d = df.copy()
    for c, _ in STAGES[1:-1]:
        d[c] = boolcol(d[c]).fillna(0)
    d["generated"] = 1
    d["both"] = d.d5_ready * d.d5_smoke
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=True)
    x = np.arange(len(STAGES))
    hum = d[d.source == "human"]
    href = [100 * hum[c].mean() for c, _ in STAGES]
    for ax, v in zip(axes, ("neutral", "production")):
        ax.plot(x, href, color=COLOR["human"], linewidth=1.2, linestyle=(0, (3, 2)), zorder=1)
        ends = [(href[-1], "human", len(hum))]
        for m in MODELS:
            g = d[(d.source == m) & (d.prompt_variant == v)]
            if g.empty:
                continue
            y = [100 * g[c].mean() for c, _ in STAGES]
            ax.plot(x, y, color=COLOR[m], linewidth=2, zorder=2)
            ax.scatter(x, y, s=16, edgecolor=COLOR[m], linewidth=1.2, zorder=3,
                       facecolor="white" if v == "neutral" else COLOR[m])
            ends.append((y[-1], m, len(g)))
        # direct labels at the right end, nudged apart so they never overlap
        ends.sort()
        placed = []
        for yv, m, n in ends:
            yy = yv
            while any(abs(yy - p) < 4.5 for p in placed):
                yy += 4.5
            placed.append(yy)
            ax.text(x[-1] + 0.15, yy, "Human" if m == "human" else f"{LABEL[m]} (n={n})",
                    color=MUTED if m == "human" else INK, va="center", fontsize=7)
        ax.set_title(f"{v.capitalize()} prompt", loc="left")
        ax.set_xticks(x, [l.replace("\n", " ") for _, l in STAGES], fontsize=7, rotation=35, ha="right",
                      rotation_mode="anchor")
        ax.set_xlim(-0.3, len(STAGES) + 1.1)
        ax.set_ylim(0, 104)
        style(ax, grid="y")
    axes[0].set_ylabel("Share of configurations (%)")
    fig.tight_layout()
    return save(fig, "fig_attrition.pdf")


def fig_tradeoff(df):
    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    pts = {}
    for m in MODELS:
        for v in ("neutral", "production"):
            g = df[(df.source == m) & (df.prompt_variant == v)]
            kx = g.d2_kubescape_compliance.dropna().astype(float).median()
            y, lo, hi = wilson(int(boolcol(g.d5_smoke).fillna(0).sum()), len(g))[:3]
            pts[(m, v)] = (kx, y, lo, hi)
    # coincident points (identical median and rate) are offset horizontally so neither marker hides the other
    seen = {}
    for k in sorted(pts):
        kx, y, lo, hi = pts[k]
        key = (round(kx, 1), round(y, 1))
        if key in seen:
            pts[k] = (kx + 0.7 * seen[key], y, lo, hi)
        seen[key] = seen.get(key, 0) + 1
    for m in MODELS:
        (x0, y0, l0, h0), (x1, y1, l1, h1) = pts[(m, "neutral")], pts[(m, "production")]
        for (xx, yy, lo, hi) in ((x0, y0, l0, h0), (x1, y1, l1, h1)):
            ax.plot([xx, xx], [lo, hi], color=COLOR[m], linewidth=0.8, alpha=0.45, zorder=1)
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=COLOR[m], lw=1.6, shrinkA=4, shrinkB=4), zorder=2)
        ax.scatter([x0], [y0], s=34, facecolor="white", edgecolor=COLOR[m], linewidth=1.6, zorder=3)
        ax.scatter([x1], [y1], s=34, color=COLOR[m], edgecolor="white", linewidth=1.2, zorder=3)
        ax.text(x1 + 0.6, y1, LABEL[m], fontsize=7, color=INK, va="center")
    h = df[df.source == "human"]
    hx = h.d2_kubescape_compliance.astype(float).median()
    hy = wilson(int(boolcol(h.d5_smoke).sum()), len(h))[0]
    ax.scatter([hx], [hy], marker="D", s=30, color=COLOR["human"], zorder=3)
    ax.text(hx - 0.6, hy, "Human", fontsize=7, color=MUTED, va="center", ha="right")
    ax.set_xlabel("Median Kubescape compliance (%)")
    ax.set_ylabel("Smoke test passes (%)")
    ax.set_ylim(20, 100)
    style(ax, grid="both")
    fig.tight_layout()
    return save(fig, "fig_tradeoff.pdf")


def fig_static_runtime(df):
    llm = df[df.source.isin(MODELS)].copy()
    llm["smoke"] = boolcol(llm.d5_smoke).fillna(0)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=True)
    for ax, (col, lab) in zip(axes, (("d3_polaris_score", "Polaris score quintile"),
                                     ("d2_kubescape_compliance", "Kubescape compliance quintile"))):
        for v, face in (("neutral", "white"), ("production", INK)):
            g = llm[llm.prompt_variant == v].dropna(subset=[col])
            q = pd.qcut(g[col].astype(float).rank(method="first"), 5, labels=False)
            xs, ys, los, his = [], [], [], []
            for k in range(5):
                s = g[q == k].smoke
                y, lo, hi = wilson(int(s.sum()), len(s))[:3]
                xs.append(k + (-0.08 if v == "neutral" else 0.08)); ys.append(y); los.append(lo); his.append(hi)
            ax.vlines(xs, los, his, color=INK, linewidth=0.8, alpha=0.5)
            ax.plot(xs, ys, color=INK, linewidth=1.2, linestyle="-" if v == "production" else (0, (3, 2)))
            ax.scatter(xs, ys, s=26, facecolor=face, edgecolor=INK, linewidth=1.2, zorder=3,
                       label=f"{v.capitalize()} prompt")
        ax.set_xticks(range(5), ["Q1\n(lowest)", "Q2", "Q3", "Q4", "Q5\n(highest)"])
        ax.set_xlabel(lab)
        ax.set_ylim(0, 105)
        style(ax, grid="y")
    axes[0].set_ylabel("Smoke test passes (%)")
    axes[0].legend(frameon=False, loc="lower left", fontsize=7)
    fig.tight_layout()
    return save(fig, "fig_static_runtime.pdf")


def main():
    os.makedirs(FIG, exist_ok=True)
    df = pd.read_csv(os.path.join(HERE, "analysis", "configs.csv"))
    for stale in ("fig_dimensions_production", "fig_prompt_effect"):  # replaced by fig_tradeoff / dropped
        for ext in (".pdf", ".png"):
            p = os.path.join(FIG, stale + ext)
            if os.path.exists(p):
                os.remove(p)
    for out in (fig_dimensions(df, "neutral"), fig_attrition(df), fig_tradeoff(df), fig_static_runtime(df)):
        print(out)


if __name__ == "__main__":
    main()
