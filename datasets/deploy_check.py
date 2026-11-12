"""Deploy a candidate's human-written manifests on the kind cluster and report whether every workload becomes Ready.

Usage: python datasets/deploy_check.py <candidate> [--keep]
"""
import json
import os
import subprocess
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "common"))
CACHE = os.path.join(HERE, ".cache")
BIN = os.path.join(HERE, "..", "tools", "bin")
CTX = "kind-k8sgen"
CLUSTER = "k8sgen"
WORKLOADS = {"Deployment", "StatefulSet", "DaemonSet"}
PROTECTED_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease", "default", "local-path-storage"}

TARGETS = {
    "cassandra": ["content/en/examples/application/cassandra/cassandra-service.yaml",
                  "content/en/examples/application/cassandra/cassandra-statefulset.yaml"],
    "guestbook": ["web/guestbook/redis-master-deployment.yaml", "web/guestbook/redis-master-service.yaml",
                  "web/guestbook/redis-replica-deployment.yaml", "web/guestbook/redis-replica-service.yaml",
                  "web/guestbook/frontend-deployment.yaml", "web/guestbook/frontend-service.yaml"],
    "n8n": ["kubernetes/" + f for f in ("namespace.yaml", "postgres-configmap.yaml", "postgres-secret.yaml",
            "postgres-claim0-persistentvolumeclaim.yaml", "postgres-deployment.yaml", "postgres-service.yaml",
            "n8n-claim0-persistentvolumeclaim.yaml", "n8n-deployment.yaml", "n8n-service.yaml")],
    "kube-state-metrics": ["examples/standard"],
    "headlamp": ["kubernetes-headlamp.yaml"],
    "grafana": ["grafana.yaml"],
    "keycloak": ["kubernetes/keycloak.yaml"],
    "voting-app": ["k8s-specifications"],
    "wordsmith": ["."],
    "emojivoto": ["kustomize/deployment"],
    "bookinfo": ["samples/bookinfo/platform/kube/bookinfo.yaml"],
    "dashboard": ["aio/deploy/recommended.yaml"],
    "online-boutique": ["release/kubernetes-manifests.yaml"],
    "sock-shop": ["deploy/kubernetes/complete-demo.yaml"],
    "teastore": ["examples/kubernetes/teastore-clusterip.yaml"],
    "podinfo": ["kustomize"],
    "zabbix": ["kubernetes.yaml"],
}

SETUP = {
    # n8n-deployment.yaml declares an "n8n-secret" volume (unused by any volumeMount) that no
    # manifest in the repo creates; without it the pod cannot be scheduled. Documented in P02's report.
    "n8n": [{"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "n8n-secret", "namespace": "n8n"},
             "stringData": {}}],
}


def run(args, timeout=900, input=None):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore",
                          timeout=timeout, input=input)


def kubectl(*args, **kw):
    return run([os.path.join(BIN, "kubectl.exe"), "--context", CTX, *args], **kw)


def render(name):
    docs = []
    for rel in TARGETS[name]:
        path = os.path.join(CACHE, name, rel)
        if os.path.isdir(path) and any(os.path.exists(os.path.join(path, k))
                                       for k in ("kustomization.yaml", "kustomization.yml")):
            text = kubectl("kustomize", path).stdout
        elif os.path.isdir(path):
            text = "\n---\n".join(open(os.path.join(path, f), encoding="utf-8").read()
                                  for f in sorted(os.listdir(path)) if f.endswith((".yaml", ".yml")))
        else:
            text = open(path, encoding="utf-8").read()
        docs += [d for d in yaml.safe_load_all(text) if d]
    # SETUP objects are appended, not prepended: some (e.g. n8n's Secret) target a namespace
    # that a preceding object in `docs` creates, and kubectl apply processes documents in order.
    return docs + SETUP.get(name, [])


def images(docs):
    found = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("containers", "initContainers") and isinstance(v, list):
                    found.update(c["image"] for c in v if "image" in c)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(docs)
    return sorted(found)


def on_node(img):
    ref = img if "/" in img.split(":")[0] else "docker.io/library/" + img
    ref = ref if ":" in ref.rsplit("/", 1)[-1] or "@" in ref else ref + ":latest"
    if not ref.split("/")[0].count(".") and not ref.startswith("localhost"):
        ref = "docker.io/" + ref
    return run(["docker", "exec", f"{CLUSTER}-worker", "crictl", "inspecti", ref]).returncode == 0


def preload(img):
    if on_node(img):
        return None
    if run(["docker", "pull", "--platform", "linux/amd64", img], timeout=1800).returncode:
        return f"pull failed: {img}"
    tar = os.path.join(CACHE, "img.tar")
    run(["docker", "save", "--platform", "linux/amd64", "-o", tar, img], timeout=1800)
    r = run([os.path.join(BIN, "kind.exe"), "load", "image-archive", tar, "--name", CLUSTER], timeout=1800)
    os.remove(tar)
    return f"load failed: {img}: {r.stderr[-200:]}" if r.returncode else None


def main():
    name, keep = sys.argv[1], "--keep" in sys.argv
    smoke_file = sys.argv[sys.argv.index("--smoke") + 1] if "--smoke" in sys.argv else None
    docs = render(name)
    ns = f"dc-{name}"
    kinds = {}
    for d in docs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    hard_ns = sorted({d["metadata"]["namespace"] for d in docs if d.get("metadata", {}).get("namespace")}
                     | {d["metadata"]["name"] for d in docs if d["kind"] == "Namespace"})
    imgs = images(docs) + (["curlimages/curl:8.11.1"] if smoke_file else [])
    print(f"{name}: {len(docs)} objects {kinds}")
    print(f"  images ({len(imgs)}): {', '.join(imgs)}")
    print(f"  hard-coded namespaces: {hard_ns or 'none'}")
    errors = [e for e in (preload(i) for i in imgs) if e]
    for e in errors:
        print("  " + e)

    kubectl("create", "namespace", ns)
    t0 = time.time()
    # `kubectl apply -n ns -f -` rejects any object that already sets its own metadata.namespace
    # (or a Namespace object, which is cluster-scoped) -- it only "defaults" the namespace for
    # objects that have none, it does not override one that's already set. So objects that hard-code
    # their own namespace must be applied without -n (letting them land in their own namespace,
    # which is why they're tracked separately as `hard_ns` targets below), and only the remainder
    # goes through -n ns.
    explicit = [d for d in docs if d["kind"] == "Namespace" or d.get("metadata", {}).get("namespace")]
    implicit = [d for d in docs if d not in explicit]
    errors = []
    if explicit:
        r = kubectl("apply", "-f", "-", input=yaml.safe_dump_all(explicit))
        if r.returncode:
            errors.append(r.stderr.strip())
    if implicit:
        r = kubectl("apply", "-n", ns, "-f", "-", input=yaml.safe_dump_all(implicit))
        if r.returncode:
            errors.append(r.stderr.strip())
    if errors:
        print("  apply errors:", "\n".join(errors)[-600:])
    targets = [ns] + hard_ns
    deadline = time.time() + 420
    while time.time() < deadline:
        status = []
        for n in targets:
            out = kubectl("get", "deploy,sts,ds", "-n", n, "-o", "json").stdout
            for it in json.loads(out or '{"items":[]}')["items"]:
                want = it["spec"].get("replicas", it["status"].get("desiredNumberScheduled", 1))
                ready = it["status"].get("readyReplicas", it["status"].get("numberReady", 0))
                status.append((f"{n}/{it['kind']}/{it['metadata']['name']}", ready, want))
        if status and all(r >= w for _, r, w in status):
            break
        time.sleep(5)
    elapsed = time.time() - t0
    ok = bool(status) and all(r >= w for _, r, w in status)
    print(f"  {'READY' if ok else 'NOT READY'} after {elapsed:.0f}s: {len(status)} workloads")
    for s, r_, w in status:
        if r_ < w:
            print(f"    {s}: {r_}/{w}")
    if not ok:
        for n in targets:
            pods = kubectl("get", "pods", "-n", n, "--no-headers").stdout.strip()
            if pods:
                print("   ", pods.replace("\n", "\n    "))
    if ok and smoke_file:
        from smoke import run_smoke
        results = run_smoke(json.load(open(smoke_file)), docs, ns, targets, kubectl)
        for r_ in results:
            print(f"  smoke {'PASS' if r_['passed'] else 'FAIL'} {r_['name']}: {r_['detail']}")
        ok = all(r_["passed"] for r_ in results)
    if not keep:
        # Never delete a namespace the manifest hard-codes if it is a cluster namespace we
        # don't own (e.g. kube-system): delete the individual objects we created instead.
        for d in docs:
            kind = d["kind"]
            name_ = d.get("metadata", {}).get("name")
            if not name_ or kind == "Namespace":
                continue
            ns_d = d.get("metadata", {}).get("namespace") or ns
            if kind.startswith("Cluster"):
                kubectl("delete", kind, name_, "--ignore-not-found")
            elif ns_d in PROTECTED_NAMESPACES:
                kubectl("delete", kind, name_, "-n", ns_d, "--ignore-not-found", "--wait=false")
        for n in targets:
            if n not in PROTECTED_NAMESPACES:
                kubectl("delete", "namespace", n, "--wait=false")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
