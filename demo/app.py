"""K8sGenBench demo: what the study found, and a side-by-side comparison of any two configurations of a project.

    python demo/app.py            opens http://localhost:8800 in the browser (--no-browser to skip)

The page shows the study's recorded results (evaluation/results/): the headline numbers, a model x prompt overview
and a check-by-check comparison of a human manifest with an LLM-generated one. "Re-run live" runs the same pipeline
(D1-D4, and with the cluster also D5-D6) on a configuration now and reports how many values match the recorded result;
live results go to demo/runs/ (cleared at every start), never over the study's results. "Report" opens a printable page.
Standard library only (plus the study's own dependencies for live runs).
"""
import csv
import glob
import html
import json
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "evaluation", "results")
RUNS = os.path.join(HERE, "runs")
ROOT_CAUSES = os.path.join(ROOT, "evaluation", "d5_root_causes.csv")
PORT = 8800
TITLE = "Reliability and Security Analysis of LLM-Generated Kubernetes Configurations"
AUTHORS = "Nabeed Ali and Talha Hussain, NED University of Engineering and Technology"
PROJECTS = {"P02_n8n": "n8n", "P03_grafana": "Grafana", "P04_voting-app": "Voting App", "P05_emojivoto": "Emojivoto",
            "P07_online-boutique": "Online Boutique", "P08_sock-shop": "Sock Shop", "P10_k8s-dashboard": "Kubernetes Dashboard"}
MODELS = {"human": "Human", "claude": "Claude", "deepseek": "DeepSeek", "gemini": "Gemini", "gpt": "GPT", "qwen": "Qwen"}
DIMENSIONS = {"D1": "Correctness", "D2": "Security", "D3": "Static reliability", "D4": "Requirements",
              "D5": "Deployment on a real cluster", "D6": "Recovery from faults"}
# check -> (dimension, plain explanation, which direction is better for scores: "hi", "lo" or None)
HELP = {
    "YAML parses": ("D1", "The file is valid YAML (no syntax errors).", None),
    "Schema valid": ("D1", "Every object matches the official Kubernetes schema (kubeconform).", None),
    "API server accepts all objects": ("D1", "A real Kubernetes API server accepts every object (dry run: nothing is created).", None),
    "Security score (Kubescape, %)": ("D2", "Share of Kubescape security controls passed. Higher = more secure on paper.", "hi"),
    "Serious findings (Trivy)": ("D2", "High and critical security misconfigurations found by Trivy. Lower is better.", "lo"),
    "Pod Security level": ("D2", "Strictest Kubernetes Pod Security Standard the pods meet: privileged < baseline < restricted.", None),
    "Passwords in the file": ("D2", "Passwords or keys written directly in the manifest. 0 is best.", "lo"),
    "Best-practice score (Polaris)": ("D3", "Polaris best-practice score, 0-100. Higher is better.", "hi"),
    "Reliability checklist (%)": ("D3", "Share of our 10 reliability settings present (probes, replicas, limits, ...).", "hi"),
    "Bad-practice warnings (KubeLinter)": ("D3", "Warnings from KubeLinter. Lower is better.", "lo"),
    "Documented requirements met": ("D4", "Components and settings the project's documentation asks for that are present.", None),
    "All pods Ready": ("D5", "Every pod started and stayed Ready for 20 s on a real (kind) cluster.", None),
    "Time to Ready (s)": ("D5", "Seconds from deployment until every pod was Ready.", "lo"),
}
SMOKE_HELP = ("D5", "Smoke test step: a real request to the running application, with the expected answer.", None)
FAULT_HELP = ("D6", "We deleted a pod or crashed a container: did the application come back, and how fast?", None)
# root-cause category (evaluation/d5_root_causes.csv) -> plain-English sentence
CAUSES = {
    "compose_literalism_aux_only": "An extra helper service copied from the Docker Compose file fails, although the application itself works.",
    "hardening_breaks_db": "Security hardening (dropped permissions) stops the database from starting.",
    "hardening_breaks_aux": "Security hardening stops a helper service from starting.",
    "hardening_breaks_api_access": "Security hardening blocks the access the application needs to the Kubernetes API.",
    "hardening_breaks_dependency": "Security hardening stops a service the application depends on.",
    "invalid_yaml_or_object": "The file is invalid YAML, or Kubernetes rejects one of its objects.",
    "liveness_kills_slow_start": "A health check (liveness probe) kills a slow-starting service before it is up.",
    "probe_on_non_server_aux": "A health check is placed on a helper that does not serve requests, so it never becomes Ready.",
    "insufficient_rbac": "The application is not given the Kubernetes permissions it needs.",
    "invalid_rbac_object": "A permissions (RBAC) object is written wrongly and rejected.",
    "networkpolicy_blocks_path": "A network policy blocks traffic the application needs.",
    "empty_required_env": "A required setting (environment variable) is left empty, so the program exits.",
    "truncated_reply": "The model's answer was cut off, so the file is incomplete.",
    "no_output_recitation": "The model provider withheld the answer, so there is no file.",
    "hallucinated_flag": "The model invented a command-line option the program does not have.",
    "memory_limit_too_low": "The memory limit is too low, so containers are killed.",
    "probe_port_mismatch": "A health check probes the wrong port.",
    "wrong_service_port": "A Service sends traffic to the wrong port.",
    "unavailable_image": "A container image that does not exist is used.",
    "dangling_dependency": "The configuration points at a service it never creates.",
    "missing_referenced_secret": "A Secret that the configuration refers to is never created.",
    "wrong_api_server_endpoint": "The application is pointed at the wrong Kubernetes API address.",
    "unpinned_tag_drift": "An unpinned image tag now pulls a newer, incompatible version.",
    "probe_missing_binary": "A health check calls a program the image no longer contains.",
    "placeholder_domain_enforced": "A placeholder domain name is enforced, so every request is redirected nowhere.",
    "missing_writable_volume": "A container needs a writable folder it is not given.",
    "undetermined": "The cause could not be determined from the recorded evidence.",
}
JOBS = {}  # job id -> {"log": [str], "done": bool, "rc": int}

# Runs inside a child process: the study's evaluate(), with a progress line per stage and results kept in demo/runs/.
LIVE_RUNNER = r"""
import json, os, sys, uuid
sys.path.insert(0, os.path.join(sys.argv[1], "evaluation"))
import eval_runner as E, d2d3, d5d6
E.RESULTS_DIR = sys.argv[2]
cfg, runtime, cluster = sys.argv[3], sys.argv[4] == "1", sys.argv[5] == "1"
parts = cfg.split("__")
source, project = parts[0], parts[1]
variant, k = (parts[2], parts[3][1:]) if len(parts) == 4 else (None, None)
say = lambda s: print(s, flush=True)
r1 = lambda x: "-" if x is None else ("%.1f" % x if isinstance(x, float) else str(x))
yn = lambda b: "yes" if b else "no"
run_id = uuid.uuid4().hex[:8]
docs, text, _, err = E.load_docs_for_source(source, project, variant, k)
rec = {"project": project, "source": source, "prompt_variant": variant, "sample_k": k, "live": True,
       "d1_parse_ok": err is None, "d1_parse_error": err, "d1_n_documents": len(docs)}
say("Step 1/4  D1 correctness: " + ("YAML parses, %d objects" % len(docs) if err is None else "YAML does NOT parse: " + str(err)[:200]))
if err is None:
    rec["d1_kubeconform"] = E.d1_kubeconform(text)
    say("          schema valid (kubeconform): " + yn(rec["d1_kubeconform"].get("valid")))
    if cluster:
        rec["d1_server_dry_run"] = E.d1_server_dry_run(docs, run_id)
        dr = rec["d1_server_dry_run"]
        say("          API server accepts %s of %s objects" % (dr.get("objects_accepted"), dr.get("objects_total")))
    else:
        rec["d1_server_dry_run"] = {}
        say("          API server check skipped: cluster not running")
    say("Step 2/4  D2 security and D3 reliability: running Kubescape, Trivy, kube-score, Polaris, KubeLinter ...")
    st = d2d3.run_static(docs, text, os.path.join(sys.argv[2], "raw", cfg))
    rec.update({"loc": st["loc"], "d2": st["d2"], "d3": st["d3"]})
    rec["d2"]["pss"] = E.d2_pss(docs, run_id) if cluster else {"level": "not checked (cluster not running)"}
    say("          security score (Kubescape) %s%%, Pod Security level %s" % (r1(st["d2"]["kubescape"].get("compliance")), rec["d2"]["pss"].get("level")))
    say("          best-practice score (Polaris) %s, reliability checklist %s%%" % (r1(st["d3"]["polaris"].get("score")), r1(st["d3"]["checklist"].get("pct"))))
    rec["d4"] = E.d4_requirements(docs, project)
    say("Step 3/4  D4 requirements met: %s of %s" % (rec["d4"].get("requirements_met"), rec["d4"].get("requirements_total")))
    if not runtime:
        say("Step 4/4  D5/D6 deployment not requested (tick 'include deployment' to run it)")
    elif not cluster:
        say("Step 4/4  D5/D6 skipped: start the cluster first (python tools/setup_cluster.py)")
    else:
        say("Step 4/4  D5 deploying on the kind cluster, waiting for Ready, running the smoke test (3-8 min) ...")
        rec["d5"], rec["d6"] = d5d6.run_runtime(docs, project, run_id)
        d5 = rec["d5"]
        say("          all pods Ready: %s (%s/%s), smoke test %s" % (yn(d5.get("ready_ok")), d5.get("ready_replicas"),
            d5.get("expected_replicas"), "PASSED" if d5.get("smoke_ok") else "FAILED"))
        d6 = rec["d6"]
        say("          D6 " + ("faults injected; recovered from all: %s" % yn(all(x.get("recovery_ok") for f in ("pod_delete", "container_crash") for x in d6[f]))
                               if d6.get("ran") else "not run: %s" % d6.get("reason")))
json.dump(rec, open(os.path.join(sys.argv[2], cfg + ".json"), "w", encoding="utf-8"), indent=2)
say("DONE")
"""


# ---------------------------------------------------------------- data
def configs():
    """{project: [config names]} from the stored results, human first."""
    out = {}
    for f in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        name = os.path.basename(f)[:-5]
        out.setdefault(name.split("__")[1], []).append(name)
    for p in out:
        out[p].sort(key=lambda n: (not n.startswith("human"), n))
    return out


def manifest_text(cfg):
    parts = cfg.split("__")
    if parts[0] == "human":
        d = os.path.join(ROOT, "datasets", parts[1], "human")
        files = [os.path.join(d, "rendered.yaml")] if os.path.exists(os.path.join(d, "rendered.yaml")) else sorted(
            f for f in glob.glob(os.path.join(d, "*.y*ml")) if not os.path.basename(f).startswith("kustomization"))
        return "\n---\n".join(open(f, encoding="utf-8").read() for f in files)
    p = os.path.join(ROOT, "generation", "outputs", parts[0], parts[1], parts[2], parts[3], "manifest.yaml")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else "(no manifest: the model returned no usable file)"


def result(cfg, live=False):
    p = os.path.join(RUNS if live else RESULTS, cfg + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def root_cause(cfg):
    if os.path.exists(ROOT_CAUSES):
        for r in csv.DictReader(open(ROOT_CAUSES, encoding="utf-8")):
            if r["config"] == cfg:
                return r
    return None


def works(r):
    """True when the configuration deployed: all pods Ready and the smoke test passed; None when not deployed."""
    d5 = (r or {}).get("d5") or {}
    if r and not r.get("d1_parse_ok"):
        return False
    return bool(d5.get("ready_ok") and d5.get("smoke_ok")) if d5.get("ran") else None


def verdict(r):
    if r and not r.get("d1_parse_ok"):
        return "DOES NOT WORK (invalid file)"
    return {True: "WORKS (all pods Ready, smoke test passed)", False: "DOES NOT WORK",
            None: "static checks only (not deployed)"}[works(r)]


def summary(r):
    """Ordered list of (check, value, ok, score) for display; ok is True/False/None, score a number or None."""
    if not r:
        return []
    yn = lambda b: "yes" if b else "no"
    rows = [("YAML parses", yn(r.get("d1_parse_ok")), bool(r.get("d1_parse_ok")), None)]
    if not r.get("d1_parse_ok"):
        return rows + [("Error", str(r.get("d1_parse_error") or "no file"), False, None)]
    kc, dr = r.get("d1_kubeconform") or {}, r.get("d1_server_dry_run") or {}
    trivy = _dig(r, "d2", "trivy", "by_severity") or {}
    serious = (trivy.get("high") or 0) + (trivy.get("critical") or 0)
    secrets = _dig(r, "d2", "secrets", "count")
    ks, pol, chk = _dig(r, "d2", "kubescape", "compliance"), _dig(r, "d3", "polaris", "score"), _dig(r, "d3", "checklist", "pct")
    smells = _dig(r, "d3", "kube_linter", "zhang_total")
    d4 = r.get("d4") or {}
    rows += [("Schema valid", yn(kc.get("valid")), bool(kc.get("valid")), None),
             ("API server accepts all objects",
              f"{yn(dr.get('server_ok'))} ({dr.get('objects_accepted')} of {dr.get('objects_total')})" if dr else "not checked (cluster not running)",
              dr.get("server_ok"), None),
             ("Security score (Kubescape, %)", _num(ks), None, ks),
             ("Serious findings (Trivy)", str(serious), None, serious),
             ("Pod Security level", str(_dig(r, "d2", "pss", "level")), None, None),
             ("Passwords in the file", _num(secrets), (secrets or 0) == 0, secrets),
             ("Best-practice score (Polaris)", _num(pol), None, pol),
             ("Reliability checklist (%)", _num(chk), None, chk),
             ("Bad-practice warnings (KubeLinter)", _num(smells), None, smells),
             ("Documented requirements met", f"{d4.get('requirements_met')} of {d4.get('requirements_total')}",
              d4.get("requirements_met") == d4.get("requirements_total"), None)]
    d5, d6 = r.get("d5") or {}, r.get("d6") or {}
    if not d5.get("ran"):
        return rows + [("All pods Ready", "not deployed", None, None)]
    rows += [("All pods Ready", f"{yn(d5.get('ready_ok'))} ({d5.get('ready_replicas')} of {d5.get('expected_replicas')})", bool(d5.get("ready_ok")), None),
             ("Time to Ready (s)", _num(d5.get("time_to_ready_s")) if d5.get("ready_ok") else "-", None,
              d5.get("time_to_ready_s") if d5.get("ready_ok") else None)]
    for c in d5.get("smoke") or []:
        rows.append((f"Smoke test: {c.get('name')}", f"{'passed' if c.get('passed') else 'failed'} ({c.get('detail')})", bool(c.get("passed")), None))
    if d6.get("ran"):
        for f in ("pod_delete", "container_crash"):
            for i, x in enumerate(d6.get(f) or [], 1):
                rows.append((f"Fault: {f.replace('_', ' ')} #{i}",
                             f"{'recovered' if x.get('recovery_ok') else 'did NOT recover'} in {_num(x.get('recovery_time_s'))} s, "
                             f"available {_num(x.get('availability_pct'))}% of the time", bool(x.get("recovery_ok")), None))
    else:
        reason = "the application did not deploy" if "not_deployed" in str(d6.get("reason")) else d6.get("reason")
        rows.append(("Fault: injection", f"not run ({reason})", None, None))
    return rows


def help_for(check):
    return HELP.get(check) or (SMOKE_HELP if check.startswith("Smoke") else FAULT_HELP if check.startswith("Fault")
                               else ("D1", "Why the file could not be read.", None))


def label(cfg, short=False):
    p = cfg.split("__")
    if p[0] == "human":
        return "Human" if short else "Human (the project's own manifest)"
    return f"{MODELS.get(p[0], p[0])}, {p[2]} prompt, sample {p[3][1:]}"


def _dig(d, *ks):
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def _num(x):
    return "-" if x is None else (f"{x:.1f}" if isinstance(x, float) else str(x))


def _pct(n, d):
    return f"{n} of {d} ({100 * n / d:.0f}%)" if d else "-"


def cluster_up():
    kubectl = os.path.join(ROOT, "tools", "bin", "kubectl.exe")
    try:
        return subprocess.run([kubectl, "--context", "kind-k8sgen", "get", "--raw", "/readyz"], capture_output=True,
                              text=True, timeout=8).stdout.strip() == "ok"
    except Exception:
        return False


# ---------------------------------------------------------------- server-rendered blocks (page and report share them)
def headline_html():
    rs = [json.load(open(f, encoding="utf-8")) for f in glob.glob(os.path.join(RESULTS, "*.json"))]
    gen = [r for r in rs if r["source"] != "human"]
    valid = sum(bool((r.get("d1_kubeconform") or {}).get("valid")) for r in gen)
    ok = sum(bool(works(r)) for r in gen)
    by = {v: [r for r in gen if r.get("prompt_variant") == v] for v in ("neutral", "production")}
    ks = {v: statistics.median([x for x in (_dig(r, "d2", "kubescape", "compliance") for r in by[v]) if x is not None]) for v in by}
    okv = {v: sum(bool(works(r)) for r in by[v]) for v in by}
    fig = lambda big, small, cls="": f"<div class='fig {cls}'><b>{big}</b><span>{small}</span></div>"
    return ("<div class='figs'>"
            + fig(len(gen), f"configurations, written by five LLMs for {len(PROJECTS)} open-source applications")
            + fig(f"{100 * valid / len(gen):.1f}%", f"pass schema validation ({valid} of {len(gen)})")
            + fig(f"{100 * ok / len(gen):.1f}%", f"actually run: every pod Ready and the smoke test passed ({ok} of {len(gen)})", "hl")
            + fig(f"{okv['neutral']} &rarr; {okv['production']}",
                  f"working configurations (of {len(by['neutral'])}) once the prompt asks for production-ready output, "
                  f"while the median security score climbs from {ks['neutral']:.0f} to {ks['production']:.0f}")
            + "</div><blockquote class='lead'>A file that validates is not a deployment that works, and a better scanner "
              "score does not make it run. Generated manifests have to be deployed and tested, not only scanned.</blockquote>")


def overview_html():
    cells = {}
    for f in glob.glob(os.path.join(RESULTS, "*.json")):
        r = json.load(open(f, encoding="utf-8"))
        cells.setdefault((r["source"], r.get("prompt_variant") or "-"), []).append(r)

    def cell(src, v):
        rs = cells.get((src, v), [])
        if not rs:
            return "<td colspan='2'>-</td>"
        ok = sum(bool(works(r)) for r in rs)
        ks = [x for x in (_dig(r, "d2", "kubescape", "compliance") for r in rs) if x is not None]
        cls = "low" if ok / len(rs) < 0.5 else ""
        return (f"<td class='pick' data-src='{src}' data-v='{v}' title='Click to compare an example with the human manifest'>"
                f"<span class='bar {cls}'><i style='width:{100 * ok / len(rs):.0f}%'></i></span>{_pct(ok, len(rs))}</td>"
                f"<td class='num'>{statistics.median(ks):.1f}</td>")

    head = ("<table class='ov'><tr><th rowspan='2'>Source</th><th colspan='2'>Neutral prompt</th><th colspan='2'>Production prompt</th></tr>"
            "<tr><th>Works on the cluster</th><th>Security score</th><th>Works on the cluster</th><th>Security score</th></tr>")
    rows = [f"<tr><td><b>Human</b> <span class='muted'>(the 7 projects' own manifests)</span></td>{cell('human', '-')}"
            "<td colspan='2' class='muted'>no prompt</td></tr>"]
    rows += [f"<tr><td><b>{MODELS[m]}</b></td>{cell(m, 'neutral')}{cell(m, 'production')}</tr>" for m in MODELS if m != "human"]
    return (head + "".join(rows) + "</table><p class='muted'>Security score = median Kubescape compliance (%). "
            "Works = all pods Ready and the smoke test passed. Click a cell to compare one of its configurations with the "
            "human manifest of the selected project.</p>")


def compare_html(a, b):
    ra, rb = result(a), result(b)
    sa, sb = {c: (v, ok, s) for c, v, ok, s in summary(ra)}, {c: (v, ok, s) for c, v, ok, s in summary(rb)}
    order = [c for c, *_ in summary(ra)] + [c for c, *_ in summary(rb) if c not in sa]
    order.sort(key=lambda c: help_for(c)[0])  # stable: keeps the check order within a dimension
    cl = lambda ok: "ok" if ok is True else "bad" if ok is False else ""
    body, last = [], None
    for c in order:
        dim, tip, better = help_for(c)
        if dim != last:
            body.append(f"<tr class='dim'><td colspan='3'>{dim} {DIMENSIONS[dim]}</td></tr>")
            last = dim
        (va, oka, xa), (vb, okb, xb) = sa.get(c, ("-", None, None)), sb.get(c, ("-", None, None))
        wa = wb = ""
        if better and xa is not None and xb is not None and xa != xb:
            wa, wb = ("win", "") if (xa > xb) == (better == "hi") else ("", "win")
        key = " key" if c in ("Security score (Kubescape, %)", "All pods Ready") or c.startswith("Smoke") else ""
        body.append(f"<tr class='{key.strip()}'><td>{html.escape(c)} <span class='tip' title='{html.escape(tip)}'>?</span></td>"
                    f"<td class='{cl(oka)} {wa}'>{html.escape(va)}</td><td class='{cl(okb)} {wb}'>{html.escape(vb)}</td></tr>")

    def side(cfg, r):
        v = verdict(r)
        cls = "v-ok" if v.startswith("WORKS") else "v-bad" if v.startswith("DOES") else "v-na"
        rc = root_cause(cfg)
        cause = (f"<p class='cause'><b>Why it fails:</b> {html.escape(CAUSES.get(rc['category'], rc['category']))}"
                 f"<br><span class='muted'>Detail: {html.escape(rc['mechanism'])}</span></p>") if rc else ""
        return f"<div><h3>{html.escape(label(cfg))}</h3><span class='verdict {cls}'>{v}</span>{cause}</div>"

    return (f"<div class='sentence'>{html.escape(sentence(a, b, ra, rb))}</div>"
            f"<div class='sides'>{side(a, ra)}{side(b, rb)}</div>"
            f"<table class='cmp'><tr><th>Check <span class='muted'>(hover ? for an explanation)</span></th>"
            f"<th>{html.escape(label(a, True))}</th><th>{html.escape(label(b, True))}</th></tr>{''.join(body)}</table>")


def sentence(a, b, ra, rb):
    """One plain sentence: who has the higher security score, and who actually works."""
    la, lb = label(a, True), label(b, True)
    ka, kb = _dig(ra, "d2", "kubescape", "compliance"), _dig(rb, "d2", "kubescape", "compliance")
    wa, wb = works(ra), works(rb)
    yn = {True: "works", False: "does not work", None: "was not deployed"}
    if ka is None or kb is None:
        sec = "Security scores cannot be compared (one file is invalid)."
    elif abs(ka - kb) < 0.05:
        sec = f"Both have the same security score ({ka:.1f})."
    else:
        hi, lo, kh, kl = (lb, la, kb, ka) if kb > ka else (la, lb, ka, kb)
        sec = f"{hi} has the higher security score ({kh:.1f} vs {kl:.1f}, +{kh - kl:.1f})."
    if wa == wb:
        run = f" On the real cluster, both {yn[wa].replace('does', 'do').replace('works', 'work').replace('was', 'were')}."
    else:
        run = f" On the real cluster, {la} {yn[wa]} and {lb} {yn[wb]}."
    hi_side = None if ka is None or kb is None or abs(ka - kb) < 0.05 else (wb if kb > ka else wa)
    if hi_side is False and wa != wb:
        run += " The higher score did not make it run."
    return sec + run


GLOSSARY = "".join(f"<tr><td>{d}</td><td>{n}</td></tr>" for d, n in [
    ("D1 Correctness", "Is the file valid YAML, does it match the Kubernetes schema, and does a real API server accept it?"),
    ("D2 Security", "Static security scanners: Kubescape (score %), Trivy (serious findings), Pod Security Standard level, passwords in the file."),
    ("D3 Static reliability", "Polaris and KubeLinter best-practice checks, and our 10-point reliability checklist (probes, replicas, limits...)."),
    ("D4 Requirements", "Are the components and settings that the project's documentation asks for present?"),
    ("D5 Deployment", "Deploy on a real kind cluster: do all pods become Ready, and does a smoke test (real requests to the app) pass?"),
    ("D6 Recovery", "Delete a pod and crash a container: does the application recover, and how fast?"),
    ("Works", "All pods Ready (D5) and the smoke test passed (D5)."),
    ("Neutral / production prompt", "Each model was asked once plainly and once for 'production-ready' output, 3 samples each.")])


# ---------------------------------------------------------------- live runs
def start_job(args):
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"log": [], "done": False}

    def work():
        t0 = time.time()
        p = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        for line in p.stdout:
            JOBS[jid]["log"].append(f"[{time.time() - t0:4.0f} s] {line.rstrip()}")
        p.wait()
        JOBS[jid]["rc"] = p.returncode
        JOBS[jid]["done"] = True

    threading.Thread(target=work, daemon=True).start()
    return jid


def live_check(cfg):
    """How many live values equal the recorded ones, and which differ (values the live run did not measure are skipped)."""
    rec, live = {c: v for c, v, *_ in summary(result(cfg))}, summary(result(cfg, True))
    skip = ("not checked", "not deployed", "not run")
    pairs = [(c, rec[c], v) for c, v, *_ in live if c in rec and not v.startswith(skip) and not rec[c].startswith(skip)]
    return {"match": sum(r == v for _, r, v in pairs), "total": len(pairs),
            "diffs": [[c, r, v] for c, r, v in pairs if r != v], "verdict": verdict(result(cfg, True))}


def live_line(cfg):
    if not result(cfg, True):
        return ""
    lc = live_check(cfg)
    return (f"<p class='muted'>Re-run live during this session: {lc['match']} of {lc['total']} values reproduced the recorded "
            f"result{'' if not lc['diffs'] else ' (differences: ' + html.escape('; '.join(f'{c}: {r} vs {v}' for c, r, v in lc['diffs'])) + ')'}.</p>")


# ---------------------------------------------------------------- pages
CSS = """
:root{--ink:#1b1a17;--muted:#6f6a60;--line:#e2ddd2;--paper:#faf8f3;--ok:#2f6b3f;--bad:#a3341f;--acc:#a3341f;
 --serif:"Source Serif 4",Charter,Georgia,serif;--sans:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;--mono:"IBM Plex Mono",Consolas,monospace}
body{font-family:var(--serif);margin:0;color:var(--ink);background:var(--paper);font-size:17px;line-height:1.5}
header,main{max-width:1080px;margin:auto;padding-left:32px;padding-right:32px}
header{padding-top:48px;padding-bottom:20px;border-bottom:2px solid var(--ink)}
.kicker{font:600 12px/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--acc)}
header h1{font-size:42px;line-height:1.1;font-weight:600;margin:12px 0 10px;letter-spacing:-.01em;max-width:30ch}
header p{margin:0;color:var(--muted);font-size:16px}
main{padding-bottom:80px}
h2{font-size:25px;font-weight:600;margin:56px 0 4px;letter-spacing:-.005em}
h2 .n{font:600 13px var(--sans);color:var(--acc);margin-right:12px;vertical-align:4px}
.intro{color:var(--muted);margin:0 0 16px;max-width:68ch}
h3{font-size:17px;margin:0 0 6px;font-weight:600}
.card{min-width:0}
.figs{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--line);margin-top:20px}
.fig{padding:4px 22px 22px;border-left:1px solid var(--line)}.fig:first-child{border-left:0;padding-left:0}
.fig b{display:block;font-size:46px;font-weight:500;line-height:1.1;margin-bottom:8px;font-variant-numeric:lining-nums}
.fig.hl b{color:var(--acc)}.fig span{font:14px/1.45 var(--sans);color:var(--muted);display:block}
.lead{font-size:23px;font-style:italic;line-height:1.4;margin:28px 0 0;padding:0;max-width:44ch}
table{border-collapse:collapse;width:100%;font:14px/1.45 var(--sans);border-top:2px solid var(--ink);border-bottom:2px solid var(--ink)}
td,th{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{font-weight:600;font-size:13px;border-bottom:1px solid var(--ink)}
.ov tr:first-child th{border-bottom:1px solid var(--line)}.num{font-variant-numeric:tabular-nums}
.bar{display:inline-block;width:64px;height:5px;background:#e9e4d9;margin-right:10px;vertical-align:middle}
.bar i{display:block;height:100%;background:var(--ink)}.bar.low i{background:var(--acc)}
.ov td.pick{cursor:pointer;font-variant-numeric:tabular-nums}.ov td.pick:hover{background:#f1ede3}
.bar-row{display:flex;gap:14px;flex-wrap:wrap;align-items:center;font:14px var(--sans);margin:4px 0 8px}
select,button{font:14px var(--sans);padding:7px 10px;border-radius:2px;border:1px solid #c9c2b4;background:#fff;color:var(--ink)}
button{background:var(--ink);color:var(--paper);border-color:var(--ink);cursor:pointer}button.sec{background:transparent;color:var(--ink)}
button:hover{background:#000}button.sec:hover{background:#f1ede3}button:disabled{opacity:.4;cursor:default}
.sentence{font-size:21px;line-height:1.45;margin:22px 0 18px;padding-left:18px;border-left:3px solid var(--acc);max-width:62ch}
.sides{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-bottom:16px}
.cmp td:nth-child(2),.cmp td:nth-child(3),.cmp th:nth-child(2),.cmp th:nth-child(3){width:34%}
.cmp tr.dim td{font:600 11px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);padding-top:20px;border-bottom:1px solid var(--ink)}
.cmp tr.key td:first-child{font-weight:600}.win{background:#e8efe2}
.ok{color:var(--ok)}.bad{color:var(--bad)}
.tip{display:inline-block;width:14px;height:14px;line-height:13px;text-align:center;border-radius:50%;border:1px solid #b9b2a4;color:var(--muted);font-size:10px;cursor:help;margin-left:3px}
.verdict{font:600 12px var(--sans);letter-spacing:.08em;text-transform:uppercase;display:inline-block;margin:2px 0 8px;padding:4px 0;border-bottom:2px solid}
.v-ok{color:var(--ok)}.v-bad{color:var(--bad)}.v-na{color:var(--muted)}
.cause{margin:4px 0;font-size:16px}.cause .muted{font-size:13px}.muted{color:var(--muted);font:13px/1.45 var(--sans)}
details{margin-top:16px;font-family:var(--sans);font-size:14px}summary{cursor:pointer;font-weight:600}
pre{background:#22201b;color:#ebe5d6;font:11.5px/1.5 var(--mono);padding:12px 14px;max-height:380px;overflow:auto;white-space:pre}
.pre2{display:grid;grid-template-columns:1fr 1fr;gap:20px}.pre2>div{min-width:0}
.pill{font:600 12px var(--sans)}
.legend td:first-child{white-space:nowrap;font-weight:600;width:200px}
footer{border-top:1px solid var(--line);margin-top:56px;padding-top:14px;font:13px var(--sans);color:var(--muted)}
@media(max-width:900px){.figs{grid-template-columns:1fr 1fr}.fig:nth-child(3){border-left:0;padding-left:0}.sides,.pre2{grid-template-columns:1fr}header h1{font-size:32px}}
@media print{.noprint{display:none}body{background:#fff;font-size:12pt}.fig,table{break-inside:avoid}h2{margin-top:28px}}
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400..600;1,8..60,400&display=swap">')

INDEX = """<!doctype html><html><head><meta charset="utf-8"><title>K8sGenBench demo</title>__FONTS__<style>__CSS__</style></head><body>
<header><div class="kicker">K8sGenBench &middot; research demo</div><h1>Can LLMs write Kubernetes configurations that really work?</h1>
<p>__TITLE__<br>__AUTHORS__</p></header>
<main>
<h2 style="margin-top:36px"><span class="n">01</span>What we found</h2>
<div id="headline">loading...</div>

<h2><span class="n">02</span>Every model, both prompts</h2>
<p class="intro">Each model wrote three configurations per project under each prompt. The human row is what the projects ship themselves.</p>
<div class="card" id="overview">loading...</div>

<h2><span class="n">03</span>One project, two configurations</h2>
<p class="intro">The same checks on both sides. Green marks the better score; the bottom rows show what happened on a real cluster.</p>
<div class="card">
 <div class="bar-row noprint">
  <label>Project <select id="proj"></select></label>
  <label>Left <select id="a"></select></label>
  <label>Right <select id="b"></select></label>
  <button onclick="report()">Open printable report</button>
 </div>
 <div id="cmp">loading...</div>
 <details><summary>Show the two manifests (YAML)</summary><div class="pre2"><div><h3 id="ma-t"></h3><pre id="ma"></pre></div><div><h3 id="mb-t"></h3><pre id="mb"></pre></div></div></details>
</div>

<h2 class="noprint"><span class="n">04</span>Run it again, now</h2>
<div class="card noprint">
 <p class="intro">Runs the study's own tools on the selected configuration and checks the numbers against the recorded ones. Static checks (D1-D4) take a few seconds.</p>
 <div class="bar-row">
  <button class="sec" id="runa" onclick="live('a')">Re-run left</button>
  <button class="sec" id="runb" onclick="live('b')">Re-run right</button>
  <label class="muted"><input type="checkbox" id="rt"> include deployment (D5/D6: needs the cluster, 3-8 min)</label>
  <span id="cl" class="pill"></span>
 </div>
 <div id="logbox" style="display:none"><div id="status" class="verdict v-na"></div><div id="diffs"></div>
  <details open><summary>Progress log</summary><pre id="log"></pre></details></div>
</div>

<h2><span class="n">05</span>What the checks mean</h2>
<div class="card"><table class="legend">__GLOSSARY__</table></div>
<footer>Data and code: github.com/nabeedjamshedali/k8sgenbench</footer>
</main>
<script>
const $=id=>document.getElementById(id);
const NAMES=__NAMES__;
let CFG={},PROJ={},timer=null;
const get=async u=>(await fetch(u)).json(), txt=async u=>(await fetch(u)).text();
function label(n){const p=n.split('__');return p[0]=='human'?'Human (the project’s own manifest)':NAMES[p[0]]+', '+p[2]+' prompt, sample '+p[3].slice(1)}
async function init(){
 [CFG,PROJ]=await Promise.all([get('/api/configs'),get('/api/projects')]);
 $('headline').innerHTML=await txt('/api/headline');$('overview').innerHTML=await txt('/api/overview');
 document.querySelectorAll('td.pick').forEach(td=>td.onclick=()=>pick(td.dataset.src,td.dataset.v));
 $('proj').innerHTML=Object.keys(CFG).map(p=>`<option value="${p}">${PROJ[p]||p}</option>`).join('');
 $('proj').value='P04_voting-app';$('proj').onchange=()=>fill();
 $('a').onchange=show;$('b').onchange=show;
 fill('human__P04_voting-app','claude__P04_voting-app__production__s1');cluster()}
function fill(a,b){const l=CFG[$('proj').value];const o=l.map(n=>`<option value="${n}">${label(n)}</option>`).join('');
 $('a').innerHTML=o;$('b').innerHTML=o;$('a').value=a||l[0];$('b').value=b||l.find(n=>n.startsWith('claude'))||l[1];show()}
function pick(src,v){const p=$('proj').value,l=CFG[p];
 const n=src=='human'?l[0]:l.find(x=>x.startsWith(src+'__'+p+'__'+v+'__'));
 if(!n){alert(NAMES[src]+' has no '+v+'-prompt configuration for '+PROJ[p]+' (its prompt exceeded the provider’s request limit).');return}
 if(src=='human')$('a').value=n;else{$('a').value=l[0];$('b').value=n}
 show();$('cmp').scrollIntoView({behavior:'smooth',block:'start'})}
async function show(){resetLive();const a=$('a').value,b=$('b').value;
 $('cmp').innerHTML=await txt('/api/compare?a='+a+'&b='+b);
 const [ma,mb]=await Promise.all([get('/api/manifest?name='+a),get('/api/manifest?name='+b)]);
 $('ma-t').textContent=label(a);$('mb-t').textContent=label(b);$('ma').textContent=ma.text;$('mb').textContent=mb.text}
async function cluster(){const u=(await get('/api/cluster')).up;
 $('cl').textContent=u?'cluster: running':'cluster: stopped (static checks only)';$('cl').style.color=u?'var(--ok)':'var(--muted)'}
function status(t,cls){$('status').textContent=t;$('status').className='verdict '+cls}
function busy(b){$('runa').disabled=b;$('runb').disabled=b}
function resetLive(){if(timer){clearInterval(timer);timer=null}busy(false);$('logbox').style.display='none'}
async function live(s){if(timer)return;const n=$(s).value;busy(true);
 $('logbox').style.display='';$('log').textContent='';$('diffs').innerHTML='';const t0=Date.now();
 status('Re-running '+label(n)+' ... 0 s','v-na');
 const j=await (await fetch('/api/run?name='+n+'&runtime='+($('rt').checked?1:0),{method:'POST'})).json();
 timer=setInterval(async()=>{const st=await get('/api/log?id='+j.id);if(!timer)return;
  $('log').textContent=st.log.join('\\n');$('log').scrollTop=1e9;const sec=Math.round((Date.now()-t0)/1000);
  if(!st.done){status('Re-running '+label(n)+' ... '+sec+' s','v-na');return}
  clearInterval(timer);timer=null;busy(false);
  if(st.rc!==0){status('Run FAILED (exit code '+st.rc+'): see the log','v-bad');return}
  const d=await get('/api/live?name='+n);
  status('Done in '+sec+' s: '+d.match+' of '+d.total+' values reproduced the recorded study result'+(d.match==d.total?'.':' (see below).'),d.match==d.total?'v-ok':'v-bad');
  $('diffs').innerHTML=d.diffs.length?'<table><tr><th>Check</th><th>Recorded</th><th>Live</th></tr>'+d.diffs.map(x=>`<tr><td>${x[0]}</td><td>${x[1]}</td><td>${x[2]}</td></tr>`).join('')+'</table>':''},1500)}
function report(){window.open('/report?a='+$('a').value+'&b='+$('b').value)}
init();
</script></body></html>""".replace("__CSS__", CSS).replace("__FONTS__", FONTS).replace("__TITLE__", TITLE).replace("__AUTHORS__", AUTHORS).replace(
    "__GLOSSARY__", GLOSSARY).replace("__NAMES__", json.dumps({k: v for k, v in MODELS.items() if k != "human"}))


def report_page(a, b):
    method = ("Each model saw only the project's own documentation and was asked for a configuration with a neutral and a "
              "production-oriented prompt, three times each. Every configuration, and the project's own manifest, was "
              "checked with the same tools: D1 to D4 by static analysis, D5 and D6 by deploying it on a real kind cluster.")
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>K8sGenBench report</title>{FONTS}<style>{CSS}</style></head><body>"
            f"<header><div class='kicker'>K8sGenBench &middot; comparison report &middot; {html.escape(PROJECTS[a.split('__')[1]])}</div>"
            f"<h1 style='max-width:none;font-size:34px'>{TITLE}</h1><p>{AUTHORS}<br>Generated {time.strftime('%Y-%m-%d %H:%M')}</p></header><main>"
            f"<p class='noprint' style='margin-top:24px'><button onclick='print()'>Save as PDF / print</button></p>"
            f"<h2><span class='n'>01</span>Study summary</h2>{headline_html()}"
            f"<h2><span class='n'>02</span>Method</h2><p style='max-width:68ch'>{method}</p>"
            f"<h2><span class='n'>03</span>{html.escape(label(a))} vs {html.escape(label(b))}</h2>"
            f"<div class='card'>{compare_html(a, b)}{live_line(a)}{live_line(b)}</div>"
            f"<h2><span class='n'>04</span>What the checks mean</h2><div class='card'><table class='legend'>{GLOSSARY}</table></div>"
            f"<footer>Data and code: github.com/nabeedjamshedali/k8sgenbench</footer></main></body></html>")


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json", code=200):
        data = (json.dumps(body) if ctype == "application/json" else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        known = {n for l in configs().values() for n in l}
        name, a, b = (q.get(k, "") for k in ("name", "a", "b"))
        if u.path == "/":
            return self._send(INDEX, "text/html")
        if u.path == "/api/configs":
            return self._send(configs())
        if u.path == "/api/projects":
            return self._send(PROJECTS)
        if u.path == "/api/cluster":
            return self._send({"up": cluster_up()})
        if u.path == "/api/headline":
            return self._send(headline_html(), "text/html")
        if u.path == "/api/overview":
            return self._send(overview_html(), "text/html")
        if u.path in ("/api/compare", "/report") and {a, b} <= known:
            return self._send((compare_html if u.path == "/api/compare" else report_page)(a, b), "text/html")
        if u.path == "/api/manifest" and name in known:
            return self._send({"text": manifest_text(name)})
        if u.path == "/api/live" and name in known and result(name, True):
            return self._send(live_check(name))
        if u.path == "/api/log":
            j = JOBS.get(q.get("id"), {"log": ["unknown job"], "done": True, "rc": 1})
            return self._send({"log": j["log"], "done": j["done"], "rc": j.get("rc")})
        self._send("not found or unknown configuration name", "text/plain", 404)

    def do_POST(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/api/run" and q.get("name") in {n for l in configs().values() for n in l}:
            os.makedirs(RUNS, exist_ok=True)
            jid = start_job([sys.executable, "-u", "-c", LIVE_RUNNER, ROOT, RUNS, q["name"], q.get("runtime", "0"),
                             "1" if cluster_up() else "0"])
            return self._send({"id": jid})
        self._send("not found or unknown configuration name", "text/plain", 404)


if __name__ == "__main__":
    shutil.rmtree(RUNS, ignore_errors=True)  # live results are for this session only
    ThreadingHTTPServer.allow_reuse_address = False  # on Windows reuse lets a second copy bind the same port silently
    server = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"K8sGenBench demo on http://localhost:{PORT}  (Ctrl+C to stop)")
    if "--no-browser" not in sys.argv:
        import webbrowser
        threading.Timer(1.0, webbrowser.open, [f"http://localhost:{PORT}"]).start()
    server.serve_forever()
