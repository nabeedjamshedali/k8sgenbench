"""Fetch candidate repositories into datasets/.cache with sparse checkouts and record the commit of each."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")

CANDIDATES = {
    "zabbix": ("https://github.com/zabbix/zabbix-docker", None, None),
    "cassandra": ("https://github.com/kubernetes/website", None, ["content/en/examples/application/cassandra"]),
    "guestbook": ("https://github.com/kubernetes/examples", None, ["web/guestbook", "guestbook"]),
    "n8n": ("https://github.com/n8n-io/n8n-hosting", None, ["kubernetes", "README.md", "docker-compose"]),
    "kube-state-metrics": ("https://github.com/kubernetes/kube-state-metrics", None, ["examples/standard", "README.md", "docs"]),
    "headlamp": ("https://github.com/kubernetes-sigs/headlamp", None, ["kubernetes-headlamp.yaml", "README.md", "docs/installation", "Dockerfile"]),
    "keycloak": ("https://github.com/keycloak/keycloak-quickstarts", None, ["kubernetes"]),
    "voting-app": ("https://github.com/dockersamples/example-voting-app", None, None),
    "wordsmith": ("https://github.com/dockersamples/wordsmith", None, None),
    "emojivoto": ("https://github.com/BuoyantIO/emojivoto", None, None),
    "bookinfo": ("https://github.com/istio/istio", None, ["samples/bookinfo"]),
    "dashboard": ("https://github.com/kubernetes/dashboard", "v2.7.0", ["aio", "README.md", "docs"]),
    "online-boutique": ("https://github.com/GoogleCloudPlatform/microservices-demo", None, ["release", "kubernetes-manifests", "src", "README.md", "docs"]),
    "sock-shop": ("https://github.com/microservices-demo/microservices-demo", None, ["deploy/kubernetes", "README.md", "internal-docs"]),
    "teastore": ("https://github.com/DescartesResearch/TeaStore", None, ["examples", "README.md", "GET_STARTED.md"]),
    "grafana": ("https://github.com/grafana/grafana", None, ["docs/sources/setup-grafana/installation/kubernetes", "conf/defaults.ini", "Dockerfile"]),
    "podinfo": ("https://github.com/stefanprodan/podinfo", None, ["kustomize", "deploy", "README.md"]),
}


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def fetch(name, url, ref, paths):
    dest = os.path.join(CACHE, name)
    if not os.path.isdir(dest):
        clone = ["clone", "--depth", "1", "--filter=blob:none"]
        if paths:
            clone.append("--sparse")
        if ref:
            clone += ["--branch", ref]
        git(*clone, url, dest)
        if paths:
            git("sparse-checkout", "set", "--no-cone", *paths, cwd=dest)
    return {"url": url, "ref": ref or git("rev-parse", "--abbrev-ref", "HEAD", cwd=dest),
            "commit": git("rev-parse", "HEAD", cwd=dest), "paths": paths}


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    lock_path = os.path.join(CACHE, "commits.json")
    lock = json.load(open(lock_path)) if os.path.exists(lock_path) else {}
    for name in sys.argv[1:] or CANDIDATES:
        try:
            lock[name] = fetch(name, *CANDIDATES[name])
            print(f"{name:16} {lock[name]['commit'][:12]}")
        except subprocess.CalledProcessError as e:
            print(f"{name:16} FAILED: {e.stderr.strip().splitlines()[-1]}")
    json.dump(lock, open(lock_path, "w"), indent=2)
