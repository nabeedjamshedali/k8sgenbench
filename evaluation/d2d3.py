"""K8sGenBench D2 (security) and D3 (static reliability) instruments.

All scanners run offline against pinned rule sets under tools/scanner-artifacts/ so every config
is judged by identical rules regardless of when it is scanned. Raw tool output is saved next to
each result JSON; only summary metrics go into the result record.
"""
import collections
import json
import os
import re
import subprocess

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "tools", "bin")
ART = os.path.join(ROOT, "tools", "scanner-artifacts")

ZHANG_SMELLS = ["dangling-service", "no-anti-affinity", "no-read-only-root-fs", "run-as-non-root",
                "unset-cpu-requirements", "unset-memory-requirements"]
POD_KINDS = {"Pod", "Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job", "CronJob"}


def _run(args, timeout=300):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore",
                          timeout=timeout)


def _save(raw_dir, name, text):
    with open(os.path.join(raw_dir, name), "w", encoding="utf-8") as f:
        f.write(text)


def loc(text):
    return sum(1 for ln in text.splitlines()
               if ln.strip() and not ln.strip().startswith("#") and ln.strip() != "---")


# ---------------------------------------------------------------- D2 security

def kubescape(path, raw_dir):
    out = os.path.join(raw_dir, "kubescape.json")
    r = _run([os.path.join(BIN, "kubescape.exe"), "scan", "framework", "nsa,mitre", path,
              "--use-artifacts-from", os.path.join(ART, "kubescape"), "--keep-local",
              "--format", "json", "--output", out])
    # an empty file means kubescape exited without a report (e.g. "no resources found to scan")
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        return {"ran": False, "stderr": (r.stdout + r.stderr)[-1500:]}
    data = json.load(open(out, encoding="utf-8"))
    sd = data["summaryDetails"]
    sev = sd.get("controlsSeverityCounters", {})
    failed = []
    for res in data.get("results", []):
        for ctl in res.get("controls", []):
            if ctl.get("status", {}).get("status") == "failed":
                failed.append({"resource": res.get("resourceID"), "control": ctl.get("controlID"),
                               "name": ctl.get("name")})
    return {
        "ran": True,
        "compliance": sd.get("complianceScore"),
        "frameworks": {fw.get("name"): fw.get("complianceScore") for fw in sd.get("frameworks", [])},
        "failed_controls_by_severity": {
            "critical": sev.get("criticalSeverity", 0), "high": sev.get("highSeverity", 0),
            "medium": sev.get("mediumSeverity", 0), "low": sev.get("lowSeverity", 0)},
        "failed": failed,
    }


def trivy(path, raw_dir):
    r = _run([os.path.join(BIN, "trivy.exe"), "config", "--cache-dir", os.path.join(ART, "trivy-cache"),
              "--skip-check-update", "--format", "json", "-q", path])
    _save(raw_dir, "trivy.json", r.stdout)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ran": False, "stderr": r.stderr[-1500:]}
    mis = [m for res in data.get("Results") or [] for m in res.get("Misconfigurations") or []
           if m.get("Status") == "FAIL"]
    counts = collections.Counter(m.get("Severity", "UNKNOWN").lower() for m in mis)
    return {
        "ran": True,
        "by_severity": {s: counts.get(s, 0) for s in ("critical", "high", "medium", "low")},
        "failed": [{"id": m.get("ID"), "title": m.get("Title"), "severity": m.get("Severity"),
                    "message": m.get("Message")} for m in mis],
    }


SECRET_NAME = re.compile(r"(pass(word|wd)?|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)", re.I)
SECRET_VALUE = [
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("url-credentials", re.compile(r"[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s:/@]+@", re.I)),
]


def _containers(spec):
    return (spec or {}).get("containers", []) + (spec or {}).get("initContainers", [])


def pod_spec(doc):
    kind = doc.get("kind")
    spec = doc.get("spec") or {}
    if kind == "Pod":
        return spec
    if kind == "CronJob":
        return (((spec.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}).get("spec")
    if kind in POD_KINDS:
        return (spec.get("template") or {}).get("spec")
    return None


def secrets(docs, text):
    """Hardcoded-secret check: (a) literal values in Secret objects, (b) literal env values whose
    variable name looks secret-bearing, (c) known credential token patterns anywhere in the text.
    Empty strings and obvious placeholders are not counted."""
    findings = []
    nonsensitive = []
    placeholder = re.compile(r"^(|changeme|change-me|replace[-_ ]?me|<.*>|\$\{.*\}|xxx+|todo)$", re.I)
    for d in docs:
        if not isinstance(d, dict):
            continue
        name = (d.get("metadata") or {}).get("name")
        if d.get("kind") == "Secret":
            # A literal only counts if its key names a credential; non-credential values stored in a
            # Secret (e.g. a host:port address) are recorded but not counted.
            for field in ("data", "stringData"):
                for k, v in (d.get(field) or {}).items():
                    if v is None or placeholder.match(str(v).strip()):
                        continue
                    (findings if SECRET_NAME.search(k) else nonsensitive).append(
                        {"type": "secret-object-literal", "object": name, "key": k})
        for ct in _containers(pod_spec(d)):
            for e in ct.get("env") or []:
                if "value" in e and SECRET_NAME.search(e.get("name", "")) \
                        and not placeholder.match(str(e.get("value")).strip()):
                    findings.append({"type": "env-literal", "object": name, "container": ct.get("name"),
                                     "key": e.get("name")})
    for label, rx in SECRET_VALUE:
        for _ in rx.finditer(text):
            findings.append({"type": label})
    return {"ran": True, "count": len(findings), "findings": findings, "nonsensitive_secret_literals": nonsensitive}


# ---------------------------------------------------------------- D3 static reliability

def kube_score(path, raw_dir):
    r = _run([os.path.join(BIN, "kube-score.exe"), "score", "-o", "json", path])
    _save(raw_dir, "kube-score.json", r.stdout)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ran": False, "stderr": r.stderr[-1500:]}
    # grades: 1 = critical, 5 = warning, 7 = almost ok, 10 = ok; skipped checks are not counted
    crit = collections.Counter()
    warn = collections.Counter()
    for obj in data or []:
        for c in obj.get("checks", []):
            if c.get("skipped"):
                continue
            if c.get("grade") == 1:
                crit[c["check"]["id"]] += 1
            elif c.get("grade") == 5:
                warn[c["check"]["id"]] += 1
    return {"ran": True, "critical": sum(crit.values()), "warning": sum(warn.values()),
            "critical_by_check": dict(crit), "warning_by_check": dict(warn)}


def polaris(path, raw_dir):
    r = _run([os.path.join(BIN, "polaris.exe"), "audit", "--audit-path", path, "--format", "json"])
    _save(raw_dir, "polaris.json", r.stdout)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ran": False, "stderr": r.stderr[-1500:]}
    failed = collections.Counter()

    def walk(results):
        for k, v in (results or {}).items():
            if isinstance(v, dict) and v.get("Success") is False:
                failed[(k, v.get("Severity"))] += 1

    for res in data.get("Results") or []:
        walk(res.get("Results"))
        pr = res.get("PodResult") or {}
        walk(pr.get("Results"))
        for ct in pr.get("ContainerResults") or []:
            walk(ct.get("Results"))
    return {"ran": True, "score": data.get("Score"),
            "failed_by_check": {f"{k}[{s}]": n for (k, s), n in failed.items()}}


def kube_linter(path, raw_dir, n_loc):
    r = _run([os.path.join(BIN, "kube-linter.exe"), "lint", "--format", "json", path])
    _save(raw_dir, "kube-linter.json", r.stdout)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ran": False, "stderr": r.stderr[-1500:]}
    by_check = collections.Counter(rep["Check"] for rep in data.get("Reports") or [])
    zhang = {s: by_check.get(s, 0) for s in ZHANG_SMELLS}
    zhang_total = sum(zhang.values())
    return {"ran": True, "total": sum(by_check.values()), "by_check": dict(by_check),
            "zhang_smells": zhang, "zhang_total": zhang_total,
            "zhang_density_per_kloc": round(1000 * zhang_total / n_loc, 1) if n_loc else None,
            "zhang_any": zhang_total > 0}


def _selector_matches(selector, labels):
    ml = (selector or {}).get("matchLabels") or {}
    if not ml and not (selector or {}).get("matchExpressions"):
        return False
    return all(labels.get(k) == v for k, v in ml.items())


def checklist(docs):
    """Reliability Controls Checklist (design doc §6), per workload; 1/0/None (N/A).
    Applicability: replicas (1), PDB (8), spread (9) apply to Deployment and StatefulSet;
    probes (2,3) to long-running workloads (not Job/CronJob); strategy (7) to Deployment,
    StatefulSet, DaemonSet; resources (4-6) and tag (10) to every workload. Probes, resources
    and tag must hold for every regular container (initContainers excluded from probes)."""
    pdbs = [d for d in docs if isinstance(d, dict) and d.get("kind") == "PodDisruptionBudget"]
    per = []
    for d in docs:
        if not isinstance(d, dict) or d.get("kind") not in POD_KINDS:
            continue
        kind = d["kind"]
        spec = d.get("spec") or {}
        ps = pod_spec(d) or {}
        cts = ps.get("containers") or []
        labels = ((spec.get("template") or {}).get("metadata") or {}).get("labels") or {} \
            if kind != "Pod" else (d.get("metadata") or {}).get("labels") or {}
        ns = (d.get("metadata") or {}).get("namespace")
        long_running = kind not in ("Job", "CronJob")
        replicated = kind in ("Deployment", "StatefulSet")
        res = lambda ct, a, b: bool(((ct.get("resources") or {}).get(a) or {}).get(b))

        def pinned(img):
            if not img:
                return False
            if "@sha256:" in img:
                return True
            last = img.rsplit("/", 1)[-1]
            return ":" in last and last.rsplit(":", 1)[1] != "latest"

        items = {
            "1_replicas_ge_2": (int(spec.get("replicas", 1)) >= 2) if kind == "Deployment" else None,
            "2_readiness": all(c.get("readinessProbe") for c in cts) if long_running and cts else None,
            "3_liveness": all(c.get("livenessProbe") for c in cts) if long_running and cts else None,
            "4_cpu_request": all(res(c, "requests", "cpu") for c in cts) if cts else None,
            "5_mem_request": all(res(c, "requests", "memory") for c in cts) if cts else None,
            "6_mem_limit": all(res(c, "limits", "memory") for c in cts) if cts else None,
            "7_rolling_update": (
                (spec.get("strategy") or {}).get("type") == "RollingUpdate" if kind == "Deployment" else
                (spec.get("updateStrategy") or {}).get("type") == "RollingUpdate"
                if kind in ("StatefulSet", "DaemonSet") else None),
            "8_pdb": any(_selector_matches((p.get("spec") or {}).get("selector"), labels)
                         and (p.get("metadata") or {}).get("namespace") == ns for p in pdbs)
            if replicated else None,
            "9_spread": bool(((ps.get("affinity") or {}).get("podAntiAffinity"))
                             or ps.get("topologySpreadConstraints")) if replicated else None,
            "10_pinned_tag": all(pinned(c.get("image")) for c in _containers(ps)) if cts else None,
        }
        # StatefulSet replicas are judged by item 1 only for Deployments (stateless workloads)
        per.append({"kind": kind, "name": (d.get("metadata") or {}).get("name"),
                    "items": {k: (None if v is None else int(v)) for k, v in items.items()}})
    applicable = [v for w in per for v in w["items"].values() if v is not None]
    by_item = {}
    for w in per:
        for k, v in w["items"].items():
            if v is not None:
                a = by_item.setdefault(k, [0, 0])
                a[0] += v
                a[1] += 1
    return {"ran": True, "n_workloads": len(per),
            "pct": round(100 * sum(applicable) / len(applicable), 1) if applicable else None,
            "by_item": {k: {"met": m, "applicable": n} for k, (m, n) in sorted(by_item.items())},
            "per_workload": per}


def run_static(docs, text, raw_dir):
    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, "manifest.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(yaml.safe_dump_all(docs, sort_keys=False))
    n_loc = loc(text)
    return {
        "loc": n_loc,
        "resource_counts": dict(collections.Counter(d.get("kind") for d in docs if isinstance(d, dict))),
        "d2": {"kubescape": kubescape(path, raw_dir), "trivy": trivy(path, raw_dir),
               "secrets": secrets(docs, text)},
        "d3": {"kube_score": kube_score(path, raw_dir), "polaris": polaris(path, raw_dir),
               "kube_linter": kube_linter(path, raw_dir, n_loc), "checklist": checklist(docs)},
    }
