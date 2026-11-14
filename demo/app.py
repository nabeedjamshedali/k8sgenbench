"""K8sGenBench demo: compare a project's human manifest with an LLM-generated one.

    python demo/app.py            then open http://localhost:8800

Recorded mode shows the stored study results (evaluation/results/) instantly. "Run live" re-runs the same
pipeline (D1-D4, and with the cluster also D5-D6) on the chosen configuration; live results are written to
demo/runs/, never over the study's results. "Report" opens a printable side-by-side comparison.
Standard library only (plus the study's own dependencies for live runs).
"""
import glob
import html
import json
import os
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
PROJECTS = {"P02_n8n": "n8n", "P03_grafana": "Grafana", "P04_voting-app": "Voting App", "P05_emojivoto": "Emojivoto",
            "P07_online-boutique": "Online Boutique", "P08_sock-shop": "Sock Shop", "P10_k8s-dashboard": "Kubernetes Dashboard"}
JOBS = {}  # job id -> {"log": [str], "done": bool, "config": str}

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
run_id = uuid.uuid4().hex[:8]
docs, text, _, err = E.load_docs_for_source(source, project, variant, k)
rec = {"project": project, "source": source, "prompt_variant": variant, "sample_k": k, "live": True,
       "d1_parse_ok": err is None, "d1_parse_error": err, "d1_n_documents": len(docs)}
say(f"D1  parse: {'OK, %d objects' % len(docs) if err is None else 'FAILED: ' + str(err)[:200]}")
if err is None:
    rec["d1_kubeconform"] = E.d1_kubeconform(text)
    say(f"D1  schema valid (kubeconform): {rec['d1_kubeconform'].get('valid')}")
    if cluster:
        rec["d1_server_dry_run"] = E.d1_server_dry_run(docs, run_id)
        dr = rec["d1_server_dry_run"]
        say(f"D1  API server dry-run: {dr.get('objects_accepted')}/{dr.get('objects_total')} objects accepted")
    else:
        rec["d1_server_dry_run"] = {}
        say("D1  API server dry-run skipped: cluster not running")
    say("D2/D3 running Kubescape, Trivy, kube-score, Polaris, KubeLinter ...")
    st = d2d3.run_static(docs, text, os.path.join(sys.argv[2], "raw", cfg))
    rec.update({"loc": st["loc"], "d2": st["d2"], "d3": st["d3"]})
    rec["d2"]["pss"] = E.d2_pss(docs, run_id) if cluster else {"level": "not checked (cluster not running)"}
    say(f"D2  Kubescape compliance {st['d2']['kubescape'].get('compliance')}; Pod Security level {rec['d2']['pss'].get('level')}")
    say(f"D3  Polaris {st['d3']['polaris'].get('score')}; reliability checklist {st['d3']['checklist'].get('pct')}%")
    rec["d4"] = E.d4_requirements(docs, project)
    say(f"D4  requirements met {rec['d4'].get('requirements_met')}/{rec['d4'].get('requirements_total')}")
    if runtime and not cluster:
        say("D5/D6 skipped: start the cluster first (python tools/setup_cluster.py)")
    if runtime and cluster:
        say("D5  deploying on the kind cluster, waiting for Ready, running the smoke test ...")
        rec["d5"], rec["d6"] = d5d6.run_runtime(docs, project, run_id)
        d5 = rec["d5"]
        say(f"D5  fully Ready {d5.get('ready_ok')} ({d5.get('ready_replicas')}/{d5.get('expected_replicas')}), "
            f"smoke test {'PASSED' if d5.get('smoke_ok') else 'FAILED'}")
        d6 = rec["d6"]
        say("D6  " + ("faults injected; recovered from all: %s" % all(x.get("recovery_ok") for f in ("pod_delete", "container_crash") for x in d6[f])
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
    return open(p, encoding="utf-8").read() if os.path.exists(p) else "(no manifest)"


def result(cfg, live=False):
    p = os.path.join(RUNS if live else RESULTS, cfg + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def root_cause(cfg):
    import csv
    if os.path.exists(ROOT_CAUSES):
        for r in csv.DictReader(open(ROOT_CAUSES, encoding="utf-8")):
            if r["config"] == cfg:
                return r
    return None


def summary(r):
    """Flat list of (dimension, check, value, ok) for display; ok is True/False/None."""
    if not r:
        return []
    g = lambda d, *ks: _dig(d, ks)
    rows = [("D1 Correctness", "YAML parses", "yes" if r.get("d1_parse_ok") else "no", r.get("d1_parse_ok"))]
    if not r.get("d1_parse_ok"):
        return rows + [("D1 Correctness", "Error", str(r.get("d1_parse_error"))[:120], False)]
    kc, dr = r.get("d1_kubeconform") or {}, r.get("d1_server_dry_run") or {}
    rows += [("D1 Correctness", "Schema valid", str(kc.get("valid")), kc.get("valid")),
             ("D1 Correctness", "API server accepts objects",
              f"{dr.get('objects_accepted')}/{dr.get('objects_total')}" if dr else "skipped (cluster not running)",
              dr.get("server_ok"))]
    ks = g(r, "d2", "kubescape", "compliance")
    trivy = g(r, "d2", "trivy", "by_severity") or {}
    rows += [("D2 Security", "Kubescape compliance (%)", _num(ks), None),
             ("D2 Security", "Trivy high + critical findings", str((trivy.get("high") or 0) + (trivy.get("critical") or 0)), None),
             ("D2 Security", "Pod Security Standard level", str(g(r, "d2", "pss", "level")), None),
             ("D2 Security", "Literal credentials found", str(g(r, "d2", "secrets", "count")), (g(r, "d2", "secrets", "count") or 0) == 0)]
    rows += [("D3 Reliability", "Polaris score", _num(g(r, "d3", "polaris", "score")), None),
             ("D3 Reliability", "Reliability checklist (%)", _num(g(r, "d3", "checklist", "pct")), None),
             ("D3 Reliability", "KubeLinter smells", str(g(r, "d3", "kube_linter", "zhang_total")), None)]
    d4 = r.get("d4") or {}
    rows.append(("D4 Requirements", "Documented requirements met", f"{d4.get('requirements_met')}/{d4.get('requirements_total')}",
                 d4.get("requirements_met") == d4.get("requirements_total")))
    d5, d6 = r.get("d5") or {}, r.get("d6") or {}
    if d5.get("ran"):
        rows += [("D5 Deployment", "Fully Ready", f"{d5.get('ready_ok')} ({d5.get('ready_replicas')}/{d5.get('expected_replicas')})", d5.get("ready_ok")),
                 ("D5 Deployment", "Time to Ready (s)", _num(d5.get("time_to_ready_s")), None)]
        for c in d5.get("smoke") or []:
            rows.append(("D5 Smoke test", c.get("name"), str(c.get("detail"))[:70], c.get("passed")))
        if d6.get("ran"):
            for f in ("pod_delete", "container_crash"):
                for i, x in enumerate(d6.get(f) or [], 1):
                    rows.append(("D6 Resilience", f"{f.replace('_', ' ')} #{i}",
                                 f"recovered in {_num(x.get('recovery_time_s'))} s, availability {_num(x.get('availability_pct'))}%",
                                 x.get("recovery_ok")))
        else:
            rows.append(("D6 Resilience", "Fault injection", f"not run: {d6.get('reason')}", None))
    else:
        rows.append(("D5 Deployment", "Deployment", "not run (static checks only)", None))
    return rows


def merged(rec, live):
    """[(dimension, check, recorded value, recorded ok, live value, live ok)], recorded order first."""
    a, b = summary(rec), summary(live)
    lv = {(d, c): (v, ok) for d, c, v, ok in b}
    rows = [(d, c, v, ok) + lv.pop((d, c), ("", None)) for d, c, v, ok in a]
    return rows + [(d, c, "", None, v, ok) for d, c, v, ok in b if (d, c) in lv]


def label(cfg):
    p = cfg.split("__")
    names = {"claude": "Claude", "deepseek": "DeepSeek", "gemini": "Gemini", "gpt": "GPT", "qwen": "Qwen"}
    return "Human (shipped manifest)" if p[0] == "human" else f"{names.get(p[0], p[0])}, {p[2]} prompt, sample {p[3][1:]}"


def same(recorded, live):
    """True/False when both values exist and the live one was actually measured; None otherwise."""
    if not recorded or not live or live.startswith(("skipped", "not checked", "not run")):
        return None
    return recorded == live


def verdict(r):
    d5 = (r or {}).get("d5") or {}
    if not d5.get("ran"):
        return "static checks done (deployment not run)"
    return "WORKS (Ready + smoke test passed)" if d5.get("ready_ok") and d5.get("smoke_ok") else "DOES NOT WORK"


def _dig(d, ks):
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def _num(x):
    return "-" if x is None else (f"{x:.1f}" if isinstance(x, float) else str(x))


def cluster_up():
    kubectl = os.path.join(ROOT, "tools", "bin", "kubectl.exe")
    try:
        return subprocess.run([kubectl, "--context", "kind-k8sgen", "get", "--raw", "/readyz"], capture_output=True,
                              text=True, timeout=8).stdout.strip() == "ok"
    except Exception:
        return False


# ---------------------------------------------------------------- live runs
def start_job(args):
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"log": [], "done": False}

    def work():
        t0 = time.time()
        p = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        for line in p.stdout:
            JOBS[jid]["log"].append(f"[{time.time() - t0:5.0f}s] {line.rstrip()}")
        p.wait()
        JOBS[jid]["log"].append(f"finished with exit code {p.returncode} after {time.time() - t0:.0f} s")
        JOBS[jid]["rc"] = p.returncode
        JOBS[jid]["done"] = True

    threading.Thread(target=work, daemon=True).start()
    return jid


# ---------------------------------------------------------------- pages
CSS = """
:root{--ink:#1d2433;--muted:#667085;--line:#e4e7ec;--ok:#067647;--bad:#b42318;--bg:#f8f9fb;--acc:#2f5bd3}
body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;color:var(--ink);background:var(--bg)}
header{background:#1d2433;color:#fff;padding:14px 24px}header h1{margin:0;font-size:19px}header p{margin:4px 0 0;color:#c9d1e0;font-size:13px}
main{padding:18px 24px;max-width:1400px;margin:auto}
.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px}
select,button{font-size:14px;padding:7px 10px;border-radius:6px;border:1px solid #cfd4dc;background:#fff}
button{background:var(--acc);color:#fff;border:0;cursor:pointer}button.sec{background:#fff;color:var(--ink);border:1px solid #cfd4dc}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
.card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px;min-width:0}
.card h2{font-size:15px;margin:0 0 8px}pre{background:#0f1729;color:#d6e2ff;font-size:11.5px;padding:10px;border-radius:6px;max-height:330px;overflow:auto;white-space:pre}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
.verdict{font-weight:700;padding:6px 10px;border-radius:6px;display:inline-block;margin:4px 0 8px}
.v-ok{background:#ecfdf3;color:var(--ok)}.v-bad{background:#fef3f2;color:var(--bad)}.v-na{background:#f2f4f7;color:var(--muted)}
#log{max-height:260px}.pill{font-size:12px;padding:3px 8px;border-radius:99px}.muted{color:var(--muted);font-size:13px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
@media print{.noprint{display:none}body{background:#fff}.card{break-inside:avoid}}
"""

INDEX = """<!doctype html><html><head><meta charset="utf-8"><title>K8sGenBench demo</title><style>%s</style></head><body>
<header><h1>K8sGenBench: human vs LLM-generated Kubernetes manifests</h1>
<p>Pick a project and two configurations. Recorded results load instantly; "Run live" re-runs the pipeline now.</p></header>
<main>
<div class="bar">
 <label>Project <select id="proj"></select></label>
 <label>Left <select id="a"></select></label>
 <label>Right <select id="b"></select></label>
 <button onclick="report()">Report</button>
 <span style="flex:1"></span>
 <span id="cl" class="pill"></span>
 <label class="muted"><input type="checkbox" id="rt"> include deployment (D5/D6, needs cluster, 3-8 min)</label>
 <button class="sec" onclick="live('a')">Run live: left</button>
 <button class="sec" onclick="live('b')">Run live: right</button>
</div>
<p class="muted" style="margin:8px 2px">Colours: <span class="ok">green = check passed</span>, <span class="bad">red = check failed</span>, black = a score (no pass/fail threshold). In the Live column, <span class="ok">&#10003;</span> = same value as the recorded study result.</p>
<div class="card" id="logcard" style="display:none;margin-top:6px"><h2>Live run <span id="logname" class="muted"></span></h2><div id="status" class="verdict v-na">starting...</div><pre id="log"></pre></div>
<div class="grid"><div class="card" id="A"></div><div class="card" id="B"></div></div>
</main>
<script>
let CFG={};
const $=id=>document.getElementById(id);
let PROJ={};
const NAMES={claude:'Claude',deepseek:'DeepSeek',gemini:'Gemini',gpt:'GPT',qwen:'Qwen'};
function label(n){const p=n.split('__');return p[0]=='human'?'Human (shipped manifest)':NAMES[p[0]]+', '+p[2]+' prompt, sample '+p[3].slice(1)}
async function init(){CFG=await (await fetch('/api/configs')).json();PROJ=await (await fetch('/api/projects')).json();
 $('proj').innerHTML=Object.keys(CFG).map(p=>`<option value="${p}">${PROJ[p]||p}</option>`).join('');$('proj').onchange=fill;fill();cluster()}
function fill(){const l=CFG[$('proj').value];const o=l.map(n=>`<option value="${n}">${label(n)}</option>`).join('');
 $('a').innerHTML=o;$('b').innerHTML=o;$('a').value=l[0];$('b').value=l.find(n=>n.startsWith('claude'))||l[1];
 $('a').onchange=()=>show('a');$('b').onchange=()=>show('b');show('a');show('b')}
async function show(s){const n=$(s).value;const d=await (await fetch('/api/config?name='+n)).json();
 const badge=(v,t)=>`<span class="verdict ${v.startsWith('WORKS')?'v-ok':v.startsWith('DOES')?'v-bad':'v-na'}">${t}: ${v}</span> `;
 const c=ok=>ok===true?'ok':ok===false?'bad':'';
 $(s.toUpperCase()).innerHTML=`<h2>${label(n)}</h2>${badge(d.verdict,'Recorded')}${d.live?badge(d.live_verdict,'Live'):''}
 ${d.cause?`<p class="muted"><b>Root cause (study):</b> ${d.cause}</p>`:''}
 <table><tr><th>Dimension</th><th>Check</th><th>Recorded</th>${d.live?'<th>Live</th>':''}</tr>${d.rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td class="${c(r[3])}">${r[2]}</td>${d.live?`<td class="${c(r[5])}">${r[4]}${r[6]===true?' <span class="ok">&#10003;</span>':r[6]===false?' <span class="bad">(differs)</span>':''}</td>`:''}</tr>`).join('')}</table>
 <h2 style="margin-top:12px">Manifest</h2><pre>${d.manifest}</pre>`;return d}
async function cluster(){const u=(await (await fetch('/api/cluster')).json()).up;
 $('cl').textContent=u?'cluster: running':'cluster: stopped (static checks only)';$('cl').style.background=u?'#ecfdf3':'#f2f4f7'}
function status(t,cls){$('status').textContent=t;$('status').className='verdict '+cls}
async function live(s){const n=$(s).value;$('logcard').style.display='';$('logname').textContent=label(n);$('log').textContent='';const t0=Date.now();status('Running... 0 s','v-na');
 const j=await (await fetch('/api/run?name='+n+'&runtime='+($('rt').checked?1:0),{method:'POST'})).json();
 const t=setInterval(async()=>{const st=await (await fetch('/api/log?id='+j.id)).json();$('log').textContent=st.log.join('\\n');
  $('log').scrollTop=1e9;const sec=Math.round((Date.now()-t0)/1000);
  if(!st.done){status('Running... '+sec+' s','v-na');return}
  clearInterval(t);const d=await show(s);
  if(st.rc!==0){status('Run FAILED (exit code '+st.rc+'): see the log below','v-bad');return}
  const m=d.match;status('Completed in '+sec+' s. '+m[0]+' of '+m[1]+' live values match the recorded study result'+(d.live_verdict.startsWith('static')?' (deployment not run).':'. Live verdict: '+d.live_verdict),m[0]==m[1]?'v-ok':'v-bad')},1500)}
function report(){window.open('/report?a='+$('a').value+'&b='+$('b').value)}
init();
</script></body></html>""" % CSS


def report_page(a, b):
    def col(cfg):
        live, rec = result(cfg, True), result(cfg)
        rc = root_cause(cfg)
        cl = lambda ok: "ok" if ok is True else "bad" if ok is False else ""
        badge = lambda v, t: (f"<span class='verdict {'v-ok' if v.startswith('WORKS') else 'v-bad' if v.startswith('DOES') else 'v-na'}'>"
                              f"{t}: {v}</span> ")
        rows = "".join(f"<tr><td>{html.escape(d)}</td><td>{html.escape(str(c))}</td><td class='{cl(ok)}'>{html.escape(str(v))}</td>"
                       + (f"<td class='{cl(lok)}'>{html.escape(str(lv))}</td>" if live else "") + "</tr>"
                       for d, c, v, ok, lv, lok in merged(rec, live))
        cause = f"<p><b>Root cause (study):</b> {html.escape(rc['mechanism'])} <span class='muted'>({html.escape(rc['evidence'])})</span></p>" if rc else ""
        return (f"<div class='card'><h2>{html.escape(label(cfg))}</h2>{badge(verdict(rec), 'Recorded')}"
                f"{badge(verdict(live), 'Live') if live else ''}{cause}"
                f"<table><tr><th>Dimension</th><th>Check</th><th>Recorded</th>{'<th>Live</th>' if live else ''}</tr>{rows}</table></div>")
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>K8sGenBench report</title><style>{CSS}</style></head><body>"
            f"<header><h1>K8sGenBench comparison report</h1><p>Project {html.escape(PROJECTS.get(a.split('__')[1], a.split('__')[1]))} &middot; generated "
            f"{time.strftime('%Y-%m-%d %H:%M')} &middot; D1 correctness, D2 security, D3 reliability, D4 requirements, "
            f"D5 deployment and smoke test, D6 recovery from injected faults</p></header><main>"
            f"<p class='noprint'><button onclick='print()'>Save as PDF / print</button></p>"
            f"<div class='grid'>{col(a)}{col(b)}</div></main></body></html>")


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
        name = os.path.basename(q.get("name", ""))  # basename: never a path outside the results folders
        if u.path == "/":
            return self._send(INDEX, "text/html")
        if u.path == "/api/configs":
            return self._send(configs())
        if u.path == "/api/projects":
            return self._send(PROJECTS)
        if u.path == "/api/cluster":
            return self._send({"up": cluster_up()})
        if u.path == "/api/config":
            live, rec = result(name, True), result(name)
            rc = root_cause(name)
            rows = [list(r) + [same(r[2], r[4])] for r in merged(rec, live)] if live else [list(r) + [None] for r in merged(rec, live)]
            compared = [r[6] for r in rows if r[6] is not None]
            return self._send({"rows": rows, "verdict": verdict(rec), "match": [sum(compared), len(compared)],
                               "live_verdict": verdict(live) if live else "", "live": bool(live),
                               "manifest": html.escape(manifest_text(name)),
                               "cause": html.escape(rc["mechanism"]) if rc else ""})
        if u.path == "/api/log":
            j = JOBS.get(q.get("id"), {"log": ["unknown job"], "done": True})
            return self._send({"log": j["log"], "done": j["done"], "rc": j.get("rc")})
        if u.path == "/report":
            return self._send(report_page(os.path.basename(q["a"]), os.path.basename(q["b"])), "text/html")
        self._send({"error": "not found"}, code=404)

    def do_POST(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/api/run":
            name = os.path.basename(q["name"])
            os.makedirs(RUNS, exist_ok=True)
            jid = start_job([sys.executable, "-u", "-c", LIVE_RUNNER, ROOT, RUNS, name, q.get("runtime", "0"),
                             "1" if cluster_up() else "0"])
            return self._send({"id": jid})
        self._send({"error": "not found"}, code=404)


if __name__ == "__main__":
    print(f"K8sGenBench demo on http://localhost:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
