"""
Guided generation with a verify-and-repair loop (phase 2, RQ6).

Round 0 sends the guided system prompt (prompts/guided_system.md) with the same user prompt as the
production variant (docs_bundle + prompts/guided.md). Each round's manifest is evaluated by the
unchanged pipeline (evaluation/eval_runner.py --runtime). If it fails the gate, the model gets the
cluster's own diagnostics as a follow-up turn and returns a corrected configuration, up to MAX_REPAIRS times.

The gate and the feedback use only signals a deployment tool has without knowing the application:
YAML parse, server-side dry-run, Pod Security baseline, Service wiring, apply errors, workload readiness,
container exit codes, last log lines and warning events. Smoke-test and D6 results are never shown to the
model; they stay the independent outcome measure.

Outputs: generation/outputs/<model>/<project>/guided_r<n>/s<k>/{request.json,response_raw.json,
manifest.yaml,extraction.json,feedback.txt}; evaluation/results/<model>__<project>__guided_r<n>__s<k>.json;
generation/outputs/<model>/<project>/guided_loop_s<k>.json (per-round summary).

Usage:
  python generation/repair_loop.py run <gemini|qwen> <project> <k>          full loop through the API
  python generation/repair_loop.py prompt claude <project> <k> <round>      write the request for a subagent
  python generation/repair_loop.py ingest claude <project> <k> <round> <reply.md>
                                                                            save a subagent reply, evaluate it,
                                                                            write feedback for the next round
  python generation/repair_loop.py feedback <model> <project> <k> <round>   (re)compute feedback from results
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

import generate as g

HERE = g.HERE
ROOT = g.ROOT
RESULTS = ROOT / "evaluation" / "results"
MAX_REPAIRS = 3
SYSTEM_PROMPT = (HERE / "prompts" / "guided_system.md").read_text(encoding="utf-8").strip()
PROMPT_VERSION = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12]
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
FEEDBACK_HEAD = ("The manifests were applied to a Kubernetes cluster (v1.37) and checked automatically. "
                 "They did not work:\n")
FEEDBACK_TAIL = ("\nFix these problems and return the complete corrected set of manifests in a single YAML code "
                 "block. Keep the settings that already work.")


def round_dir(model, project, k, rnd):
    return HERE / "outputs" / model / project / f"guided_r{rnd}" / f"s{k}"


def result_path(model, project, k, rnd):
    return RESULTS / f"{model}__{project}__guided_r{rnd}__s{k}.json"


# ---------------------------------------------------------------- conversation

def conversation(model, project, k, rnd):
    """[(role, text)] sent to produce round `rnd`: the user prompt, then for every earlier round the
    model's reply and the feedback on it."""
    turns = [("user", g.build_user_prompt(project, "guided"))]
    for r in range(rnd):
        d = round_dir(model, project, k, r)
        turns.append(("assistant", reply_text(d)))
        turns.append(("user", (d / "feedback.txt").read_text(encoding="utf-8")))
    return turns


def reply_text(d):
    raw = json.loads((d / "response_raw.json").read_text(encoding="utf-8"))
    if "reply_text" in raw:
        return raw["reply_text"]
    data = raw["raw"]
    if data.get("candidates"):
        parts = data["candidates"][0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return data["choices"][0]["message"]["content"]


def call_gemini(env, turns):
    model_id = g.CONFIG["models"]["gemini"]["model_id"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "model" if r == "assistant" else "user", "parts": [{"text": t}]} for r, t in turns],
        "generationConfig": {"temperature": g.CONFIG["temperature"], "maxOutputTokens": g.CONFIG["max_tokens"]},
    }
    t0 = time.time()
    r = g.gemini_post(env, url, payload, timeout=600)  # client-side timeout only; long thinking replies took over 300 s
    latency = time.time() - t0
    r.raise_for_status()
    data = r.json()
    parts = data["candidates"][0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    u = data.get("usageMetadata", {})
    return text, data, latency, u.get("promptTokenCount"), u.get("candidatesTokenCount")


def call_groq(env, turns, model_id):
    payload = {
        "model": model_id,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + [{"role": r, "content": t} for r, t in turns],
        "temperature": g.CONFIG["temperature"],
        "max_tokens": g.CONFIG["max_tokens"],
    }
    t0 = time.time()
    r = g.post_with_retry("https://api.groq.com/openai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {env['GROQ_API_KEY']}"}, json=payload, timeout=300)
    latency = time.time() - t0
    r.raise_for_status()
    data = r.json()
    u = data.get("usage", {})
    return data["choices"][0]["message"]["content"], data, latency, u.get("prompt_tokens"), u.get("completion_tokens")


def save_round(model, project, k, rnd, text, raw, latency, tin, tout, provider, model_id):
    d = round_dir(model, project, k, rnd)
    d.mkdir(parents=True, exist_ok=True)
    manifest, status = g.extract_yaml(text)
    (d / "request.json").write_text(json.dumps({
        "model_id": model_id, "provider": provider, "temperature": g.CONFIG["temperature"],
        "max_tokens": g.CONFIG["max_tokens"], "system_prompt_version": PROMPT_VERSION, "round": rnd,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2))
    (d / "response_raw.json").write_text(json.dumps({"raw": raw, "latency_s": latency, "tokens_in": tin,
                                                     "tokens_out": tout}, indent=2))
    (d / "manifest.yaml").write_text(manifest, encoding="utf-8")
    (d / "extraction.json").write_text(json.dumps({"status": status}, indent=2))


LOCK = ROOT / "evaluation" / "cluster.lock"


def evaluate(model, project, k, rnd):
    # one deployment at a time on the shared cluster: timing and resource pressure must not depend on what
    # else happens to be running
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{model} {project} s{k} r{rnd} pid {os.getpid()}".encode())
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(10)
    try:
        return _evaluate(model, project, k, rnd)
    finally:
        LOCK.unlink(missing_ok=True)


def _evaluate(model, project, k, rnd):
    r = subprocess.run([sys.executable, str(ROOT / "evaluation" / "eval_runner.py"), model, project,
                        f"guided_r{rnd}", str(k), "--runtime"], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", timeout=3600)
    print(r.stdout.strip() or r.stderr.strip()[-2000:])
    return json.loads(result_path(model, project, k, rnd).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- gate and feedback

def wiring_problems(docs):
    """Services that select no pod template, or name a targetPort no selected container declares."""
    pods = []
    for d in docs:
        spec = (d.get("spec") or {})
        tpl = (spec.get("jobTemplate") or {}).get("spec", {}).get("template") if d.get("kind") == "CronJob" \
            else spec.get("template")
        if d.get("kind") in ("Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job", "CronJob") and tpl:
            pods.append(((d.get("metadata") or {}).get("namespace"), (tpl.get("metadata") or {}).get("labels") or {},
                         (tpl.get("spec") or {}).get("containers") or []))
        elif d.get("kind") == "Pod":
            pods.append(((d.get("metadata") or {}).get("namespace"), (d.get("metadata") or {}).get("labels") or {},
                         spec.get("containers") or []))
    out = []
    for s in docs:
        if s.get("kind") != "Service":
            continue
        sel = (s.get("spec") or {}).get("selector")
        if not sel:
            continue
        ns = (s.get("metadata") or {}).get("namespace")
        name = (s.get("metadata") or {}).get("name")
        matched = [c for pns, labels, cs in pods if pns == ns and all(labels.get(a) == b for a, b in sel.items())
                   for c in cs]
        if not matched:
            out.append(f"Service {name} selects {sel}, but no pod template in its namespace has these labels.")
            continue
        names = {p.get("name") for c in matched for p in c.get("ports") or [] if p.get("name")}
        numbers = {p.get("containerPort") for c in matched for p in c.get("ports") or []}
        for p in (s.get("spec") or {}).get("ports") or []:
            tp = p.get("targetPort", p.get("port"))
            if isinstance(tp, str) and not tp.isdigit() and tp not in names:
                out.append(f"Service {name} targetPort '{tp}' is not the name of any port of the selected containers.")
            elif numbers and str(tp).isdigit() and int(tp) not in numbers:
                out.append(f"Service {name} targetPort {tp} is not a containerPort of the selected containers "
                           f"(they declare {sorted(n for n in numbers if n)}).")
    return out


ERROR_LINE = re.compile(r"error|fatal|panic|denied|not permitted|refused|not found|invalid|cannot|failed|exception",
                        re.I)
STACK_LINE = re.compile(r"^\s+at |^\s*File \"|^\s*goroutine ")


def log_excerpt(log):
    """The lines that name the cause (error-like lines, stack frames dropped) plus the last two lines."""
    lines = [l.rstrip() for l in ANSI.sub("", log).splitlines() if l.strip()]
    hits = [l for l in lines if ERROR_LINE.search(l) and not STACK_LINE.match(l)]
    picked = list(dict.fromkeys(hits[-8:] + lines[-2:]))
    return "\n".join(l[:300] for l in picked)[-1500:]


def problems(record, docs):
    """Generic problems found in one round; an empty list means the configuration passes the gate."""
    p = []
    if not record["d1_parse_ok"]:
        msg = (record.get("d1_parse_error") or "")[:400]
        fr = record.get("gen_finish_reason")
        trunc = " The reply was cut off before the end." if fr in ("MAX_TOKENS", "length") else ""
        return [f"The reply could not be parsed as Kubernetes YAML: {msg}.{trunc}"]
    dr = record["d1_server_dry_run"]
    for o in dr.get("per_object") or []:
        if not o["accepted"]:
            p.append(f"The API server rejected {o['kind']} {o['name']}: {o['error'].strip()[:300]}")
    pss = record["d2"].get("pss") or {}
    if pss.get("level") == "none":
        for v in (pss.get("violations") or {}).get("baseline") or []:
            detail = v["detail"]
            detail = detail[detail.find("would violate"):] if "would violate" in detail else detail
            p.append(f"{v['kind']} {v['name']} violates Pod Security baseline: {detail.strip()[:300]}")
    p += wiring_problems(docs)
    d5 = record.get("d5") or {}
    # only what the configuration itself created: a config that deploys into kube-system shares it with the
    # cluster's own pods, whose state and logs are not about this configuration
    names = {(d.get("metadata") or {}).get("name") for d in docs}
    owners = {(d.get("metadata") or {}).get("name") for d in docs
              if d.get("kind") in ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "Pod")}

    def own(obj):
        return obj in names or any(obj.startswith(f"{w}-") for w in owners if w)

    if d5.get("ran"):
        rejected = {(o["kind"], o["name"]) for o in dr.get("per_object") or [] if not o["accepted"]}
        for e in d5.get("apply_errors") or []:
            if (e["kind"], e["name"]) not in rejected:
                p.append(f"kubectl apply failed for {e['kind']} {e['name']}: {e['error'].strip()[:300]}")
        mine = [w for w in d5.get("workloads") or [] if own(w["name"])]
        others_only = mine and all(w["ready"] >= w["want"] for w in mine) and any(
            w["ready"] < w["want"] for w in d5.get("workloads") or [] if not own(w["name"]))
        if not d5.get("ready_ok") and not others_only:
            bad = [f"{w['kind']} {w['name']} {w['ready']}/{w['want']} Ready" for w in mine if w["ready"] < w["want"]]
            p.append(f"Not all workloads became Ready within 5 minutes ({d5.get('failure_reason')}): "
                     + (", ".join(bad) if bad else "no workload objects were created" if not mine
                        else "the workloads did not stay Ready") + ".")
            diag = d5.get("diagnostics") or {}
            seen = set()
            for pod in [x for x in diag.get("pods") or [] if own(x["pod"])]:
                # replicas of one workload fail the same way; report each container once
                key = (pod["container"], pod["last_exit"], pod["last_reason"])
                if key in seen or len(seen) >= 8:
                    continue
                seen.add(key)
                line = (f"Pod {pod['pod']} container {pod['container']}: {pod['restarts']} restarts, "
                        f"last exit code {pod['last_exit']} ({pod['last_reason']}).")
                if pod.get("last_log"):
                    log = log_excerpt(pod["last_log"])
                    line += f" Last log lines:\n    " + log.replace("\n", "\n    ")
                p.append(line)
            events = [(ev.split("|", 1), n) for ev, n in (diag.get("warning_events") or {}).items()]
            for (obj, msg), n in [e for e in events if own(e[0][0])][:10]:
                p.append(f"Warning event on {obj} ({n}x): {msg}")
        # gate v2: a Ready pod need not serve the port its Service sends traffic to
        for x in d5.get("service_listen") or []:
            if x["ok"] is False:
                p.append(f"Service {x['service']} port {x['port']} sends traffic to port {x['target_port']} of pod "
                         f"{x['pod']}, but that pod listens only on TCP port(s) {', '.join(map(str, x['listening']))}.")
    return p


def write_feedback(model, project, k, rnd):
    record = json.loads(result_path(model, project, k, rnd).read_text(encoding="utf-8"))
    d = round_dir(model, project, k, rnd)
    try:
        docs = [x for x in yaml.safe_load_all((d / "manifest.yaml").read_text(encoding="utf-8")) if isinstance(x, dict)]
    except yaml.YAMLError:
        docs = []
    p = problems(record, docs)
    if p:
        (d / "feedback.txt").write_text(FEEDBACK_HEAD + "\n".join(f"- {x}" for x in p) + "\n" + FEEDBACK_TAIL,
                                        encoding="utf-8")
    elif (d / "feedback.txt").exists():
        (d / "feedback.txt").unlink()
    update_summary(model, project, k, rnd, record, p)
    return p


def update_summary(model, project, k, rnd, record, p):
    path = HERE / "outputs" / model / project / f"guided_loop_s{k}.json"
    s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"system_prompt_version": PROMPT_VERSION,
                                                                            "rounds": []}
    s["rounds"] = [x for x in s["rounds"] if x["round"] != rnd]
    d5 = record.get("d5") or {}
    s["rounds"].append({"round": rnd, "gate_passed": not p, "n_problems": len(p),
                        "ready_ok": d5.get("ready_ok"), "smoke_ok": d5.get("smoke_ok")})
    s["rounds"].sort(key=lambda x: x["round"])
    s["final_round"] = max(x["round"] for x in s["rounds"])
    s["stopped"] = "gate_passed" if not p else ("max_repairs" if rnd >= MAX_REPAIRS else "open")
    path.write_text(json.dumps(s, indent=2))


# ---------------------------------------------------------------- commands

def run(model, project, k):
    env = g.load_env()
    cfg = g.CONFIG["models"][model]
    for rnd in range(MAX_REPAIRS + 1):
        if not result_path(model, project, k, rnd).exists():
            # a reply saved before a crash in its evaluation is evaluated, not generated again
            if not (round_dir(model, project, k, rnd) / "extraction.json").exists():
                turns = conversation(model, project, k, rnd)
                if cfg["provider"] == "gemini":
                    out = call_gemini(env, turns)
                elif cfg["provider"] == "groq":
                    out = call_groq(env, turns, cfg["model_id"])
                else:
                    sys.exit(f"{model}: use the prompt/ingest commands")
                save_round(model, project, k, rnd, *out, cfg["provider"], cfg["model_id"])
            evaluate(model, project, k, rnd)
        p = write_feedback(model, project, k, rnd)
        print(f"{model} {project} s{k} r{rnd}: {'GATE PASSED' if not p else f'{len(p)} problem(s)'}")
        if not p:
            break


def prompt(model, project, k, rnd):
    turns = conversation(model, project, k, rnd)
    d = round_dir(model, project, k, rnd)
    d.mkdir(parents=True, exist_ok=True)
    body = [f"=== SYSTEM ===\n{SYSTEM_PROMPT}"] + [f"=== {r.upper()} ===\n{t}" for r, t in turns]
    (d / "subagent_prompt.txt").write_text("\n\n".join(body), encoding="utf-8")
    print(d / "subagent_prompt.txt")


def ingest(model, project, k, rnd, reply_file):
    text = Path(reply_file).read_text(encoding="utf-8")
    cfg = g.CONFIG["models"][model]
    save_round(model, project, k, rnd, text, {"reply_text": text}, None, None, None, cfg["provider"], cfg["model_id"])
    raw_path = round_dir(model, project, k, rnd) / "response_raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw["reply_text"] = text
    raw_path.write_text(json.dumps(raw, indent=2))
    evaluate(model, project, k, rnd)
    p = write_feedback(model, project, k, rnd)
    print(f"{model} {project} s{k} r{rnd}: {'GATE PASSED' if not p else f'{len(p)} problem(s)'}")


if __name__ == "__main__":
    cmd, a = sys.argv[1], sys.argv[2:]
    if cmd == "run":
        run(a[0], a[1], a[2])
    elif cmd == "prompt":
        prompt(a[0], a[1], a[2], int(a[3]))
    elif cmd == "ingest":
        ingest(a[0], a[1], a[2], int(a[3]), a[4])
    elif cmd == "feedback":
        print("\n".join(write_feedback(a[0], a[1], a[2], int(a[3]))) or "GATE PASSED")
