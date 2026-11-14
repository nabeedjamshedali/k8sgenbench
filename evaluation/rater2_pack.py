"""Build a blind evidence pack for a second root-cause labelling pass (evaluation/d5_root_causes.csv is the first).

Writes, outside the repository (argument 1, default: a scratch folder):
  pack/cases/<CASE>.md        evidence for one case: D1 status, D5 status, smoke results, cluster diagnostics
  pack/cases/<CASE>.yaml      the configuration as evaluated
  pack/categories.md          the label set with definitions (the same set as tables.THEMES)
  pack/answer_template.csv    case_id,category,evidence_level
and, in the repository, evaluation/rater2_key.csv mapping case ids to configurations (never given to the rater).
Model names are removed from every evidence text so that the labelling is blind to the source.
"""
import glob
import json
import os
import random
import re
import shutil
import sys

import pandas as pd

import tables

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "rater2_pack")
SCRUB = re.compile(r"claude|deepseek|gemini|gpt|qwen|chatgpt|anthropic|openai|human", re.I)


def scrub(s):
    return SCRUB.sub("X", str(s))


def manifest_text(cfg):
    if cfg.startswith("human__"):
        proj = cfg.split("__")[1]
        files = sorted(glob.glob(os.path.join(ROOT, "datasets", proj, "human", "**", "*.y*ml"), recursive=True))
        return "\n---\n".join(open(f, encoding="utf-8", errors="replace").read() for f in files)
    src, proj, var, s = cfg.split("__")
    return open(os.path.join(ROOT, "generation", "outputs", src, proj, var, s, "manifest.yaml"),
                encoding="utf-8", errors="replace").read()


def evidence(cfg, finish):
    r = json.load(open(os.path.join(HERE, "results", cfg + ".json"), encoding="utf-8"))
    d5 = r.get("d5") or {}
    L = [f"# Case evidence", "", f"Project: {r['project']}", f"Prompt: {r.get('prompt_variant') or 'n/a (shipped manifest)'}",
         f"Generation stop reason: {finish}", "",
         "## D1 (parse, schema, API server dry-run)", f"- parses: {r.get('d1_parse_ok')}"]
    if r.get("d1_parse_error"):
        L.append(f"- parse error: {str(r['d1_parse_error'])[:600]}")
    kc = r.get("d1_kubeconform") or {}
    L.append(f"- schema valid: {kc.get('valid')}")
    for e in (kc.get("details") or [])[:8]:
        L.append(f"  - schema error: {e.get('kind')}/{e.get('name')}: {str(e.get('msg'))[:300]}")
    dr = r.get("d1_server_dry_run") or {}
    L.append(f"- API server accepted all objects: {dr.get('server_ok')} "
             f"({dr.get('objects_accepted')}/{dr.get('objects_total')} objects)")
    for e in (dr.get("errors") or [])[:8]:
        L.append(f"  - rejected: {str(e)[:400]}")
    L += ["", "## D5 (deployment)", f"- applied: {d5.get('apply_ok')}", f"- fully Ready: {d5.get('ready_ok')} "
          f"({d5.get('ready_replicas')}/{d5.get('expected_replicas')} replicas)", f"- failure class: {d5.get('failure_reason')}",
          f"- smoke test passed: {d5.get('smoke_ok')}"]
    for e in (d5.get("apply_errors") or [])[:6]:
        L.append(f"  - apply error: {str(e)[:400]}")
    for w in d5.get("workloads") or []:
        L.append(f"  - workload: {json.dumps(w)[:300]}")
    for i in d5.get("images") or []:
        if isinstance(i, dict) and not i.get("as_written_pullable", True):
            L.append(f"  - image not pullable as written: {i.get('ref')} (served: {i.get('served')})")
    for sh in d5.get("shims_applied") or []:
        L.append(f"  - start-up prerequisite supplied by the evaluator: {json.dumps(sh)}")
    L += ["", "### Smoke checks"]
    for c in d5.get("smoke") or []:
        L.append(f"- {c.get('name')}: passed={c.get('passed')} | {str(c.get('detail'))[:300]}")
    diag = d5.get("diagnostics") or {}
    L += ["", "### Cluster record at the Ready deadline (captured only if not Ready)"]
    for p in diag.get("pods") or []:
        L.append(f"- container {p.get('container')} (pod {p.get('pod')}): restarts={p.get('restarts')} "
                 f"last_exit={p.get('last_exit')} reason={p.get('last_reason')}")
        if p.get("last_log"):
            L.append("  last log lines:\n  ```\n  " + str(p["last_log"])[-1500:].replace("\n", "\n  ") + "\n  ```")
    for k, n in list((diag.get("warning_events") or {}).items())[:12]:
        L.append(f"- warning event x{n}: {k[:250]}")
    if not diag:
        L.append("- (none: the configuration was Ready, did not deploy, or failed before deployment)")
    return scrub("\n".join(L))


def main():
    rc = pd.read_csv(os.path.join(HERE, "d5_root_causes.csv"))
    res = pd.read_csv(os.path.join(HERE, "results", "results.csv"))
    res["config"] = res.apply(lambda x: f"human__{x.project_id}" if x.source == "human" else
                              f"{x.source}__{x.project_id}__{x.prompt_variant}__s{int(x.sample_k)}", axis=1)
    finish = dict(zip(res.config, res.gen_finish_reason))
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "cases"))
    configs = list(rc.config)
    random.Random(20261114).shuffle(configs)
    key = []
    for i, cfg in enumerate(configs, 1):
        cid = f"C{i:02d}"
        key.append((cid, cfg))
        open(os.path.join(OUT, "cases", cid + ".md"), "w", encoding="utf-8").write(
            evidence(cfg, finish.get(cfg, "n/a")).replace("# Case evidence", f"# Case {cid}", 1))
        open(os.path.join(OUT, "cases", cid + ".yaml"), "w", encoding="utf-8").write(scrub(manifest_text(cfg)))
    cats = ["# Root-cause categories", "",
            "Assign exactly one category per case: the mechanism that explains why the configuration was not both fully "
            "Ready and passing its smoke test. Evidence level: `observed` if the case evidence shows the mechanism "
            "directly (an error message, exit reason or event naming it), `inferred` if you reconstruct it from the "
            "manifest together with the observed status, `undetermined` if neither is possible (use category "
            "`undetermined`).", ""]
    for theme, items in tables.THEMES:
        cats.append(f"## {theme}")
        cats += [f"- `{c}`: {lab}" for c, lab in items]
        cats.append("")
    open(os.path.join(OUT, "categories.md"), "w", encoding="utf-8").write("\n".join(cats))
    open(os.path.join(OUT, "answer_template.csv"), "w", encoding="utf-8").write(
        "case_id,category,evidence_level\n" + "".join(f"{c},,\n" for c, _ in key))
    pd.DataFrame(key, columns=["case_id", "config"]).to_csv(os.path.join(HERE, "rater2_key.csv"), index=False)
    print(f"{len(key)} cases -> {OUT}")


if __name__ == "__main__":
    main()
