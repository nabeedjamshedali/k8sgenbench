"""(Re)create the evaluation cluster: kind 1 control-plane + 3 workers, plus a local registry mirror.

Every node's containerd tries http://k8sgen-registry:5000 first for ANY registry host and falls
back to the upstream registry on a miss. The evaluation pushes each image a config references into
the mirror before deploying it, so time-to-Ready never depends on network speed and kubelet pulls
(including imagePullPolicy: Always) are served locally.

Usage: python tools/setup_cluster.py [--recreate]
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.join(HERE, "bin", "kind.exe")
CLUSTER = "k8sgen"
REGISTRY = "k8sgen-registry"
REGISTRY_PORT = 5001  # host-side port; nodes reach it as k8sgen-registry:5000 on the kind network
REGISTRY_IMAGE = "registry:2.8.3"

HOSTS_TOML = f'[host."http://{REGISTRY}:5000"]\n  capabilities = ["pull", "resolve"]\n'

# kind's containerd runs with LimitNOFILE=infinity, so containers inherit an open-files limit of ~1e9.
# Old MySQL/Mongo builds size internal tables from that limit (sock-shop's catalogue-db `mysqld --help`
# grew past 9 GB in 20 s and took the Docker engine down). Cap it at Docker's own default, 1048576, so the
# runtime matches a stock container host; it applies identically to every config.
NOFILE_DROPIN = "[Service]\nLimitNOFILE=1048576\n"


def run(args, check=True, **kw):
    print("+", " ".join(args))
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore", **kw)
    if check and r.returncode:
        sys.exit(f"failed: {r.stderr or r.stdout}")
    return r


def main():
    if "--recreate" in sys.argv:
        run([KIND, "delete", "cluster", "--name", CLUSTER], check=False)
    if run(["docker", "inspect", REGISTRY], check=False).returncode:
        run(["docker", "run", "-d", "--restart=always", "--name", REGISTRY,
             "-p", f"127.0.0.1:{REGISTRY_PORT}:5000", REGISTRY_IMAGE])
    clusters = run([KIND, "get", "clusters"]).stdout.split()
    if CLUSTER not in clusters:
        run([KIND, "create", "cluster", "--config", os.path.join(HERE, "kind-cluster.yaml"), "--wait", "180s"],
            timeout=900)
    run(["docker", "network", "connect", "kind", REGISTRY], check=False)
    nodes = run([KIND, "get", "nodes", "--name", CLUSTER]).stdout.split()
    for node in nodes:
        run(["docker", "exec", node, "mkdir", "-p", "/etc/containerd/certs.d/_default"])
        run(["docker", "exec", "-i", node, "sh", "-c", "cat > /etc/containerd/certs.d/_default/hosts.toml"],
            input=HOSTS_TOML)
        run(["docker", "exec", node, "mkdir", "-p", "/etc/systemd/system/containerd.service.d"])
        run(["docker", "exec", "-i", node, "sh", "-c", "cat > /etc/systemd/system/containerd.service.d/10-nofile.conf"],
            input=NOFILE_DROPIN)
        run(["docker", "exec", node, "sh", "-c", "systemctl daemon-reload && systemctl restart containerd"])
    run([os.path.join(HERE, "bin", "kubectl.exe"), "wait", "--for=condition=Ready", "nodes", "--all", "--timeout=180s"],
        timeout=240)
    print(f"cluster {CLUSTER}: {len(nodes)} nodes; mirror {REGISTRY} (host port {REGISTRY_PORT})")


if __name__ == "__main__":
    main()
