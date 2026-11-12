"""Phase R9: statistical analysis per paper Section 3.6 (Statistical analysis).

Reads evaluation/results/*.json (via flatten.row) and writes evaluation/analysis/:
  configs.csv        one row per configuration with the derived analysis metrics
  summary_<v>.csv    per-source descriptive table for each prompt variant
  report.md          all tests (RQ1, RQ3, RQ4, RQ5) with n, statistic, p (Holm-adjusted where a family), effect size

Usage: python evaluation/stats.py
Unit of analysis: the configuration, as pre-specified. Because the 3 samples of a (model, project) are not independent
of each other, RQ1 is also repeated at project level (mean over samples, paired with the human config of the same
project, n = number of projects) as a robustness check; a result is only called robust if both agree.
"""
import glob
import json
import os
import re

import numpy as np
import pandas as pd
from scipy import stats

import flatten

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "analysis")
MODELS = ["claude", "deepseek", "gemini", "gpt", "qwen"]

# (column, label); continuous metrics are compared only where defined (e.g. D6 only for deployed configs)
CONTINUOUS = [("d1_accept_pct", "D1 objects accepted (%)"),
              ("d2_kubescape_compliance", "D2 Kubescape compliance (%)"),
              ("d2_trivy_high_crit", "D2 Trivy high+critical findings"),
              ("d3_checklist_pct", "D3 reliability checklist (%)"),
              ("d3_polaris_score", "D3 Polaris score"),
              ("d3_zhang_density_kloc", "D3 Zhang smells per KLOC"),
              ("d4_pct", "D4 requirements met (%)"),
              ("d5_time_to_ready_s", "D5 time to Ready (s)"),
              ("d6_availability_mean", "D6 mean availability (%)"),
              ("d6_recovery_time_mean", "D6 mean recovery time (s)"),
              ("d6_availability_strict", "D6 mean availability, fully-Ready only (%)")]
BINARY = [("d1_parse_ok", "D1 parses"), ("d1_schema_ok", "D1 schema-valid"), ("d1_server_ok", "D1 API-accepted"),
          ("d2_pss_restricted", "D2 passes PSS restricted"), ("d2_pss_baseline", "D2 passes PSS baseline+"),
          ("d2_has_secret", "D2 hard-coded secret found"), ("d3_zhang_any", "D3 any Zhang smell"),
          ("d5_ready", "D5 Ready"), ("d5_smoke", "D5 smoke passes"), ("d6_all_recovered", "D6 all 6 faults recovered"),
          ("d6_all_recovered_strict", "D6 all recovered, fully-Ready only")]


def b(x):
    if isinstance(x, bool):
        return x
    if x in (None, "", "None"):
        return None
    return str(x) == "True"


def load():
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
        r = json.load(open(f, encoding="utf-8"))
        x = flatten.row(r)
        parsed = b(x["d1_parse_ok"])
        tot, acc = x["d1_objects_total"], x["d1_objects_accepted"]
        x["d1_accept_pct"] = 100.0 * acc / tot if parsed and tot else (0.0 if parsed is False else None)
        x["d1_parse_ok"], x["d1_schema_ok"], x["d1_server_ok"] = (bool(parsed), bool(b(x["d1_schema_ok"])),
                                                                  bool(b(x["d1_server_ok"])))
        lvl = x["d2_pss_level"]
        x["d2_pss_restricted"] = lvl == "restricted" if parsed else None
        x["d2_pss_baseline"] = lvl in ("baseline", "restricted") if parsed else None
        x["d2_has_secret"] = (x["d2_secrets_found"] or 0) > 0 if parsed else None
        x["d2_trivy_high_crit"] = ((x.get("d2_trivy_high") or 0) + (x.get("d2_trivy_critical") or 0)) if parsed else None
        x["d3_zhang_any"] = b(x["d3_zhang_any"]) if parsed else None
        # a config that does not parse or is not deployed is a D5 failure, not missing data
        x["d5_ready"] = bool(b(x["d5_ready_ok"]))
        x["d5_smoke"] = bool(b(x["d5_smoke_ok"]))
        av, rt, ok = [], [], []
        for fault in ("pod_delete", "container_crash"):
            for i in (1, 2, 3):
                if x.get(f"d6_{fault}_recovery_ok_{i}") is not None:
                    ok.append(bool(b(x[f"d6_{fault}_recovery_ok_{i}"])))
                    av.append(x[f"d6_{fault}_availability_pct_{i}"])
                    rt.append(x[f"d6_{fault}_recovery_time_s_{i}"])
        x["d6_all_recovered"] = all(ok) if ok else None
        x["d6_availability_mean"] = float(np.mean([a for a in av if a is not None])) if av else None
        x["d6_recovery_time_mean"] = float(np.mean([t for t in rt if t is not None])) if any(t is not None for t in rt) else None
        # sensitivity: D6 only where the config was fully Ready (the original gate), not admitted by smoke alone
        strict = x.get("d6_gate") == "ready"
        x["d6_availability_strict"] = x["d6_availability_mean"] if strict else None
        x["d6_all_recovered_strict"] = x["d6_all_recovered"] if strict else None
        rows.append(x)
    df = pd.DataFrame(rows)
    for c, _ in CONTINUOUS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ---------- tests ----------
def holm(ps):
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    adj = np.empty_like(ps)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def cliffs_delta(a, b_):
    a, b_ = np.asarray(a, float), np.asarray(b_, float)
    if len(a) == 0 or len(b_) == 0:
        return np.nan
    gt = sum((x > y) for x in a for y in b_)
    lt = sum((x < y) for x in a for y in b_)
    return (gt - lt) / (len(a) * len(b_))


def cliff_mag(d):
    if np.isnan(d):
        return ""
    d = abs(d)
    return "negligible" if d < 0.147 else "small" if d < 0.33 else "medium" if d < 0.474 else "large"


def dunn(groups):
    """Dunn's test (tie-corrected), all pairs, Holm-adjusted. groups: {name: values}."""
    names = list(groups)
    allv = np.concatenate([groups[n] for n in names])
    ranks = stats.rankdata(allv)
    n_tot = len(allv)
    _, counts = np.unique(allv, return_counts=True)
    tie = (counts ** 3 - counts).sum() / (12 * (n_tot - 1))
    mean_rank, start = {}, 0
    for n in names:
        k = len(groups[n])
        mean_rank[n] = ranks[start:start + k].mean()
        start += k
    pairs, ps = [], []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, c = names[i], names[j]
            se = np.sqrt((n_tot * (n_tot + 1) / 12 - tie) * (1 / len(groups[a]) + 1 / len(groups[c])))
            z = (mean_rank[a] - mean_rank[c]) / se if se > 0 else 0.0
            pairs.append((a, c, z))
            ps.append(2 * stats.norm.sf(abs(z)))
    return [(a, c, z, p, pa) for (a, c, z), p, pa in zip(pairs, ps, holm(ps) if ps else [])]


def mcnemar_exact(x, y):
    """x, y: paired booleans. Returns (b, c, p) where b = x True & y False."""
    b_ = int(np.sum(x & ~y))
    c = int(np.sum(~x & y))
    p = stats.binomtest(b_, b_ + c, 0.5).pvalue if b_ + c else 1.0
    return b_, c, p


def fmt_p(p):
    return "" if p is None or (isinstance(p, float) and np.isnan(p)) else ("<0.001" if p < 0.001 else f"{p:.3f}")


# ---------- report ----------
def describe(df, variant):
    sub = df[(df.prompt_variant == variant) | (df.source == "human")]
    out = []
    for src in ["human"] + MODELS:
        s = sub[sub.source == src]
        if s.empty:
            continue
        row = {"source": src, "n": len(s)}
        for c, lab in BINARY:
            v = s[c].dropna()
            row[lab] = f"{100 * v.mean():.0f}% ({int(v.sum())}/{len(v)})" if len(v) else ""
        for c, lab in CONTINUOUS:
            v = s[c].dropna()
            row[lab] = f"{v.median():.1f} [{v.quantile(.25):.1f}-{v.quantile(.75):.1f}] n={len(v)}" if len(v) else ""
        out.append(row)
    return pd.DataFrame(out)


def md_table(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def compare_sources(df, sources, title, lines, ref=None, balanced=False):
    """Kruskal-Wallis + Dunn (continuous), chi2/Fisher (binary) across `sources`; Cliff's delta vs `ref`.
    balanced: keep only projects that every present source covers, so project mix does not confound the comparison
    (Qwen has no samples for the two largest prompts)."""
    present = [s for s in sources if (df.source == s).any()]
    if balanced:
        common = set.intersection(*(set(df[df.source == s].project_id) for s in present)) if present else set()
        df = df[df.project_id.isin(common)]
        title += f" -- balanced on {len(common)} common projects"
    lines.append(f"\n## {title}\n")
    lines.append(f"Sources with data: {', '.join(present)}\n")
    lines.append("| metric | test | statistic | p | post-hoc / effect (Holm-adjusted) |\n|---|---|---|---|---|")
    for c, lab in CONTINUOUS:
        groups = {s: df[df.source == s][c].dropna().to_numpy() for s in present}
        groups = {s: v for s, v in groups.items() if len(v) >= 2}
        if len(groups) < 2 or len(np.unique(np.concatenate(list(groups.values())))) < 2:
            lines.append(f"| {lab} | Kruskal-Wallis | | | insufficient data |")
            continue
        h, p = stats.kruskal(*groups.values())
        notes = []
        if ref and ref in groups:
            for s in groups:
                if s != ref:
                    d = cliffs_delta(groups[s], groups[ref])
                    notes.append(f"{s} vs {ref}: δ={d:+.2f} ({cliff_mag(d)})")
        if p < 0.05:
            sig = [f"{a}-{c_}: p={fmt_p(pa)}" for a, c_, z, p_, pa in dunn(groups) if pa < 0.05]
            notes.append("Dunn sig.: " + ("; ".join(sig) if sig else "none after Holm"))
        lines.append(f"| {lab} | Kruskal-Wallis (n={sum(map(len, groups.values()))}) | H={h:.2f} | {fmt_p(p)} | {'<br>'.join(notes)} |")
    for c, lab in BINARY:
        tab = []
        for s in present:
            v = df[df.source == s][c].dropna().astype(bool)
            if len(v):
                tab.append((s, int(v.sum()), int((~v).sum())))
        if len(tab) < 2:
            continue
        m = np.array([[t[1], t[2]] for t in tab])
        if (m.sum(axis=0) == 0).any():
            lines.append(f"| {lab} | χ² | | | all sources identical ({'yes' if m[:, 0].sum() else 'no'}) |")
            continue
        chi2, p, _, exp = stats.chi2_contingency(m)
        notes = []
        if ref and any(t[0] == ref for t in tab):
            r = next(t for t in tab if t[0] == ref)
            fp = [(t[0], stats.fisher_exact([[t[1], t[2]], [r[1], r[2]]])[1]) for t in tab if t[0] != ref]
            for (s, _), pa in zip(fp, holm([x[1] for x in fp])):
                notes.append(f"{s} vs {ref} Fisher p={fmt_p(pa)}")
        warn = " (expected<5: read Fisher)" if (exp < 5).any() else ""
        lines.append(f"| {lab} | χ²{warn} | {chi2:.2f} | {fmt_p(p)} | {'<br>'.join(notes)} |")


def project_level_rq1(df, lines):
    lines.append("\n## RQ1 robustness: project level (mean over samples, paired with the human config of the same project)\n")
    lines.append("Wilcoxon signed-rank per model vs human; n = projects with both. Low power at n ≤ 7: read with the config-level result.\n")
    lines.append("| metric | " + " | ".join(MODELS) + " |\n|---|" + "---|" * len(MODELS))
    neu = df[df.prompt_variant == "neutral"]
    hum = df[df.source == "human"].set_index("project_id")
    for c, lab in CONTINUOUS + BINARY:
        cells = []
        for m in MODELS:
            pm = neu[neu.source == m].groupby("project_id")[c].apply(lambda v: pd.to_numeric(v, errors="coerce").mean())
            both = pd.concat([pm, pd.to_numeric(hum[c], errors="coerce")], axis=1, keys=["m", "h"]).dropna()
            if len(both) < 3:
                cells.append(f"n={len(both)}")
                continue
            diff = both.m - both.h
            if (diff == 0).all():
                cells.append(f"n={len(both)} Δ=0")
                continue
            p = stats.wilcoxon(both.m, both.h).pvalue
            cells.append(f"n={len(both)} Δmed={diff.median():+.2f} p={fmt_p(p)}")
        lines.append(f"| {lab} | " + " | ".join(cells) + " |")


def rq5(df, lines):
    lines.append("\n## RQ5: production vs neutral prompt (paired by model, project, sample)\n")
    lines.append("| metric | model | n pairs | test | result |\n|---|---|---|---|---|")
    llm = df[df.source.isin(MODELS)]
    key = ["source", "project_id", "sample_k"]
    pv = llm.pivot_table(index=key, columns="prompt_variant", values=[c for c, _ in CONTINUOUS + BINARY], aggfunc="first")
    for c, lab in CONTINUOUS + BINARY:
        if (c, "neutral") not in pv or (c, "production") not in pv:
            continue
        for m in ["all"] + MODELS:
            sub = pv if m == "all" else pv[pv.index.get_level_values(0) == m]
            pair = sub[[(c, "neutral"), (c, "production")]].dropna()
            if len(pair) < 3:
                continue
            n_, p_ = pair[(c, "neutral")], pair[(c, "production")]
            if c in dict(BINARY):
                bb, cc, p = mcnemar_exact(p_.astype(bool).to_numpy(), n_.astype(bool).to_numpy())
                res = f"prod-only yes={bb}, neutral-only yes={cc}, McNemar exact p={fmt_p(p)}"
                test = "McNemar"
            else:
                n_, p_ = n_.astype(float), p_.astype(float)
                d = (p_ - n_)
                if (d == 0).all():
                    res, test = "no difference", "Wilcoxon"
                else:
                    w = stats.wilcoxon(p_, n_)
                    res = f"median Δ(prod-neutral)={d.median():+.2f}, W={w.statistic:.1f}, p={fmt_p(w.pvalue)}"
                    test = "Wilcoxon"
            lines.append(f"| {lab} | {m} | {len(pair)} | {test} | {res} |")


def rq3_consistency(df, lines):
    lines.append("\n## RQ3 consistency: spread across the 3 samples of each (model, project, variant)\n")
    lines.append("Continuous: median over cells of the across-sample SD. Binary: share of cells where all samples agree.\n")
    lines.append("| model | cells (k=3) | " + " | ".join(l for _, l in CONTINUOUS[:7]) + " | D5 Ready agree | D5 smoke agree |")
    lines.append("|---|---|" + "---|" * 9)
    llm = df[df.source.isin(MODELS)]
    for m in MODELS:
        g = llm[llm.source == m].groupby(["project_id", "prompt_variant"])
        cells = [x for _, x in g if len(x) == 3]
        if not cells:
            continue
        sds = []
        for c, _ in CONTINUOUS[:7]:
            v = [x[c].astype(float).std(ddof=1) for x in cells if x[c].notna().sum() == 3]
            sds.append(f"{np.median(v):.2f}" if v else "")
        agree = [f"{100 * np.mean([x[c].nunique() == 1 for x in cells]):.0f}%" for c in ("d5_ready", "d5_smoke")]
        lines.append(f"| {m} | {len(cells)} | " + " | ".join(sds) + " | " + " | ".join(agree) + " |")


def rq4(df, lines):
    lines.append("\n## RQ4: do static scores predict runtime outcomes? (all configurations, Spearman ρ; point-biserial for binary)\n")
    lines.append("| static | runtime | n | ρ / r_pb | p |\n|---|---|---|---|---|")
    static = ["d2_kubescape_compliance", "d3_checklist_pct", "d3_polaris_score", "d3_zhang_density_kloc", "d4_pct"]
    runtime = [("d5_ready", True), ("d5_smoke", True), ("d6_availability_mean", False), ("d5_time_to_ready_s", False)]
    labels = dict(CONTINUOUS + BINARY)
    rows, ps = [], []
    for s in static:
        for r, is_bin in runtime:
            pair = df[[s, r]].dropna()
            if len(pair) < 5 or pair[s].nunique() < 2 or pair[r].nunique() < 2:
                continue
            if is_bin:
                rho, p = stats.pointbiserialr(pair[r].astype(int), pair[s].astype(float))
            else:
                rho, p = stats.spearmanr(pair[s].astype(float), pair[r].astype(float))
            rows.append((labels[s], labels[r], len(pair), rho))
            ps.append(p)
    for (s, r, n, rho), pa in zip(rows, holm(ps) if ps else []):
        lines.append(f"| {s} | {r} | {n} | {rho:+.2f} | {fmt_p(pa)} (Holm) |")


# ---------- RQ2 ----------
RAHMAN = ["Absent resource limit", "Absent securityContext", "Activation of hostIPC", "Activation of hostNetwork",
          "Activation of hostPID", "Capability misuse", "Docker socket mounting",
          "Escalated privileges for child processes", "Hard-coded secret", "Insecure HTTP",
          "Privileged securityContext"]
SECRET_KEY = ("user", "password", "passwd", "token", "secret")
# Zhang et al. 2024, Table 2 (ChatGPT, 95 manifests): smell -> (density per KLOC, proportion %). The anti-affinity
# row is printed with density/proportion swapped in the PDF text; 4 occurrences / ~1.49 KLOC = 2.7 and 4/95 = 4.2%.
ZHANG = {"dangling-service": (6.7, 10.5), "no-anti-affinity": (2.7, 4.2), "no-read-only-root-fs": (22.7, 35.8),
         "run-as-non-root": (22.8, 35.7), "unset-cpu-requirements": (45.5, 35.8),
         "unset-memory-requirements": (45.5, 35.8)}


def _pod_specs(d):
    spec = d.get("spec") or {}
    if d.get("kind") == "Pod":
        return [spec]
    if d.get("kind") == "CronJob":
        spec = ((spec.get("jobTemplate") or {}).get("spec")) or {}
    tpl = (spec.get("template") or {}).get("spec")
    return [tpl] if isinstance(tpl, dict) else []


def rahman_categories(docs):
    """Rahman et al. (TOSEM 2023) 11 categories, implemented from their SLI-KUBE rules (Table 3) on the manifest."""
    hit = set()

    def scan_strings(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str) and v.startswith("http://") and not re.match(r"http://(localhost|127\.0\.0\.1)", v):
                    hit.add("Insecure HTTP")
                scan_strings(v)
        elif isinstance(x, list):
            for v in x:
                if isinstance(v, str) and v.startswith("http://") and not re.match(r"http://(localhost|127\.0\.0\.1)", v):
                    hit.add("Insecure HTTP")
                scan_strings(v)

    for d in docs:
        if not isinstance(d, dict):
            continue
        scan_strings(d)
        if d.get("kind") == "Secret":
            for sect in ("data", "stringData"):
                if any(any(s in str(k).lower() for s in SECRET_KEY) and v for k, v in (d.get(sect) or {}).items()):
                    hit.add("Hard-coded secret")
        for ps in _pod_specs(d):
            for flag, cat in (("hostIPC", "Activation of hostIPC"), ("hostNetwork", "Activation of hostNetwork"),
                              ("hostPID", "Activation of hostPID")):
                if ps.get(flag) is True:
                    hit.add(cat)
            for v in ps.get("volumes") or []:
                if "docker.sock" in str(((v or {}).get("hostPath") or {}).get("path", "")):
                    hit.add("Docker socket mounting")
            for c in (ps.get("containers") or []) + (ps.get("initContainers") or []):
                lim = ((c.get("resources") or {}).get("limits")) or {}
                if not (lim.get("cpu") and lim.get("memory")):
                    hit.add("Absent resource limit")
                sc = c.get("securityContext")
                if not sc:
                    hit.add("Absent securityContext")
                sc = sc or {}
                if sc.get("privileged") is True:
                    hit.add("Privileged securityContext")
                if sc.get("allowPrivilegeEscalation") is True:
                    hit.add("Escalated privileges for child processes")
                caps = [str(x).upper().replace("CAP_", "") for x in ((sc.get("capabilities") or {}).get("add") or [])]
                if "SYS_ADMIN" in caps or "SYS_MODULE" in caps:
                    hit.add("Capability misuse")
                for e in c.get("env") or []:
                    if any(s in str(e.get("name", "")).lower() for s in SECRET_KEY) and e.get("value"):
                        hit.add("Hard-coded secret")
                for m in c.get("volumeMounts") or []:
                    if "docker.sock" in str(m.get("mountPath", "")):
                        hit.add("Docker socket mounting")
    return hit


def rq2(df, lines):
    import yaml as _yaml
    import eval_runner
    rows = []
    for r in df.itertuples():
        if r.d1_parse_ok is not True and str(r.d1_parse_ok) != "True":
            continue
        try:
            if r.source == "human":
                docs = eval_runner.load_docs_for_source("human", r.project_id)[0]
            else:
                p = os.path.join(eval_runner.GEN_OUTPUTS, r.source, r.project_id, r.prompt_variant, f"s{r.sample_k}",
                                 "manifest.yaml")
                docs = [d for d in _yaml.safe_load_all(open(p, encoding="utf-8")) if d]
        except Exception:
            continue
        cats = rahman_categories(docs)
        rows.append({"source": r.source, "prompt_variant": r.prompt_variant if r.source != "human" else "human",
                     **{c: c in cats for c in RAHMAN}})
    t = pd.DataFrame(rows)
    lines.append("\n## RQ2: Rahman et al. security misconfiguration categories (share of parsed configurations)\n")
    lines.append("Detected with the SLI-KUBE rules of Rahman et al. (2023, Table 3), applied to every container and pod spec.\n")
    if not t.empty:
        g = (100 * t.groupby(["source", "prompt_variant"])[RAHMAN].mean()).round(0).astype(int)
        g.insert(0, "n", t.groupby(["source", "prompt_variant"]).size())
        g.index = [a if b == "human" else f"{a} ({b})" for a, b in g.index]
        lines.append(md_table(g.T.reset_index().rename(columns={"index": "category"})))
        t.to_csv(os.path.join(OUT, "rq2_rahman.csv"), index=False)
    lines.append("\n## RQ2: KubeLinter smells vs Zhang et al. (2024, ChatGPT 2023)\n")
    lines.append("Proportion = % of configurations with >= 1 instance; density = instances per KLOC. Our unit is a whole "
                 "multi-object configuration, Zhang's a manifest file (often one object), so density is the comparable "
                 "measure; proportions are inflated by the larger unit.\n")
    lines.append("| smell | Zhang 2023 density | Zhang 2023 % | " + " | ".join(f"{s} density | {s} %" for s in ["human"] + MODELS
                 if (df.source == s).any()) + " |")
    present = [s for s in ["human"] + MODELS if (df.source == s).any()]
    lines.append("|---|---|---|" + "---|---|" * len(present))
    for smell, (zd, zp) in ZHANG.items():
        col = f"d3_smell_{smell}"
        cells = []
        for s in present:
            sub = df[(df.source == s) & (df.prompt_variant.isin(["neutral", "n/a"]))]
            v = pd.to_numeric(sub[col], errors="coerce") if col in sub else pd.Series(dtype=float)
            loc = pd.to_numeric(sub["loc"], errors="coerce")
            ok = v.notna() & loc.notna()
            dens = 1000 * v[ok].sum() / loc[ok].sum() if loc[ok].sum() else np.nan
            prop = 100 * (v[ok] > 0).mean() if ok.any() else np.nan
            cells += [f"{dens:.1f}", f"{prop:.0f}"]
        lines.append(f"| {smell} | {zd} | {zp} | " + " | ".join(cells) + " |")
    lines.append("\nLLM columns use the neutral prompt only, the closest analogue to Zhang's DevGPT conversations.")


def _features(docs, with_values):
    """Normalised key paths (kind-prefixed, list indices collapsed) of a manifest; with_values adds scalar leaves."""
    out = set()

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for v in x:
                walk(v, path + "[]")
        else:
            out.add(f"{path}={x}" if with_values else path)
    for d in docs:
        if isinstance(d, dict):
            walk(d, str(d.get("kind")))
    return out


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else np.nan


def contamination(df, lines):
    """Threats 'Training-data contamination': similarity of each generated manifest to the human one, against the
    same model's similarity to the OTHER models' manifests for the same project and variant (the peer control).
    Similarity to the human well above the peer level suggests reproduction of the published manifest."""
    import yaml as _yaml
    import eval_runner
    feats, rows = {}, []
    for r in df.itertuples():
        try:
            if r.source == "human":
                docs = eval_runner.load_docs_for_source("human", r.project_id)[0]
            else:
                p = os.path.join(eval_runner.GEN_OUTPUTS, r.source, r.project_id, r.prompt_variant, f"s{r.sample_k}",
                                 "manifest.yaml")
                docs = [d for d in _yaml.safe_load_all(open(p, encoding="utf-8")) if d]
        except Exception:
            continue
        feats[(r.source, r.project_id, r.prompt_variant, r.sample_k)] = (_features(docs, False), _features(docs, True))
    hum = {k[1]: v for k, v in feats.items() if k[0] == "human"}
    for (src, proj, var, k), (fs, fv) in feats.items():
        if src == "human" or proj not in hum:
            continue
        peers = [v for (s2, p2, v2, _), v in feats.items() if s2 not in ("human", src) and p2 == proj and v2 == var]
        rows.append({"source": src, "project_id": proj, "prompt_variant": var,
                     "j_struct_human": jaccard(fs, hum[proj][0]), "j_value_human": jaccard(fv, hum[proj][1]),
                     "j_struct_peer": np.mean([jaccard(fs, p[0]) for p in peers]) if peers else np.nan,
                     "j_value_peer": np.mean([jaccard(fv, p[1]) for p in peers]) if peers else np.nan})
    c = pd.DataFrame(rows)
    c.to_csv(os.path.join(OUT, "contamination.csv"), index=False)
    lines.append("\n## Contamination indicator: Jaccard similarity to the human manifest vs to other models (peer control)\n")
    lines.append("struct = key paths; value = key path + scalar value. Median per (project, source); "
                 "'excess' = human minus peer, value level (positive = closer to the published manifest than models are to each other).\n")
    if c.empty:
        lines.append("no data")
        return
    g = c.groupby(["project_id", "source"])[["j_struct_human", "j_struct_peer", "j_value_human", "j_value_peer"]].median()
    g["excess_value"] = g.j_value_human - g.j_value_peer
    lines.append(md_table(g.round(2).reset_index()))


# Kubescape control <-> Trivy check on the same concept. Only pairs whose Trivy title was seen in this corpus and
# matches are scored; CANDIDATE pairs are listed for verification once a config fails them (title check below).
OVERLAP = {"privilege escalation allowed": ("C-0016", "KSV-0001"),
           "runs as root": ("C-0013", "KSV-0012"),
           "writable root filesystem": ("C-0017", "KSV-0014"),
           "CPU limit missing": ("C-0270", "KSV-0011"),
           "memory limit missing": ("C-0271", "KSV-0018")}
CANDIDATE = {"privileged container": ("C-0057", "KSV-0017"), "hostPath mount": ("C-0048", "KSV-0023"),
             "host network": ("C-0041", "KSV-0009"), "host port": ("C-0044", "KSV-0024")}


def scanner_kappa(df, lines):
    """Cohen's kappa between Kubescape and Trivy: unit = (configuration, concept), 'fails anywhere in the config'.
    Trivy lists only failing checks, so an absent ID is a pass; Kubescape reports every control's status."""
    pairs, titles = [], {}
    for r in df.itertuples():
        name = r.source + "__" + r.project_id + ("" if r.source == "human" else f"__{r.prompt_variant}__s{r.sample_k}")
        d = os.path.join(HERE, "results", "raw", name)
        try:
            ks = json.load(open(os.path.join(d, "kubescape.json"), encoding="utf-8"))["summaryDetails"]["controls"]
            tv = json.load(open(os.path.join(d, "trivy.json"), encoding="utf-8"))
        except (OSError, KeyError, ValueError):
            continue
        tv_fail = set()
        for res in tv.get("Results") or []:
            for m in res.get("Misconfigurations") or []:
                if m.get("Status") == "FAIL":
                    tv_fail.add(m["ID"])
                    titles[m["ID"]] = m.get("Title")
        for concept, (kc, tc) in OVERLAP.items():
            st = ks.get(kc, {}).get("status")
            st = st.get("status") if isinstance(st, dict) else st
            if st not in ("passed", "failed"):
                continue
            pairs.append((concept, st == "failed", tc in tv_fail))
    lines.append("\n## Scanner agreement: Kubescape vs Trivy on overlapping checks (Cohen's κ)\n")
    lines.append("Unit: (configuration, concept); 'fails anywhere in the configuration'.\n")
    lines.append("| concept | n | both fail | KS only | Trivy only | both pass | κ |\n|---|---|---|---|---|---|---|")

    def kappa(rows):
        a = np.array([x for _, x, _ in rows]); t = np.array([y for _, _, y in rows])
        po = np.mean(a == t)
        pe = a.mean() * t.mean() + (1 - a.mean()) * (1 - t.mean())
        return (po - pe) / (1 - pe) if pe < 1 else np.nan, a, t

    for concept in list(OVERLAP) + ["ALL"]:
        rows = [p for p in pairs if concept == "ALL" or p[0] == concept]
        if not rows:
            continue
        k, a, t = kappa(rows)
        lines.append(f"| {concept} | {len(rows)} | {int(np.sum(a & t))} | {int(np.sum(a & ~t))} | {int(np.sum(~a & t))} | "
                     f"{int(np.sum(~a & ~t))} | {'n/a (no variance)' if np.isnan(k) else f'{k:.2f}'} |")
    seen = [f"{c}: {tc} = '{titles[tc]}'" for c, (_, tc) in CANDIDATE.items() if tc in titles]
    if seen:
        lines.append("\nCandidate pairs now observed (verify title, then move to OVERLAP): " + "; ".join(seen))


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    df.to_csv(os.path.join(OUT, "configs.csv"), index=False)
    lines = ["# K8sGenBench statistical report (generated by evaluation/stats.py; do not edit)\n",
             f"Configurations: {len(df)} ("
             + ", ".join(f"{s}={int((df.source == s).sum())}" for s in ["human"] + MODELS) + ")\n",
             "Missing cells are excluded, not imputed. A config that does not parse or deploy counts as a D5 failure;"
             " D5 time to Ready and D6 metrics are conditional on deployment.\n"]
    fr = df[df.gen_finish_reason.notna() & ~df.gen_finish_reason.astype(str).str.upper().isin(["STOP"])]
    lines.append("\n## Generations not ended by the model (provider stop reason; API-generated models only)\n")
    lines.append(md_table(fr.groupby(["source", "gen_finish_reason"]).size().reset_index(name="n"))
                 if len(fr) else "none")
    for v in ("neutral", "production"):
        t = describe(df, v)
        t.to_csv(os.path.join(OUT, f"summary_{v}.csv"), index=False)
        lines.append(f"\n## Descriptives: {v} prompt (human row = shipped manifests)\n")
        lines.append("Binary: % (yes/n). Continuous: median [IQR] n.\n")
        lines.append(md_table(t.set_index("source").T.reset_index().rename(columns={"index": "metric"})))
    neu = df[(df.prompt_variant == "neutral") | (df.source == "human")]
    compare_sources(neu, ["human"] + MODELS, "RQ1: neutral LLM configs vs human (configuration level)", lines, ref="human")
    compare_sources(neu, ["human"] + MODELS, "RQ1: neutral LLM configs vs human (configuration level)", lines,
                    ref="human", balanced=True)
    for intent in ("production", "demo"):
        compare_sources(neu[neu.human_intent == intent], ["human"] + MODELS,
                        f"RQ1 stratum: projects whose human manifest is {intent}-oriented", lines, ref="human")
    project_level_rq1(df, lines)
    for v in ("neutral", "production"):
        compare_sources(df[df.prompt_variant == v], MODELS, f"RQ3: LLM vs LLM, {v} prompt", lines)
        compare_sources(df[df.prompt_variant == v], MODELS, f"RQ3: LLM vs LLM, {v} prompt", lines, balanced=True)
    rq3_consistency(df, lines)
    rq5(df, lines)
    rq4(df, lines)
    rq2(df, lines)
    scanner_kappa(df, lines)
    contamination(df, lines)
    open(os.path.join(OUT, "report.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{len(df)} configs -> {OUT}\\report.md")


if __name__ == "__main__":
    main()
