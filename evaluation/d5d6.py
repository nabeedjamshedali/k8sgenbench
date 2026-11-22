"""K8sGenBench D5 (runtime deployment + smoke test) and D6 (resilience under faults).

Images: every image a config references is served from the local registry mirror (see
tools/setup_cluster.py). For projects whose exact image path is not in docs_bundle/
(datasets/<P>/image_aliases.json), a reference that is not pullable as written but whose repository
basename names a documented component is served the canonical image under the config's own
reference. The manifest is never edited; each image's provenance is recorded in the result.

Runtime shims (datasets/<P>/runtime_shims.json): a start-up prerequisite that the binary enforces but
docs_bundle/ never states (e.g. a mandatory env var only visible in source) is injected at deploy
time, only where the config does not already set it. Applied identically to every source; each
injection is recorded in the result.

All times are taken from the cluster's own clock (kind node / kubelet / container runtime
timestamps), never the host's, so host-VM clock skew cannot distort recovery or availability.
"""
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATASETS = os.path.join(ROOT, "datasets")
sys.path.insert(0, os.path.join(DATASETS, "common"))
from reqlib import Manifests  # noqa: E402
from smoke import PROBER_IMAGE, client_placement, label_args, prober_overrides, resolve_url, run_smoke, selector  # noqa: E402

BIN = os.path.join(ROOT, "tools", "bin")
CTX = "kind-k8sgen"
CLUSTER = "k8sgen"
CONTROL_PLANE = f"{CLUSTER}-control-plane"
MIRROR = "localhost:5001"
WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet"}
PROTECTED_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease", "default", "local-path-storage"}
READY_TIMEOUT = 300
RECOVERY_TIMEOUT = 180
FAULT_REPS = 3


def run(args, timeout=900, input=None):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore",
                          timeout=timeout, input=input)


def kubectl(*args, **kw):
    return run([os.path.join(BIN, "kubectl.exe"), "--context", CTX, *args], **kw)


def kjson(*args):
    """An API error is an infrastructure failure, never data: retry, then abort the config so nothing is
    recorded for it (an empty list here once turned a sick Docker engine into a 'no_workloads' result)."""
    for attempt in range(3):
        r = kubectl(*args, "-o", "json")
        if r.returncode == 0:
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                pass
        time.sleep(5)
    raise RuntimeError(f"INFRA: kubectl {' '.join(args)} failed 3x: {r.stderr.strip()[-300:]}")


def cluster_now():
    return float(run(["docker", "exec", CONTROL_PLANE, "date", "+%s.%N"]).stdout.strip())


def ts(s):
    """RFC3339 (kubelet / runtime timestamp) -> epoch seconds."""
    s = s.strip().rstrip("Z")
    if "." in s:
        head, frac = s.split(".", 1)
        s = f"{head}.{frac[:6]}"
        fmt = "%Y-%m-%dT%H:%M:%S.%f"
    else:
        fmt = "%Y-%m-%dT%H:%M:%S"
    return dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc).timestamp()


# ---------------------------------------------------------------- images

def images(docs):
    found = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("containers", "initContainers") and isinstance(v, list):
                    found.update(c["image"] for c in v if isinstance(c, dict) and c.get("image"))
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(docs)
    return sorted(found)


def split_ref(ref):
    """-> (registry host, repository path, tag or None, digest or None) using Docker's defaulting rules."""
    digest = None
    if "@" in ref:
        ref, digest = ref.split("@", 1)
    first, _, rest = ref.partition("/")
    if rest and ("." in first or ":" in first or first == "localhost"):
        host, path = first, rest
    else:
        host, path = "docker.io", ref
        if "/" not in path:
            path = "library/" + path
    tag = None
    last = path.rsplit("/", 1)[-1]
    if ":" in last:
        path, tag = path.rsplit(":", 1)
    if not tag and not digest:
        tag = "latest"
    return host, path, tag, digest


def mirror_has(path, tag):
    req = urllib.request.Request(f"http://{MIRROR}/v2/{path}/manifests/{tag}", method="HEAD", headers={
        "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json, "
                  "application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


DEFINITIVE_PULL_FAILURE = ("manifest unknown", "not found", "unauthorized", "denied", "invalid reference",
                           "repository does not exist", "no matching manifest", "name unknown")


def _network_up():
    try:
        urllib.request.urlopen(urllib.request.Request("https://registry-1.docker.io/v2/", method="HEAD"), timeout=20)
        return True
    except urllib.error.HTTPError:  # 401 from the registry still proves connectivity
        return True
    except (urllib.error.URLError, OSError):
        return False


def docker_pull(ref):
    """True if pulled; False only on a DEFINITIVE answer that the reference does not exist or is not public (a
    config defect). A transient network failure is retried and then raised as INFRA, never scored as 'unpullable'."""
    for attempt in range(3):
        try:
            r = run(["docker", "pull", "--platform", "linux/amd64", ref], timeout=3600)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode == 0:
            return True
        err = (r.stdout + r.stderr).lower()
        if any(s in err for s in DEFINITIVE_PULL_FAILURE):
            return False
        if "no such host" in err and _network_up():
            return False  # the registry host itself does not exist, while the network is demonstrably up
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"INFRA: docker pull {ref} failed transiently 3x (network); not scored as unpullable")


def push_to_mirror(src_ref, path, tag):
    dst = f"{MIRROR}/{path}:{tag}"
    run(["docker", "tag", src_ref, dst])
    return run(["docker", "push", dst], timeout=1800).returncode == 0


def kind_load(ref):
    return run([os.path.join(BIN, "kind.exe"), "load", "docker-image", ref, "--name", CLUSTER],
               timeout=1800).returncode == 0


def nodes():
    return run([os.path.join(BIN, "kind.exe"), "get", "nodes", "--name", CLUSTER]).stdout.split()


def prepull(refs):
    """Pull every servable image onto every node BEFORE the Ready clock starts (design doc §7), so
    image transfer never overlaps container start-up inside the measured window."""
    failed = []
    for node in nodes():
        for ref in refs:
            if run(["docker", "exec", node, "crictl", "pull", ref], timeout=1800).returncode:
                failed.append(f"{node}:{ref}")
    return failed


def load_aliases(project):
    f = os.path.join(DATASETS, project, "image_aliases.json")
    if not os.path.exists(f):
        return {}
    return {tok.lower(): canon for canon, toks in json.load(open(f))["aliases"].items() for tok in toks}


LEDGER = os.path.join(HERE, "mirror_ledger.json")  # mirror path:tag -> what was pushed there and why


def _ledger():
    return json.load(open(LEDGER)) if os.path.exists(LEDGER) else {}


def _record(key, entry):
    led = _ledger()
    led[key] = entry
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1, sort_keys=True)


def provision(ref, aliases):
    host, path, tag, digest = split_ref(ref)
    rec = {"ref": ref, "as_written_pullable": None, "served": None}
    if digest:
        # A digest pin must stay byte-identical, so it is never re-pushed: nodes pull it upstream in prepull().
        ok = docker_pull(ref)
        rec.update(as_written_pullable=ok, served="upstream-prepulled" if ok else "unavailable")
        return rec
    key = f"{path}:{tag}"
    known = _ledger().get(key)
    if known and mirror_has(path, tag):
        rec.update(as_written_pullable=known["as_written_pullable"], served=known["served"])
        return rec
    if docker_pull(ref):
        rec.update(as_written_pullable=True, served="mirror" if push_to_mirror(ref, path, tag) else "upstream")
    else:
        rec["as_written_pullable"] = False
        canon = aliases.get(path.rsplit("/", 1)[-1].lower())
        if canon and docker_pull(canon) and push_to_mirror(canon, path, tag):
            rec["served"] = f"alias:{canon}"
        else:
            rec["served"] = "unavailable"
    if rec["served"] not in ("upstream", "unavailable"):
        _record(key, {"ref": ref, "as_written_pullable": rec["as_written_pullable"], "served": rec["served"]})
    return rec


# ---------------------------------------------------------------- deploy

def load_shims(project):
    f = os.path.join(DATASETS, project, "runtime_shims.json")
    return json.load(open(f)) if os.path.exists(f) else {}


def state_namespace(c, owner_ns, rule):
    """Namespace in which a container's application reads its own state objects: the value of the `rule["arg"]` flag,
    else of the `rule["env"]` variable (a fieldRef to metadata.namespace means the pod's own namespace), else
    `rule["default"]`. None stands for the configuration's default namespace (the D5 namespace)."""
    argv = [str(a) for a in (c.get("command") or []) + (c.get("args") or [])]
    for i, a in enumerate(argv):
        if a.startswith(rule["arg"] + "="):
            return a.split("=", 1)[1]
        if a == rule["arg"] and i + 1 < len(argv):
            return argv[i + 1]
    for e in c.get("env") or []:
        if isinstance(e, dict) and e.get("name") == rule["env"]:
            if e.get("value"):
                return e["value"]
            if ((e.get("valueFrom") or {}).get("fieldRef") or {}).get("fieldPath") == "metadata.namespace":
                return owner_ns
    return rule["default"]


def apply_shims(docs, shims):
    import copy
    docs, applied = copy.deepcopy(docs), []
    env_shims, obj_shims = shims.get("env", []), shims.get("objects", [])
    wanted = []  # (object shim, namespace) for containers that need a state object the configuration does not define

    def walk(o, owner, owner_ns):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("containers", "initContainers") and isinstance(v, list):
                    for c in v:
                        if not isinstance(c, dict) or not c.get("image"):
                            continue
                        base = split_ref(c["image"])[1].rsplit("/", 1)[-1].lower()
                        for sh in env_shims:
                            env = c.setdefault("env", []) if base == sh["image_basename"] else None
                            if env is not None and not any(isinstance(e, dict) and e.get("name") == sh["name"] for e in env):
                                env.append({"name": sh["name"], "value": sh["value"]})
                                applied.append({"object": owner, "container": c.get("name"), "env": sh["name"]})
                        for sh in obj_shims:
                            if base == sh["image_basename"]:
                                wanted.append((sh, state_namespace(c, owner_ns, sh["namespace"])))
                else:
                    walk(v, owner, owner_ns)
        elif isinstance(o, list):
            for v in o:
                walk(v, owner, owner_ns)
    for d in list(docs):
        if isinstance(d, dict):
            md = d.get("metadata") or {}
            walk(d, f"{d.get('kind')}/{md.get('name')}", md.get("namespace"))
    # An object shim fires only when the configuration defines no object of that kind and name at all (like the env
    # shim's "does not already set it"); the object is created where the application looks for it, and recorded.
    done = set()
    for sh, ns in wanted:
        defined = any(isinstance(d, dict) and d.get("kind") == sh["kind"]
                      and (d.get("metadata") or {}).get("name") == sh["name"] for d in docs)
        if defined or (sh["name"], ns) in done:
            continue
        obj = {"apiVersion": "v1", "kind": sh["kind"], "metadata": {"name": sh["name"]}, **sh["body"]}
        if ns:
            obj["metadata"]["namespace"] = ns
        docs.append(obj)
        done.add((sh["name"], ns))
        applied.append({"object": f"{sh['kind']}/{sh['name']}", "namespace": ns or "(default)", "created": True})
    return docs, applied


def split_docs(docs):
    namespaces = [d for d in docs if d.get("kind") == "Namespace"]
    explicit = [d for d in docs if d.get("kind") != "Namespace" and (d.get("metadata") or {}).get("namespace")]
    implicit = [d for d in docs if d.get("kind") != "Namespace" and d not in explicit]
    return namespaces, explicit, implicit


def apply_all(docs, ns):
    namespaces, explicit, implicit = split_docs(docs)
    hard_ns = sorted({d["metadata"]["namespace"] for d in explicit} | {d["metadata"]["name"] for d in namespaces})
    for n in hard_ns:
        if n not in PROTECTED_NAMESPACES and not any(d["metadata"]["name"] == n for d in namespaces):
            kubectl("create", "namespace", n)  # referenced but undeclared; D1 records it as a finding
    errors = []
    for d, flag in [(d, []) for d in namespaces + explicit] + [(d, ["-n", ns]) for d in implicit]:
        r = kubectl("apply", *flag, "-f", "-", input=yaml.safe_dump(d))
        if r.returncode:
            errors.append({"kind": d.get("kind"), "name": (d.get("metadata") or {}).get("name"),
                           "error": r.stderr.strip()[-400:]})
    return [ns] + hard_ns, errors


def workload_status(targets):
    status = []
    for n in targets:
        for it in kjson("get", "deploy,sts,ds", "-n", n)["items"]:
            st = it.get("status", {})
            want = it["spec"].get("replicas", st.get("desiredNumberScheduled", 1))
            ready = st.get("readyReplicas", st.get("numberReady", 0)) or 0
            status.append({"ns": n, "kind": it["kind"], "name": it["metadata"]["name"], "ready": ready, "want": want})
    return status


def failure_reason(targets):
    reasons = []
    for n in targets:
        for p in kjson("get", "pods", "-n", n)["items"]:
            st = p.get("status", {})
            for cs in (st.get("initContainerStatuses") or []) + (st.get("containerStatuses") or []):
                w = (cs.get("state") or {}).get("waiting") or {}
                if w.get("reason"):
                    reasons.append(w["reason"])
                elif (cs.get("state") or {}).get("running") and not cs.get("ready"):
                    reasons.append("NotReady(probe)")
            for c in st.get("conditions") or []:
                if c.get("type") == "PodScheduled" and c.get("status") == "False":
                    reasons.append(f"Pending({c.get('reason')}: {(c.get('message') or '')[:120]})")
    if not reasons:
        return "timeout"
    for key in ("ImagePullBackOff", "ErrImagePull", "CrashLoopBackOff", "CreateContainerConfigError", "Pending", "NotReady(probe)"):
        if any(r.startswith(key) for r in reasons):
            return key if key != "Pending" else next(r for r in reasons if r.startswith("Pending"))
    return sorted(set(reasons))[0]


def diagnostics(targets, docs=()):
    """Evidence for a failed deployment, taken before the namespace is deleted: per pod, restarts and how the
    container last ended; per object, warning-event counts (e.g. 'Unhealthy: Liveness probe failed', FailedMount).
    In a shared system namespace (a config that deploys into kube-system), only the config's own pods and events
    count; the cluster's pods would otherwise take the log slots."""
    owners = [(d.get("metadata") or {}).get("name") for d in docs if d.get("kind") in WORKLOAD_KINDS | {"Job", "CronJob", "Pod"}]

    def own(n, obj):
        return n not in PROTECTED_NAMESPACES or any(obj == w or obj.startswith(f"{w}-") for w in owners if w)

    pods, events = [], {}
    for n in targets:
        for p in kjson("get", "pods", "-n", n)["items"]:
            if not own(n, p["metadata"]["name"]):
                continue
            for cs in (p.get("status") or {}).get("containerStatuses") or []:
                term = ((cs.get("lastState") or {}).get("terminated")) or {}
                if cs.get("restartCount") or not cs.get("ready"):
                    entry = {"pod": p["metadata"]["name"], "container": cs["name"],
                             "restarts": cs.get("restartCount", 0), "last_exit": term.get("exitCode"),
                             "last_reason": term.get("reason")}
                    if cs.get("restartCount") and len(pods) < 12:
                        # the crashed run's last lines usually name the cause (e.g. "chown: Operation not permitted")
                        lg = kubectl("logs", "-n", n, p["metadata"]["name"], "-c", cs["name"], "--previous",
                                     "--tail", "40", timeout=30)
                        entry["last_log"] = (lg.stdout or "").strip()[-3000:]
                    pods.append(entry)
        for e in kjson("get", "events", "-n", n, "--field-selector", "type=Warning").get("items", []):
            if not own(n, e["involvedObject"].get("name") or ""):
                continue
            msg = (e.get("message") or "").split(":")[0][:60]
            key = f"{e['involvedObject'].get('name')}|{e.get('reason')}: {msg}"
            events[key] = events.get(key, 0) + (e.get("count") or 1)
    return {"pods": pods[:40], "warning_events": dict(sorted(events.items(), key=lambda kv: -kv[1])[:40])}


# an ephemeral container that meets Pod Security "restricted", so it is admitted in any namespace; it only reads files
LISTEN_SPEC = {"securityContext": {"runAsNonRoot": True, "runAsUser": 65534, "allowPrivilegeEscalation": False,
                                   "capabilities": {"drop": ["ALL"]}, "seccompProfile": {"type": "RuntimeDefault"}}}


def listening(ns, pod):
    """TCP ports the pod listens on, read from /proc/net/tcp{,6} by an ephemeral container that shares the pod's
    network namespace (no traffic is sent, so NetworkPolicies cannot affect the answer); None if it cannot be read."""
    spec = os.path.join(tempfile.gettempdir(), "k8sgen_listen_spec.json")
    with open(spec, "w") as f:
        json.dump(LISTEN_SPEC, f)
    # not --attach: a container that exits within milliseconds can end before the attach, losing its output
    name = f"listen-{int(time.time() * 1000) % 10**8}"
    if kubectl("debug", "-n", ns, f"pod/{pod}", "--image", PROBER_IMAGE, "--profile", "restricted", "--custom", spec,
               "--container", name, "--quiet", "--", "cat", "/proc/net/tcp", "/proc/net/tcp6", timeout=60).returncode:
        return None
    deadline = time.time() + 60
    while time.time() < deadline:
        st = kubectl("get", "pod", "-n", ns, pod, "-o",
                     f"jsonpath={{.status.ephemeralContainerStatuses[?(@.name=='{name}')].state.terminated.reason}}").stdout
        if st.strip():
            break
        time.sleep(1)
    r = kubectl("logs", "-n", ns, pod, "-c", name, timeout=30)
    ports = set()
    for line in (r.stdout or "").splitlines():
        f = line.split()
        # 0A = LISTEN; a socket bound to loopback only (127.0.0.1, ::1) is not reachable through a Service
        if len(f) > 3 and ":" in f[1] and f[3] == "0A":
            addr, port = f[1].rsplit(":", 1)
            if addr not in ("0100007F", "00000000000000000000000001000000"):
                ports.add(int(port, 16))
    return sorted(ports) or None


def service_listen_check(docs, ns):
    """For every Service with a selector: does a running selected pod listen on each targetPort? Evidence for the
    repair gate only (an all-Ready deployment can still route its Services to ports nobody serves); no metric uses it.
    Runs after D5 and D6, so it cannot affect their measurements."""
    out, cache = [], {}
    for s in docs:
        if s.get("kind") != "Service" or not (s.get("spec") or {}).get("selector"):
            continue
        sns = (s.get("metadata") or {}).get("namespace") or ns
        pods = [p for p in service_pods(s, sns) if (p.get("status") or {}).get("phase") == "Running"]
        for port in s["spec"].get("ports") or []:
            entry = {"service": s["metadata"]["name"], "namespace": sns, "port": port.get("port"),
                     "target_port": port.get("targetPort", port.get("port")), "pod": None, "listening": None, "ok": None}
            if pods:
                p = pods[0]
                tp = entry["target_port"]
                if isinstance(tp, str) and not tp.isdigit():
                    tp = next((cp.get("containerPort") for c in p["spec"]["containers"] for cp in c.get("ports") or []
                               if cp.get("name") == tp), None)
                key = (sns, p["metadata"]["name"])
                if key not in cache:
                    cache[key] = listening(sns, p["metadata"]["name"])
                entry.update({"pod": p["metadata"]["name"], "listening": cache[key]})
                if tp is not None and cache[key] is not None:
                    entry["ok"] = int(tp) in cache[key]
            out.append(entry)
    return out


def cleanup(docs, targets):
    for d in docs:
        kind, name = d.get("kind"), (d.get("metadata") or {}).get("name")
        if not name or kind == "Namespace":
            continue
        ns_d = (d.get("metadata") or {}).get("namespace")
        if kind.startswith("Cluster") or kind in ("CustomResourceDefinition", "StorageClass", "PersistentVolume",
                                                   "PriorityClass", "IngressClass", "APIService",
                                                   "ValidatingWebhookConfiguration", "MutatingWebhookConfiguration"):
            kubectl("delete", kind, name, "--ignore-not-found", "--wait=false")
        elif ns_d in PROTECTED_NAMESPACES:
            kubectl("delete", kind, name, "-n", ns_d, "--ignore-not-found", "--wait=false")
    for n in targets:
        if n not in PROTECTED_NAMESPACES:
            kubectl("delete", "namespace", n, "--ignore-not-found", "--wait=false")
    deadline = time.time() + 180
    while time.time() < deadline:
        if all(kubectl("get", "namespace", n).returncode for n in targets if n not in PROTECTED_NAMESPACES):
            break
        time.sleep(2)


# ---------------------------------------------------------------- D6

def service_pods(svc, ns):
    sel = (svc.get("spec") or {}).get("selector") or {}
    if not sel:
        return []
    label = ",".join(f"{k}={v}" for k, v in sel.items())
    return [p for p in kjson("get", "pods", "-n", ns, "-l", label)["items"]
            if not p["metadata"].get("deletionTimestamp")]


def ready_time(pod):
    for c in pod.get("status", {}).get("conditions") or []:
        if c.get("type") == "Ready" and c.get("status") == "True":
            return ts(c["lastTransitionTime"])
    return None


def start_prober(ns, url, insecure, pod_labels=None):
    curl = "curl -s -o /dev/null -w '%{http_code}' --max-time 1" + (" -k" if insecure else "")
    loop = f"while true; do echo $({curl} {shlex.quote(url)}); sleep 0.2; done"
    kubectl("run", "d6-prober", "-n", ns, "--image", PROBER_IMAGE, "--restart=Never", *label_args(pod_labels),
            "--overrides", prober_overrides("d6-prober", ["sh", "-c", loop]))
    kubectl("wait", "-n", ns, "--for=condition=Ready", "pod/d6-prober", "--timeout=120s")


def availability(ns, t0, t1):
    lines = kubectl("logs", "-n", ns, "d6-prober", "--timestamps").stdout.splitlines()
    codes = []
    for ln in lines:
        stamp, _, code = ln.partition(" ")
        try:
            t = ts(stamp)
        except ValueError:
            continue
        if t0 <= t <= t1:
            codes.append(code.strip())
    if not codes:
        return None, 0
    ok = sum(1 for c in codes if c[:1] in ("2", "3"))
    return round(100 * ok / len(codes), 1), len(codes)


def wait_stable(svc, ns, n_expected, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        pods = service_pods(svc, ns)
        if len([p for p in pods if ready_time(p)]) >= n_expected:
            return pods
        time.sleep(2)
    return service_pods(svc, ns)


def restarts(pod):
    return sum(cs.get("restartCount", 0) for cs in pod.get("status", {}).get("containerStatuses") or [])


def one_fault(fault, svc, ns, port, n_expected, prober_ns):
    pods = wait_stable(svc, ns, n_expected)
    # Fewest restarts first: with >1 replica each repetition hits a fresh pod, so kubelet's
    # CrashLoopBackOff from an earlier repetition does not leak into the next one.
    ready = sorted([p for p in pods if ready_time(p)], key=lambda p: (restarts(p), p["metadata"]["name"]))
    if not ready:
        return {"ran": False, "reason": "no Ready pod behind the target Service"}
    victim = ready[0]
    vname = victim["metadata"]["name"]
    # By UID, not name: a StatefulSet recreates the deleted pod under the same name (e.g. n8n-0).
    before = {p["metadata"]["uid"] for p in pods}
    t_kill = cluster_now()
    if fault == "pod_delete":
        kubectl("delete", "pod", vname, "-n", ns, "--grace-period=0", "--force", "--wait=false")
        restarts0 = None
    else:
        cstats = victim["status"].get("containerStatuses") or []
        target = next((cs for cs in cstats
                       for c in victim["spec"]["containers"] if c["name"] == cs["name"]
                       and any(str(pp.get("containerPort")) == str(port) for pp in c.get("ports") or [])),
                      cstats[0] if cstats else None)
        if not target or not target.get("containerID"):
            return {"ran": False, "reason": "victim has no running container"}
        restarts0 = target.get("restartCount", 0)
        cid = target["containerID"].split("://", 1)[-1]
        run(["docker", "exec", victim["spec"]["nodeName"], "crictl", "stop", "--timeout", "0", cid])
    t_rec = None
    deadline = time.time() + RECOVERY_TIMEOUT
    while time.time() < deadline:
        if fault == "pod_delete":
            new = [p for p in service_pods(svc, ns) if p["metadata"]["uid"] not in before and ready_time(p)]
            if new:
                t_rec = min(ready_time(p) for p in new)
        else:
            p = kjson("get", "pod", vname, "-n", ns)
            cs = [c for c in (p.get("status", {}).get("containerStatuses") or []) if c["name"] == target["name"]]
            rt = ready_time(p) if p.get("status") else None
            if cs and cs[0].get("restartCount", 0) > restarts0 and cs[0].get("ready") and rt and rt >= t_kill - 1:
                t_rec = rt
        if t_rec:
            break
        time.sleep(1)
    ok = t_rec is not None
    window_end = (t_rec + 5) if ok else (t_kill + RECOVERY_TIMEOUT)
    while cluster_now() < window_end + 1:
        time.sleep(1)
    avail, n_probes = availability(prober_ns, t_kill, window_end)
    return {"ran": True, "victim": vname, "victim_prior_restarts": restarts(victim), "recovery_ok": ok,
            "recovery_time_s": round(max(t_rec - t_kill, 0), 1) if ok else None,
            "availability_pct": avail, "n_probes": n_probes}


def d6(docs, project, ns, client):
    spec = json.load(open(os.path.join(DATASETS, project, "smoke.json")))
    target = spec.get("d6_target")
    if not target:
        return {"ran": False, "reason": "no d6_target"}
    m = Manifests(docs)
    hits = m.exposed(selector(target), target["port"])
    if not hits:
        return {"ran": False, "reason": f"no Service routes to the D6 target {target.get('component') or target['image']}"}
    svc, sport = hits[0]
    svc_ns = (svc.get("metadata") or {}).get("namespace") or ns
    base = resolve_url(m, target, ns)
    n_expected = len([p for p in service_pods(svc, svc_ns) if ready_time(p)])
    pns = client["namespace"]
    start_prober(pns, base + target.get("path", "/"), target.get("scheme") == "https", client["pod_labels"])
    out = {"ran": True, "service": svc["metadata"]["name"], "n_ready_before": n_expected}
    try:
        for fault in ("pod_delete", "container_crash"):
            out[fault] = [one_fault(fault, svc, svc_ns, target["port"], n_expected, pns) for _ in range(FAULT_REPS)]
    finally:
        kubectl("delete", "pod", "d6-prober", "-n", pns, "--wait=false")
    return out


# ---------------------------------------------------------------- entry point

MIN_FREE_DISK_GB = 15
READY_STABLE_S = 20


def run_runtime(docs, project, run_id, with_d6=True):
    import shutil
    free_gb = shutil.disk_usage("C:\\").free / 1e9
    if free_gb < MIN_FREE_DISK_GB:
        # Stop the whole batch rather than fill the laptop's disk; nothing is recorded for this config.
        sys.exit(f"ABORT: only {free_gb:.1f} GB free on C: (< {MIN_FREE_DISK_GB} GB); free space and re-run.")
    aliases = load_aliases(project)
    imgs = [provision(i, aliases) for i in images(docs) + [PROBER_IMAGE]]
    prepull_failed = prepull([i["ref"] for i in imgs if i["served"] != "unavailable"])
    docs, shims_applied = apply_shims(docs, load_shims(project))
    ns = f"d5-{run_id}"
    kubectl("create", "namespace", ns)
    t0 = cluster_now()
    targets, apply_errors = apply_all(docs, ns)
    d5 = {"ran": True, "images": imgs, "shims_applied": shims_applied, "prepull_failed": prepull_failed, "apply_ok": not apply_errors, "apply_errors": apply_errors}
    d6_res = {"ran": False, "reason": "SKIPPED(not_deployed)"}
    try:
        # Ready = every workload at its desired Ready count continuously for READY_STABLE_S (a pod that
        # passes readiness and then crashes seconds later must not count); time-to-Ready is the start
        # of that stable window.
        deadline = time.time() + READY_TIMEOUT
        status, since = [], None
        while time.time() < deadline:
            status = workload_status(targets)
            if status and all(s["ready"] >= s["want"] for s in status):
                since = since or cluster_now()
                if cluster_now() - since >= READY_STABLE_S:
                    break
            else:
                since = None
            time.sleep(3)
        ready_ok = since is not None and cluster_now() - since >= READY_STABLE_S
        d5.update({
            "ready_ok": ready_ok,
            "time_to_ready_s": round(since - t0, 1) if ready_ok else None,
            "ready_replicas": sum(min(s["ready"], s["want"]) for s in status),
            "expected_replicas": sum(s["want"] for s in status),
            "workloads": status,
            "failure_reason": None if ready_ok else ("no_workloads" if not status else failure_reason(targets)),
        })
        if not ready_ok:
            try:
                d5["diagnostics"] = diagnostics(targets, docs)
            except Exception as e:  # evidence only; never fail the measurement over it
                d5["diagnostics"] = {"error": str(e)[:200]}
        spec = json.load(open(os.path.join(DATASETS, project, "smoke.json")))
        # Probers sit where the config's own NetworkPolicies admit a client to the entry service.
        entry = spec.get("d6_target") or next((c["target"] for c in spec["checks"] if "target" in c), None)
        client = client_placement(docs, entry, ns) if entry else {"namespace": ns, "create_namespace": False,
                                                                   "namespace_labels": {}, "pod_labels": {}, "via": "default"}
        d5["client_placement"] = client
        if client["create_namespace"]:
            if client["namespace"] not in targets:
                kubectl("create", "namespace", client["namespace"])
                targets.append(client["namespace"])
            if client["namespace_labels"]:
                kubectl("label", "namespace", client["namespace"], "--overwrite",
                        *[f"{k}={v}" for k, v in client["namespace_labels"].items()])
        if status:
            smoke = run_smoke(spec, docs, ns, targets, kubectl, client)
            d5["smoke"] = smoke
            d5["smoke_ok"] = all(r["passed"] for r in smoke)
        else:
            d5["smoke_ok"] = False
        # D6 injects faults into the entry service, so it needs a working application, not every auxiliary workload
        # Ready (e.g. a crashing load generator): run it if fully Ready OR the functional smoke test passed, and
        # record which gate admitted it so D6 can be reported under the strict (ready) definition as well.
        if (ready_ok or d5["smoke_ok"]) and with_d6:
            d6_res = d6(docs, project, ns, client)
            d6_res["gate"] = "ready" if ready_ok else "smoke_only"
        if status:
            try:
                d5["service_listen"] = service_listen_check(docs, ns)
            except Exception as e:  # evidence only; never fail the measurement over it
                d5["service_listen_error"] = str(e)[:200]
    finally:
        try:
            cleanup(docs, targets)
        except subprocess.TimeoutExpired as e:
            # A slow namespace delete must not discard a finished measurement; the next config uses a fresh namespace.
            print(f"WARN: cleanup timed out ({e.cmd[-3:]}); result kept", file=sys.stderr)
    return d5, d6_res
