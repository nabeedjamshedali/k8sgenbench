"""Robustness analyses requested in review: tests that respect clustering by project and by (model, project) cell.

Writes evaluation/analysis/robust_report.md. Uses stats.load(), so every value comes from the same flattened results as
report.md. Sections:
  A  RQ5 paired at the (model, project) cell: per-cell mean under each prompt, Wilcoxon over cells (the sample index k
     carries no meaning across prompts, so pairing by k is replaced), Holm across the five models.
  B  RQ1 project level (n <= 7 project pairs per model), Holm across the five models per metric.
  C  RQ3 blocked on project: Friedman test over the five common projects, Kendall's W.
  D  RQ4 logistic regression of each runtime outcome on a standardised static score, with prompt and project fixed
     effects and cluster-robust (model x project) sandwich standard errors; also within-prompt correlations.
  E  D6 availability and absolute downtime stratified by the replica count of the faulted workload.
  F  Sensitivity of D5 to the deployment-time adjustments (image aliases, start-up shims): worst-case bound.
"""
import glob
import json
import os

import numpy as np
import pandas as pd
from scipy import stats as st

import stats as S

OUT = os.path.join(S.OUT, "robust_report.md")
MODELS = S.MODELS
STATIC = [("d2_kubescape_compliance", "Kubescape compliance"), ("d3_checklist_pct", "Checklist coverage"),
          ("d3_polaris_score", "Polaris score"), ("d3_zhang_density_kloc", "KubeLinter smells/KLOC"),
          ("d4_pct", "Requirements met")]


def cell_means(df, col):
    llm = df[df.source.isin(MODELS)].copy()
    llm[col] = pd.to_numeric(llm[col], errors="coerce").astype(float)
    return llm.pivot_table(index=["source", "project_id"], columns="prompt_variant", values=col, aggfunc="mean")


def sec_a(df, L):
    L.append("\n## A. RQ5 paired at the (model, project) cell\n")
    L.append("Per-cell mean over the samples of each prompt (binary outcomes become per-cell rates); Wilcoxon signed-rank "
             "over cells (zero differences dropped, as in Wilcoxon's original procedure). Per-model p-values are "
             "Holm-adjusted across the five models.\n")
    L.append("| metric | all cells: n, median Δ (prod−neutral), p | " + " | ".join(MODELS) + " |")
    L.append("|---|---|" + "---|" * len(MODELS))
    cols = [(c, l) for c, l in S.CONTINUOUS if not c.startswith("d1_")] + \
           [(c, l) for c, l in S.BINARY if c in ("d2_pss_restricted", "d5_ready", "d5_smoke")]
    for c, lab in cols:
        pv = cell_means(df, c)
        if "neutral" not in pv or "production" not in pv:
            continue
        pv = pv[["neutral", "production"]].dropna()
        d = pv.production - pv.neutral

        def test(x):
            x = x[x != 0]
            return st.wilcoxon(x).pvalue if len(x) >= 3 else None
        p_all = test(d)
        per, ps = [], []
        for m in MODELS:
            dm = d[d.index.get_level_values(0) == m]
            per.append((len(dm), dm.median() if len(dm) else np.nan))
            ps.append(test(dm))
        idx = [i for i, p in enumerate(ps) if p is not None]
        adj = dict(zip(idx, S.holm([ps[i] for i in idx]))) if idx else {}
        cells = [f"n={n} Δ={md:+.2f} p={S.fmt_p(adj[i])}" if i in adj else f"n={n} Δ={md:+.2f}"
                 for i, (n, md) in enumerate(per)]
        scale = 100 if c in dict(S.BINARY) else 1
        L.append(f"| {lab} | n={len(d)} Δ={d.median() * scale:+.2f}{' pp' if scale == 100 else ''} "
                 f"p={S.fmt_p(p_all) if p_all is not None else 'n/a'} | " + " | ".join(cells) + " |")
    # the paired binary counts at cell level, for the text
    for c in ("d5_ready", "d5_smoke"):
        pv = cell_means(df, c)[["neutral", "production"]].dropna()
        L.append(f"\n{c}: cells where the production rate is lower {int((pv.production < pv.neutral).sum())}, "
                 f"higher {int((pv.production > pv.neutral).sum())}, equal {int((pv.production == pv.neutral).sum())} "
                 f"(of {len(pv)})")


def sec_b(df, L):
    L.append("\n## B. RQ1 at project level, Holm-adjusted across the five models\n")
    L.append("Mean over the neutral samples of each project, paired with that project's human manifest; Wilcoxon signed-rank.\n")
    L.append("| metric | " + " | ".join(MODELS) + " |\n|---|" + "---|" * len(MODELS))
    neu = df[df.prompt_variant == "neutral"]
    hum = df[df.source == "human"].set_index("project_id")
    for c, lab in S.CONTINUOUS + S.BINARY:
        res, ps = [], []
        for m in MODELS:
            pm = neu[neu.source == m].groupby("project_id")[c].apply(lambda v: pd.to_numeric(v, errors="coerce").mean())
            both = pd.concat([pm, pd.to_numeric(hum[c], errors="coerce")], axis=1, keys=["m", "h"]).dropna()
            diff = both.m - both.h
            if len(both) < 3 or (diff == 0).all():
                res.append((len(both), diff.median() if len(both) else np.nan)); ps.append(None); continue
            res.append((len(both), diff.median())); ps.append(st.wilcoxon(both.m, both.h).pvalue)
        idx = [i for i, p in enumerate(ps) if p is not None]
        adj = dict(zip(idx, S.holm([ps[i] for i in idx]))) if idx else {}
        L.append(f"| {lab} | " + " | ".join(f"n={n} Δ={md:+.2f}" + (f" p={S.fmt_p(ps[i])}→{S.fmt_p(adj[i])}" if i in adj else "")
                                            for i, (n, md) in enumerate(res)) + " |")
    L.append("\n(p shown as unadjusted→Holm.)")


def sec_c(df, L):
    L.append("\n## C. RQ3 blocked on project (Friedman, five common projects)\n")
    L.append("Project-level mean per model; Friedman test across the five models with projects as blocks; Kendall's W.\n")
    L.append("| prompt | metric | n blocks | χ² | p | W | mean rank per model |\n|---|---|---|---|---|---|---|")
    llm = df[df.source.isin(MODELS)]
    common = sorted(set.intersection(*[set(llm[llm.source == m].project_id) for m in MODELS]))
    for v in ("neutral", "production"):
        for c, lab in [(c, l) for c, l in STATIC[:3]] + [("d5_ready", "D5 Ready rate"), ("d5_smoke", "D5 smoke rate")]:
            sub = llm[(llm.prompt_variant == v) & llm.project_id.isin(common)].copy()
            sub[c] = pd.to_numeric(sub[c], errors="coerce").astype(float)
            t = sub.pivot_table(index="project_id", columns="source", values=c, aggfunc="mean")[MODELS].dropna()
            if len(t) < 3:
                continue
            chi, p = st.friedmanchisquare(*[t[m] for m in MODELS])
            W = chi / (len(t) * (len(MODELS) - 1))
            ranks = t.rank(axis=1).mean()
            L.append(f"| {v} | {lab} | {len(t)} | {chi:.2f} | {S.fmt_p(p)} | {W:.2f} | " +
                     ", ".join(f"{m} {ranks[m]:.1f}" for m in MODELS) + " |")
    L.append(f"\nCommon projects: {', '.join(common)}")


def logit_cluster(X, y, g, iters=100):
    """Logistic regression by Newton-Raphson; cluster-robust sandwich covariance (CR1 small-sample factor)."""
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ beta))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-8 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p))
        beta += step
        if np.max(np.abs(step)) < 1e-9:
            break
    p = 1 / (1 + np.exp(-X @ beta))
    bread = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]) + 1e-8 * np.eye(X.shape[1]))
    u = X * (y - p)[:, None]
    groups = pd.Series(range(len(y))).groupby(np.asarray(g)).indices
    meat = sum(np.outer(u[i].sum(0), u[i].sum(0)) for i in groups.values())
    G, n, k = len(groups), len(y), X.shape[1]
    V = bread @ meat @ bread * (G / (G - 1)) * ((n - 1) / (n - k))
    return beta, np.sqrt(np.diag(V)), G


def sec_d(df, L):
    L.append("\n## D. RQ4: runtime outcome ~ static score + prompt + project (logistic, cluster-robust)\n")
    L.append("All generated configurations with the static score defined. Static score standardised (OR per 1 SD). "
             "Fixed effects for prompt and project; projects in which the outcome never varies are dropped (they carry "
             "no within-project information). Standard errors clustered by (model, project); Holm across the table. "
             "Model 2 adds model fixed effects.\n")
    L.append("| static score | outcome | n | clusters | OR per SD (95% CI) | p (Holm) | OR with model FE (95% CI) | p (Holm) |")
    L.append("|---|---|---|---|---|---|---|---|")
    llm = df[df.source.isin(MODELS)].copy()
    rows, p1, p2 = [], [], []
    for s, slab in STATIC:
        for yv, ylab in (("d5_ready", "fully Ready"), ("d5_smoke", "smoke passes")):
            d = llm[[s, yv, "prompt_variant", "project_id", "source"]].copy()
            d[s] = pd.to_numeric(d[s], errors="coerce")
            d = d.dropna()
            d[yv] = d[yv].astype(float)
            keep = d.groupby("project_id")[yv].transform(lambda v: v.nunique() > 1)
            d = d[keep]
            z = (d[s] - d[s].mean()) / d[s].std()
            base = pd.get_dummies(d[["prompt_variant", "project_id"]], drop_first=True).astype(float)
            out = []
            for extra in (None, "source"):
                Xd = base if extra is None else pd.concat(
                    [base, pd.get_dummies(d[[extra]], drop_first=True).astype(float)], axis=1)
                X = np.column_stack([np.ones(len(d)), z.to_numpy(), Xd.to_numpy()])
                b_, se, G = logit_cluster(X, d[yv].to_numpy(), d.source + "|" + d.project_id)
                zst = b_[1] / se[1]
                out.append((b_[1], se[1], 2 * st.norm.sf(abs(zst)), G))
            rows.append((slab, ylab, len(d), out))
            p1.append(out[0][2]); p2.append(out[1][2])
    a1, a2 = S.holm(p1), S.holm(p2)
    for (slab, ylab, n, out), q1, q2 in zip(rows, a1, a2):
        f = lambda b_, se: f"{np.exp(b_):.2f} ({np.exp(b_ - 1.96 * se):.2f}–{np.exp(b_ + 1.96 * se):.2f})"
        L.append(f"| {slab} | {ylab} | {n} | {out[0][3]} | {f(out[0][0], out[0][1])} | {S.fmt_p(q1)} | "
                 f"{f(out[1][0], out[1][1])} | {S.fmt_p(q2)} |")
    L.append("\n### Within-prompt point-biserial correlations (unadjusted; descriptive)\n")
    L.append("| static score | outcome | neutral r (p, n) | production r (p, n) |\n|---|---|---|---|")
    for s, slab in STATIC:
        for yv, ylab in (("d5_ready", "fully Ready"), ("d5_smoke", "smoke passes")):
            cells = []
            for v in ("neutral", "production"):
                d = llm[llm.prompt_variant == v][[s, yv]].copy()
                d[s] = pd.to_numeric(d[s], errors="coerce"); d = d.dropna()
                r, p = st.pointbiserialr(d[yv].astype(int), d[s].astype(float))
                cells.append(f"{r:+.2f} ({S.fmt_p(p)}, {len(d)})")
            L.append(f"| {slab} | {ylab} | " + " | ".join(cells) + " |")


def d6_rows():
    rows = []
    for f in glob.glob(os.path.join(S.HERE, "results", "*.json")):
        r = json.load(open(f, encoding="utf-8"))
        d6 = r.get("d6") or {}
        if not d6.get("ran"):
            continue
        av, down = [], []
        for fault in ("pod_delete", "container_crash"):
            for e in d6.get(fault) or []:
                if e.get("ran") and e.get("availability_pct") is not None:
                    av.append(e["availability_pct"])
                    down.append((1 - e["availability_pct"] / 100) * (e.get("n_probes") or 0) / 5.0)
        if av:
            rows.append({"source": r["source"], "prompt": r.get("prompt_variant") or "human",
                         "replicas": d6.get("n_ready_before"), "availability": np.mean(av), "downtime_s": np.mean(down)})
    return pd.DataFrame(rows)


def sec_e(L):
    L.append("\n## E. D6 stratified by the replica count of the faulted workload\n")
    L.append("Downtime = (1 − availability) × probing window, from the 5 Hz prober (n_probes / 5 s), mean over the six faults.\n")
    d = d6_rows()
    d["rep"] = np.where(d.replicas.fillna(1) >= 2, "≥2 replicas", "1 replica")
    L.append("| group | prompt | n | median availability (%) | median downtime (s) |\n|---|---|---|---|---|")
    for grp, sub in d.groupby(["rep", "prompt"]):
        L.append(f"| {grp[0]} | {grp[1]} | {len(sub)} | {sub.availability.median():.1f} | {sub.downtime_s.median():.1f} |")
    L.append("\n| prompt | share of D6 configurations whose faulted workload has ≥2 replicas |\n|---|---|")
    for v, sub in d.groupby("prompt"):
        L.append(f"| {v} | {100 * (sub.replicas.fillna(1) >= 2).mean():.0f}% ({int((sub.replicas.fillna(1) >= 2).sum())}/{len(sub)}) |")
    rho, p = st.spearmanr(d.replicas.fillna(1), d.availability)
    L.append(f"\nSpearman(replicas, availability) = {rho:+.2f} (p={S.fmt_p(p)}, n={len(d)})")
    one = d[d.rep == "1 replica"]
    if len(one) > 3:
        h = st.kruskal(*[g.downtime_s for _, g in one.groupby("source") if len(g)])
        L.append(f"Single-replica downtime across sources: Kruskal-Wallis H={h.statistic:.2f}, p={S.fmt_p(h.pvalue)}")


def sec_f(L):
    L.append("\n## F. Sensitivity of D5 to deployment-time adjustments (worst-case bound)\n")
    n = shim = alias = 0
    rd = sm = both = 0
    tot = {"ready": 0, "smoke": 0, "both": 0}
    for f in glob.glob(os.path.join(S.HERE, "results", "*.json")):
        b = os.path.basename(f)
        if b.startswith("human") or not b.endswith(".json"):
            continue
        d = (json.load(open(f, encoding="utf-8")).get("d5") or {})
        n += 1
        r_, s_ = bool(d.get("ready_ok")), bool(d.get("smoke_ok"))
        tot["ready"] += r_; tot["smoke"] += s_; tot["both"] += r_ and s_
        has_s = bool(d.get("shims_applied"))
        has_a = any(str(i.get("served", "")).startswith("alias:") for i in d.get("images") or [] if isinstance(i, dict))
        shim += has_s; alias += has_a
        if has_s or has_a:
            rd += r_; sm += s_; both += r_ and s_
    L.append(f"Generated configurations: {n}; with a start-up shim applied: {shim}; with an image alias served: {alias}; "
             f"with either: of which Ready {rd}, smoke {sm}, both {both}.")
    L.append(f"\n| outcome | as reported | worst case (every adjusted success counted as failure) |\n|---|---|---|")
    for k, v in (("ready", rd), ("smoke", sm), ("both", both)):
        L.append(f"| {k} | {tot[k]}/{n} ({100 * tot[k] / n:.1f}%) | {tot[k] - v}/{n} ({100 * (tot[k] - v) / n:.1f}%) |")


def main():
    df = S.load()
    L = ["# K8sGenBench robustness report (generated by evaluation/robust.py; do not edit)\n"]
    sec_a(df, L); sec_b(df, L); sec_c(df, L); sec_d(df, L); sec_e(L); sec_f(L)
    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("->", OUT)


if __name__ == "__main__":
    main()
