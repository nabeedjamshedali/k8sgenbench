"""RQ6: neutral vs production vs guided (first attempt) vs guided + repair (final attempt), per model.

Usage: python evaluation/rq6.py           -> test split: evaluation/analysis/rq6_report.md, paper/tables/tab_rq6.tex
       python evaluation/rq6.py --dev     -> the development projects with the current prompt (report only)
The final attempt of a loop is the round named in generation/outputs/<m>/<p>/guided_loop_s<k>.json. Outcomes are
the independent ones (D5 Ready/smoke, D6), never the gate. A loop the provider stopped (request too large) keeps
its last evaluated round as its final attempt and is counted separately.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import binomtest

import stats as S

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(HERE, "results")
OUTPUTS = os.path.join(ROOT, "generation", "outputs")
MODELS = ["claude", "gemini", "qwen"]
LABEL = {"claude": "Claude", "gemini": "Gemini", "qwen": "Qwen"}
TEST = ["P03_grafana", "P05_emojivoto", "P07_online-boutique", "P06_wordsmith", "P09_teastore", "P12_headlamp"]
DEV = ["P02_n8n", "P04_voting-app", "P08_sock-shop", "P10_k8s-dashboard"]
CONDITIONS = [("neutral", "Neutral"), ("production", "Production"), ("guided", "Guided, first attempt"),
              ("repair", "Guided + repair, final attempt")]


def record(name):
    f = os.path.join(RESULTS, f"{name}.json")
    return S.derive(json.load(open(f, encoding="utf-8"))) if os.path.exists(f) else None


def rows(projects, samples):
    out = []
    for m in MODELS:
        for p in projects:
            for k in samples:
                base = {"model": m, "project": p, "k": k}
                for v in ("neutral", "production"):
                    x = record(f"{m}__{p}__{v}__s{k}")
                    if x is not None:
                        out.append({**base, "condition": v, **x})
                loop = os.path.join(OUTPUTS, m, p, f"guided_loop_s{k}.json")
                if not os.path.exists(loop):
                    continue
                s = json.load(open(loop, encoding="utf-8"))
                r0 = record(f"{m}__{p}__guided_r0__s{k}")
                if r0 is None:
                    continue
                out.append({**base, "condition": "guided", **r0})
                done = [x["round"] for x in s["rounds"]]
                fin = record(f"{m}__{p}__guided_r{max(done)}__s{k}")
                out.append({**base, "condition": "repair", **fin, "rounds": len(done), "stopped": s["stopped"],
                            "gate_passed": s["rounds"][-1]["gate_passed"]})
    return pd.DataFrame(out)


def pct(s):
    s = s.dropna().astype(bool)
    return f"{100 * s.mean():.0f} ({int(s.sum())}/{len(s)})" if len(s) else "--"


def med(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    return f"{s.median():.1f}" if len(s) else "--"


def mcnemar(df, m, a, b, col):
    """Exact McNemar test on configurations present in both conditions (same model, project, sample)."""
    x = df[(df.model == m) & (df.condition == a)].set_index(["project", "k"])[col]
    y = df[(df.model == m) & (df.condition == b)].set_index(["project", "k"])[col]
    j = x.to_frame("a").join(y.to_frame("b"), how="inner").dropna()
    n01 = int(((~j.a.astype(bool)) & j.b.astype(bool)).sum())
    n10 = int((j.a.astype(bool) & ~j.b.astype(bool)).sum())
    p = binomtest(n01, n01 + n10).pvalue if n01 + n10 else 1.0
    return n01, n10, p, len(j)


def report(df):
    lines = ["| Model | Condition | n | Ready | Smoke | Ready and smoke | PSS baseline | Kubescape | D6 availability |",
             "|---|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for c, lab in CONDITIONS:
            g = df[(df.model == m) & (df.condition == c)]
            if not len(g):
                continue
            both = g.d5_ready & g.d5_smoke
            lines.append(f"| {LABEL[m]} | {lab} | {len(g)} | {pct(g.d5_ready)} | {pct(g.d5_smoke)} | {pct(both)} | "
                         f"{pct(g.d2_pss_baseline)} | {med(g.d2_kubescape_compliance)} | {med(g.d6_availability_mean)} |")
    lines += ["", "Loops (final attempt):", "", "| Model | Loops | Gate passed | Max repairs | Provider stopped | "
              "Rounds (median) | Gate passed but smoke failed |", "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        g = df[(df.model == m) & (df.condition == "repair")]
        if not len(g):
            continue
        lines.append(f"| {LABEL[m]} | {len(g)} | {int((g.stopped == 'gate_passed').sum())} | "
                     f"{int((g.stopped == 'max_repairs').sum())} | {int((g.stopped == 'provider_request_limit').sum())} | "
                     f"{g.rounds.median():.0f} | {int(((g.stopped == 'gate_passed') & ~g.d5_smoke).sum())} |")
    lines += ["", "Paired exact McNemar tests on the smoke test (configurations present in both conditions):", ""]
    for m in MODELS:
        for a, b in (("production", "guided"), ("guided", "repair"), ("production", "repair")):
            n01, n10, p, n = mcnemar(df, m, a, b, "d5_smoke")
            if n:
                lines.append(f"- {LABEL[m]}: {a} -> {b}: {n01} gained, {n10} lost of {n} pairs, p = {p:.3f}")
    return "\n".join(lines) + "\n"


def latex(df):
    head = (r"\begin{table*}[t]" "\n" r"\centering\small" "\n"
            r"\caption{RQ6 on the held-out projects: share of configurations fully Ready, passing the smoke test, and "
            r"both; share meeting Pod Security baseline; median Kubescape compliance and D6 availability. The final "
            r"attempt is the last round of each loop.}\label{tab:rq6}" "\n"
            r"\begin{tabular}{llrlllll}" "\n" r"\toprule" "\n"
            r"Model & Condition & $n$ & Ready & Smoke test & Both & PSS baseline & Kubescape \\ \midrule" "\n")
    body = []
    for m in MODELS:
        for c, lab in CONDITIONS:
            g = df[(df.model == m) & (df.condition == c)]
            if len(g):
                both = g.d5_ready & g.d5_smoke
                body.append(" & ".join([LABEL[m] if c == "neutral" else "", lab, str(len(g)), pct(g.d5_ready),
                                        pct(g.d5_smoke), pct(both), pct(g.d2_pss_baseline),
                                        med(g.d2_kubescape_compliance)]).replace("%", r"\%") + r" \\")
        body.append(r"\midrule")
    body[-1] = r"\bottomrule"
    return "% generated by evaluation/rq6.py -- do not edit\n" + head + "\n".join(body) + "\n" r"\end{tabular}" "\n" r"\end{table*}" "\n"


if __name__ == "__main__":
    dev = "--dev" in sys.argv
    df = rows(DEV if dev else TEST, [1] if dev else [1, 2, 3])
    if not len(df):
        sys.exit("no RQ6 results yet")
    text = report(df)
    print(text)
    if not dev:
        os.makedirs(os.path.join(HERE, "analysis"), exist_ok=True)
        open(os.path.join(HERE, "analysis", "rq6_report.md"), "w", encoding="utf-8").write(text)
        os.makedirs(os.path.join(ROOT, "paper", "tables"), exist_ok=True)
        open(os.path.join(ROOT, "paper", "tables", "tab_rq6.tex"), "w", encoding="utf-8").write(latex(df))
