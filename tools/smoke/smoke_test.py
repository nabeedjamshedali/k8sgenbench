"""End-to-end environment check: every pipeline stage on one sample app.

Usage: python tools/smoke/smoke_test.py
Requires the kind cluster from tools/kind-cluster.yaml to be running.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "..", "bin")
MANIFEST = os.path.join(HERE, "sample-app.yaml")
OUT = os.path.join(HERE, "out")
CTX = "kind-k8sgen"
CLUSTER = "k8sgen"
NS = "smoke"
K8S_VERSION = "1.37.0"
IMAGES = ["ghcr.io/stefanprodan/podinfo:6.7.1", "curlimages/curl:8.11.1"]


def tool(name):
    return os.path.join(BIN, name + ".exe")


def run(args, check=False, timeout=600):
    res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=timeout)
    if check and res.returncode:
        raise RuntimeError(f"{args[0]} failed: {res.stderr or res.stdout}")
    return res


def kubectl(*args, **kw):
    return run([tool("kubectl"), "--context", CTX, *args], **kw)


def save(name, text):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(text)


def stage(title, fn):
    t0 = time.time()
    try:
        detail = fn()
        print(f"[PASS] {title:38} {time.time() - t0:6.1f}s  {detail or ''}")
        return True
    except Exception as e:
        print(f"[FAIL] {title:38} {time.time() - t0:6.1f}s  {e}")
        return False


def d1_kubeconform():
    r = run([tool("kubeconform"), "-strict", "-summary", "-output", "json",
             "-kubernetes-version", K8S_VERSION, MANIFEST])
    save("kubeconform.json", r.stdout)
    summary = json.loads(r.stdout)["summary"]
    if r.returncode or summary["invalid"] or summary["errors"]:
        raise RuntimeError(r.stdout[-400:])
    return f"valid={summary['valid']}"


def d1_dry_run():
    kubectl("create", "namespace", NS)
    kubectl("label", "namespace", NS, "pod-security.kubernetes.io/enforce=restricted", "--overwrite", check=True)
    r = kubectl("apply", "-n", NS, "--dry-run=server", "-f", MANIFEST)
    save("dryrun.txt", r.stdout + r.stderr)
    if r.returncode or "violate" in r.stderr.lower():
        raise RuntimeError(r.stderr[-400:])
    return "accepted under PSS 'restricted'"


def d2_kubescape():
    out = os.path.join(OUT, "kubescape.json")
    r = run([tool("kubescape"), "scan", "framework", "nsa,mitre", MANIFEST,
             "--format", "json", "--output", out], timeout=900)
    data = json.load(open(out, encoding="utf-8"))
    score = data.get("summaryDetails", {}).get("complianceScore")
    if score is None:
        raise RuntimeError((r.stderr or r.stdout)[-400:])
    return f"compliance={score:.1f}%"


def d2_trivy():
    r = run([tool("trivy"), "config", "--quiet", "--format", "json", MANIFEST], timeout=900)
    save("trivy.json", r.stdout)
    results = json.loads(r.stdout).get("Results", [])
    counts = {}
    for res in results:
        for m in res.get("Misconfigurations", []) or []:
            counts[m["Severity"]] = counts.get(m["Severity"], 0) + 1
    return f"misconfigs={counts or 'none'}"


def d3_kube_score():
    r = run([tool("kube-score"), "score", "--output-format", "json", MANIFEST])
    save("kube-score.json", r.stdout)
    objs = json.loads(r.stdout)
    grades = {}
    for o in objs:
        for c in o.get("checks", []):
            grades[c["grade"]] = grades.get(c["grade"], 0) + 1
    return f"check grades={grades} (10=ok, 5=warning, 1=critical)"


def d3_polaris():
    r = run([tool("polaris"), "audit", "--audit-path", MANIFEST, "--format", "json"])
    save("polaris.json", r.stdout)
    return f"score={json.loads(r.stdout)['Score']}"


def d3_kube_linter():
    r = run([tool("kube-linter"), "lint", "--format", "json", MANIFEST])
    save("kube-linter.json", r.stdout)
    reports = json.loads(r.stdout).get("Reports") or []
    return f"findings={len(reports)} {sorted({x['Check'] for x in reports})}"


def preload(img):
    """Docker Desktop keeps multi-platform image indexes, which `kind load docker-image`
    cannot import, so export only linux/amd64 and load the archive instead."""
    run(["docker", "pull", "-q", img], check=True, timeout=900)
    archive = os.path.join(OUT, img.replace("/", "_").replace(":", "_") + ".tar")
    run(["docker", "save", "--platform", "linux/amd64", "-o", archive, img], check=True, timeout=900)
    run([tool("kind"), "load", "image-archive", archive, "--name", CLUSTER], check=True, timeout=900)
    os.remove(archive)


def d5_deploy():
    for img in IMAGES:
        preload(img)
    t0 = time.time()
    kubectl("apply", "-n", NS, "-f", MANIFEST, check=True)
    kubectl("rollout", "status", "-n", NS, "deployment/podinfo", "--timeout=300s", check=True, timeout=320)
    ready = time.time() - t0
    spread = kubectl("get", "pods", "-n", NS, "-l", "app=podinfo", "-o",
                     "jsonpath={.items[*].spec.nodeName}").stdout.split()
    return f"time-to-ready={ready:.1f}s replicas on nodes={sorted(set(spread))}"


def start_prober():
    pod = {
        "apiVersion": "v1", "kind": "Pod", "metadata": {"name": "prober"},
        "spec": {
            "securityContext": {"runAsNonRoot": True, "runAsUser": 100, "seccompProfile": {"type": "RuntimeDefault"}},
            "containers": [{
                "name": "prober", "image": IMAGES[1], "command": ["sh", "-c"],
                "args": ["while true; do curl -s -o /dev/null -w '%{http_code}\n' --max-time 1 http://podinfo/; "
                         "sleep 0.2; done"],
                "securityContext": {"allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}},
            }],
        },
    }
    path = os.path.join(OUT, "prober.json")
    json.dump(pod, open(path, "w"))
    kubectl("apply", "-n", NS, "-f", path, check=True)
    kubectl("wait", "-n", NS, "--for=condition=Ready", "pod/prober", "--timeout=120s", check=True, timeout=130)


def probe_samples():
    """(epoch_seconds, http_code) per probe; timestamps come from the container runtime."""
    from datetime import datetime
    out = []
    for line in kubectl("logs", "-n", NS, "prober", "--timestamps").stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            ts = datetime.fromisoformat(parts[0][:26].rstrip("Z") + "+00:00")
            out.append((ts.timestamp(), parts[1]))
    return out


def d5_smoke():
    start_prober()
    time.sleep(3)
    codes = [c for _, c in probe_samples()]
    if not codes or any(c != "200" for c in codes):
        raise RuntimeError(f"prober codes={codes[-10:]}")
    return f"HTTP 200 x{len(codes)} via Service from inside the cluster"


def serving_pods():
    """Pods that are Ready and not terminating; only these carry traffic."""
    pods = json.loads(kubectl("get", "pods", "-n", NS, "-l", "app=podinfo", "-o", "json", check=True).stdout)
    return [p["metadata"]["name"] for p in pods["items"]
            if not p["metadata"].get("deletionTimestamp")
            and any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", []))]


def crash_container(pod):
    """Kill the pod's container at the node level, like a process crash (always immediate)."""
    p = json.loads(kubectl("get", "pod", "-n", NS, pod, "-o", "json", check=True).stdout)
    node = p["spec"]["nodeName"]
    cid = p["status"]["containerStatuses"][0]["containerID"].split("//", 1)[1]
    run(["docker", "exec", node, "crictl", "stop", "--timeout", "0", cid], check=True)
    return p["status"]["containerStatuses"][0]["restartCount"]


def pod_kill(replicas, fault="pod-delete"):
    deadline = time.time() + 90
    while len(serving_pods()) != replicas or len(kubectl(
            "get", "pods", "-n", NS, "-l", "app=podinfo", "-o", "name").stdout.split()) != replicas:
        if time.time() > deadline:
            raise RuntimeError("deployment never settled before the kill")
        time.sleep(1)
    victim = serving_pods()[0]
    time.sleep(2)
    t_kill = time.time()
    if fault == "pod-delete":
        kubectl("delete", "pod", "-n", NS, victim, "--grace-period=0", "--force", "--wait=false")
    else:
        restarts_before = crash_container(victim)
    recovered = None
    seen_unready = False
    while time.time() - t_kill < 180:
        serving = serving_pods()
        if fault == "pod-delete":
            done = len(serving) == replicas and victim not in serving
        else:
            seen_unready = seen_unready or victim not in serving
            p = json.loads(kubectl("get", "pod", "-n", NS, victim, "-o", "json").stdout or "{}")
            restarted = p.get("status", {}).get("containerStatuses", [{}])[0].get("restartCount", 0) > restarts_before
            done = restarted and len(serving) == replicas
        if done:
            recovered = time.time() - t_kill
            break
        time.sleep(0.2)
    post_window = 5.0
    time.sleep(post_window + 1)
    samples = probe_samples()
    end = t_kill + (recovered or 180) + post_window
    window = [c for ts, c in samples if t_kill <= ts <= end]
    ok = sum(c == "200" for c in window)
    save(f"prober_{fault}_{replicas}replica.log",
         f"# kill at t=0, recovered at t={recovered}, window [0, {end - t_kill:.1f}]\n"
         + "\n".join(f"{ts - t_kill:+.2f} {c}" for ts, c in samples))
    if recovered is None:
        raise RuntimeError(f"deployment did not return to {replicas}/{replicas} ready within 180s")
    return recovered, ok, len(window)


def d6_pod_kill():
    recovered, ok, n = pod_kill(3)
    return (f"recovered 3/3 in {recovered:.1f}s; availability during recovery "
            f"{100.0 * ok / max(n, 1):.1f}% ({ok}/{n} probes)")


def d6_container_crash():
    recovered, ok, n = pod_kill(3, fault="container-crash")
    return (f"restarted, 3/3 serving in {recovered:.1f}s; availability "
            f"{100.0 * ok / max(n, 1):.1f}% ({ok}/{n} probes)")


def d6_negative_control():
    """With 1 replica, a container crash must cause observable downtime, otherwise the probe is blind."""
    kubectl("scale", "-n", NS, "deployment/podinfo", "--replicas=1", check=True)
    kubectl("rollout", "status", "-n", NS, "deployment/podinfo", "--timeout=120s", check=True, timeout=130)
    recovered, ok, n = pod_kill(1, fault="container-crash")
    if ok == n:
        raise RuntimeError(f"no downtime detected with 1 replica ({ok}/{n}); availability probe is not sensitive")
    return (f"restarted 1/1 in {recovered:.1f}s; availability {100.0 * ok / max(n, 1):.1f}% "
            f"({ok}/{n}) -> downtime correctly detected")


def main():
    os.makedirs(OUT, exist_ok=True)
    kubectl("delete", "namespace", NS, "--wait=true", timeout=180)
    stages = [
        ("D1 kubeconform (schema)", d1_kubeconform),
        ("D1 server dry-run + PSS restricted", d1_dry_run),
        ("D2 Kubescape (NSA, MITRE)", d2_kubescape),
        ("D2 Trivy config", d2_trivy),
        ("D3 kube-score", d3_kube_score),
        ("D3 Polaris", d3_polaris),
        ("D3 KubeLinter", d3_kube_linter),
        ("D5 deploy on kind", d5_deploy),
        ("D5 functional smoke test", d5_smoke),
        ("D6 pod-delete recovery (3 replicas)", d6_pod_kill),
        ("D6 container-crash (3 replicas)", d6_container_crash),
        ("D6 negative control (1 replica)", d6_negative_control),
    ]
    results = []
    for title, fn in stages:
        if title.startswith(("D5 functional", "D6")) and not results[7]:
            print(f"[SKIP] {title:38}         SKIPPED(not_deployed)")
            results.append(False)
            continue
        results.append(stage(title, fn))
    kubectl("delete", "namespace", NS, "--wait=false")
    print(f"\n{sum(results)}/{len(results)} stages passed. Raw outputs in {OUT}")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
