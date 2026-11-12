"""D5 functional smoke test driven by a project's smoke.json."""
import json
import re
import shlex
import time

from reqlib import Component, Manifests, repo

PROBER_IMAGE = "curlimages/curl:8.11.1"


def selector(target):
    """A target with "component" also matches workloads identifiable by that name, for projects whose
    exact image path is not in docs_bundle/ (same rule as the D4 oracle split)."""
    if target.get("component"):
        return Component(*([target["component"]] if isinstance(target["component"], str) else target["component"]),
                         image=target.get("image"))
    return target["image"]


def resolve_url(m, target, ns):
    hits = m.exposed(selector(target), target["port"])
    if not hits:
        return None
    svc, port = hits[0]
    svc_ns = svc.get("metadata", {}).get("namespace") or ns
    scheme = target.get("scheme", "http")
    return f"{scheme}://{svc['metadata']['name']}.{svc_ns}.svc.cluster.local:{port['port']}"


def _labels_match(sel, labels):
    """LabelSelector semantics (matchLabels + matchExpressions); an empty selector matches everything."""
    sel = sel or {}
    if any(labels.get(k) != v for k, v in (sel.get("matchLabels") or {}).items()):
        return False
    for e in sel.get("matchExpressions") or []:
        k, op, vals = e.get("key"), e.get("operator"), e.get("values") or []
        if (op == "In" and labels.get(k) not in vals) or (op == "NotIn" and labels.get(k) in vals)                 or (op == "Exists" and k not in labels) or (op == "DoesNotExist" and k in labels):
            return False
    return True


def client_placement(docs, target, ns):
    """Where an in-cluster client must sit to be allowed to reach `target` under the config's OWN
    NetworkPolicies (a config that admits only, e.g., its ingress controller is hardened, not broken).
    -> {"namespace", "create_namespace", "namespace_labels", "pod_labels", "via"}."""
    default = {"namespace": ns, "create_namespace": False, "namespace_labels": {}, "pod_labels": {}, "via": "default"}
    hits = Manifests(docs).exposed(selector(target), target["port"])
    if not hits:
        return default
    svc, sport = hits[0]
    svc_ns = (svc.get("metadata") or {}).get("namespace") or ns
    sel = (svc.get("spec") or {}).get("selector") or {}
    pods = []  # pod-template labels of the workloads behind the Service
    cports = []  # their container ports, to resolve a named targetPort / named policy port
    for d in docs:
        tspec = ((d.get("spec") or {}).get("template") or {}) if isinstance(d, dict) else {}
        labels = (tspec.get("metadata") or {}).get("labels") or {}
        if sel and ((d.get("metadata") or {}).get("namespace") or ns) == svc_ns and all(labels.get(k) == v for k, v in sel.items()):
            pods.append(labels)
            for c in (tspec.get("spec") or {}).get("containers") or []:
                cports += c.get("ports") or []
    tport = sport.get("targetPort", sport.get("port"))
    # A port can be referred to by number or by its container-port name (Service targetPort and NetworkPolicy
    # ports alike); treat both spellings of the target port as the same port, as Kubernetes does.
    tports = {tport}
    for cp in cports:
        if tport in (cp.get("name"), cp.get("containerPort")):
            tports |= {cp.get("name"), cp.get("containerPort")}
    tports.discard(None)
    rules = []
    for d in docs:
        if not isinstance(d, dict) or d.get("kind") != "NetworkPolicy" or ((d.get("metadata") or {}).get("namespace") or ns) != svc_ns:
            continue
        spec = d.get("spec") or {}
        if "Ingress" in (spec.get("policyTypes") or ["Ingress"]) and any(_labels_match(spec.get("podSelector"), l) for l in pods):
            rules += [(d["metadata"]["name"], r) for r in spec.get("ingress") or []]
    selected = any(isinstance(d, dict) and d.get("kind") == "NetworkPolicy"
                   and ((d.get("metadata") or {}).get("namespace") or ns) == svc_ns
                   and "Ingress" in ((d.get("spec") or {}).get("policyTypes") or ["Ingress"])
                   and any(_labels_match((d.get("spec") or {}).get("podSelector"), l) for l in pods) for d in docs)
    if not selected:
        return default
    ok_port = lambda r: not r.get("ports") or any(p.get("port") is None or p.get("port") in tports for p in r["ports"])
    ns_peers, pod_peers = [], []
    for pname, r in rules:
        if not ok_port(r):
            continue
        if not r.get("from"):
            return {**default, "via": f"{pname}: any source"}
        for peer in r["from"]:
            if "namespaceSelector" in peer:
                ns_peers.append((pname, peer))
            elif "podSelector" in peer:
                pod_peers.append((pname, peer))
    # Prefer a namespace peer (an ingress-controller-like client) over impersonating an app pod in the
    # app's own namespace, where the prober's labels could be picked up by the app's own Services.
    for pname, peer in ns_peers:
        nl = dict((peer["namespaceSelector"] or {}).get("matchLabels") or {})
        name = nl.get("kubernetes.io/metadata.name") or f"{ns}-client"
        nl.pop("kubernetes.io/metadata.name", None)
        return {"namespace": name, "create_namespace": True, "namespace_labels": nl,
                "pod_labels": dict(((peer.get("podSelector") or {}).get("matchLabels")) or {}), "via": pname}
    for pname, peer in pod_peers:
        return {"namespace": svc_ns, "create_namespace": False, "namespace_labels": {},
                "pod_labels": dict((peer["podSelector"] or {}).get("matchLabels") or {}), "via": pname}
    return {**default, "via": "no permitting ingress rule (client blocked by config)"}


def label_args(labels):
    return ["--labels=" + ",".join(f"{k}={v}" for k, v in labels.items())] if labels else []


def prober_overrides(pod, command):
    """`kubectl run --overrides` making a prober pod comply with the 'restricted' Pod Security Standard, so it can
    run in a namespace that a configuration labels as restricted (curlimages/curl already runs as uid 100)."""
    return json.dumps({"spec": {
        "securityContext": {"runAsNonRoot": True, "runAsUser": 100, "seccompProfile": {"type": "RuntimeDefault"}},
        "containers": [{"name": pod, "image": PROBER_IMAGE, "command": command,
                        "securityContext": {"allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}}}]}})


def start_prober(kubectl, ns, pod_labels=None, pod="smoke-prober"):
    kubectl("run", pod, "-n", ns, "--image", PROBER_IMAGE, "--restart=Never", *label_args(pod_labels),
            "--overrides", prober_overrides(pod, ["sleep", "3600"]))
    kubectl("wait", "-n", ns, "--for=condition=Ready", f"pod/{pod}", "--timeout=120s")


def http_check(kubectl, ns, check, base, pod="smoke-prober"):
    cmd = ["curl", "-s", "-o", "/tmp/body", "-w", "%{http_code}", "--max-time", "10", "-L"]
    if check.get("insecure_tls") or check["target"].get("scheme") == "https":
        cmd.append("-k")
    if check.get("method", "GET") != "GET":
        cmd += ["-X", check["method"]]
    for k, v in (check.get("form") or {}).items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    for k, v in (check.get("headers") or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(base + check.get("path", "/"))
    script = " ".join(shlex.quote(c) for c in cmd) + "; echo; cat /tmp/body"
    r = kubectl("exec", "-n", ns, pod, "--", "sh", "-c", script, timeout=60)
    code, _, body = r.stdout.partition("\n")
    ok = code.strip() == str(check.get("expect_status", 200))
    if ok and check.get("expect_body"):
        ok = check["expect_body"] in body
    return ok, f"HTTP {code.strip() or 'none'}" + ("" if ok or not check.get("expect_body") else f", body lacks {check['expect_body']!r}")


def pod_running(kubectl, ns_list, image):
    for n in ns_list:
        out = kubectl("get", "pods", "-n", n, "-o", "json").stdout
        for p in json.loads(out or '{"items":[]}')["items"]:
            if p["status"].get("phase") != "Running":
                continue
            for c in p["spec"]["containers"]:
                if repo(c["image"]) == repo(image):
                    return n, p["metadata"]["name"], c["name"]
    return None


def exec_check(kubectl, ns_list, check):
    hit = pod_running(kubectl, ns_list, check["exec"]["image"])
    if not hit:
        return False, f"no running pod with image {check['exec']['image']}"
    n, pod, container = hit
    r = kubectl("exec", "-n", n, pod, "-c", container, "--", *check["exec"]["command"], timeout=60)
    out = r.stdout.strip()
    ok = r.returncode == 0 and re.search(check.get("expect_regex", "."), out, re.M) is not None
    return ok, f"output {out[:80]!r}" if out else f"exit {r.returncode}: {r.stderr.strip()[:120]}"


def run_smoke(spec, docs, ns, ns_list, kubectl, client=None):
    """Run every check in order; each retries for up to retry_seconds (default 30).
    `client` (from client_placement) is where the prober pod runs; URLs are always fully qualified."""
    m = Manifests(docs)
    client = client or {"namespace": ns, "pod_labels": {}, "via": "default"}
    pns = client.get("namespace", ns)
    start_prober(kubectl, pns, client.get("pod_labels"))
    extra = {}  # (namespace, labels) -> prober pod name, for checks whose target admits a different client
    results = []
    for check in spec["checks"]:
        where, pod = pns, "smoke-prober"
        if "target" in check and "exec" not in check:
            # The config's own NetworkPolicies may admit a different client to this check's target (e.g. a scraper
            # that only the dashboard pod may call): probe from where that target admits a client.
            own = client_placement(docs, check["target"], ns)
            if own["via"] not in ("default", client.get("via")) and (own["namespace"], own["pod_labels"]) != (pns, client.get("pod_labels")):
                key = (own["namespace"], json.dumps(own["pod_labels"], sort_keys=True))
                if key not in extra:
                    if own["create_namespace"] and own["namespace"] not in ns_list:
                        kubectl("create", "namespace", own["namespace"])
                        ns_list.append(own["namespace"])
                        if own["namespace_labels"]:
                            kubectl("label", "namespace", own["namespace"], "--overwrite",
                                    *[f"{k}={v}" for k, v in own["namespace_labels"].items()])
                    extra[key] = f"smoke-prober-{len(extra) + 2}"
                    start_prober(kubectl, own["namespace"], own["pod_labels"], pod=extra[key])
                where, pod = own["namespace"], extra[key]
        deadline = time.time() + check.get("retry_seconds", 30)
        while True:
            if "exec" in check:
                ok, detail = exec_check(kubectl, ns_list, check)
            else:
                base = resolve_url(m, check["target"], ns)
                ok, detail = (http_check(kubectl, where, check, base, pod=pod) if base
                              else (False, f"no Service routes to {check['target']['image']}:{check['target']['port']}"))
            if ok or time.time() > deadline:
                break
            time.sleep(3)
        results.append({"name": check["name"], "passed": ok, "detail": detail,
                        **({"prober": f"{where}/{pod}"} if pod != "smoke-prober" else {})})
        if pod != "smoke-prober":
            # A prober wearing an app pod's labels can be selected by that app's Services; remove it before the
            # next check (waiting for deletion) so it never receives traffic meant for the app.
            kubectl("delete", "pod", "-n", where, pod, "--wait=true", "--timeout=60s")
            extra = {k: v for k, v in extra.items() if v != pod}
    kubectl("delete", "pod", "-n", pns, "smoke-prober", "--wait=false")
    return results
