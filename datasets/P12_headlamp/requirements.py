"""D4 requirement checks for P12, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

HEADLAMP = "ghcr.io/headlamp-k8s/headlamp"
TRUE = {"", "true", "1", "t"}


def in_cluster_enabled(m, w, c):
    args = [str(a) for a in (c.get("command") or []) + (c.get("args") or [])]
    for a in args:
        flag, _, val = a.partition("=")
        if flag.lstrip("-") != "in-cluster":
            continue
        return val.strip().lower() in TRUE
    env = m.env(w, c, "HEADLAMP_CONFIG_IN_CLUSTER")
    return env is not None and env.strip().lower() in TRUE - {""}


def token_mounted(m, w):
    ps = m.pod_spec(w)
    if "automountServiceAccountToken" in ps:
        return ps["automountServiceAccountToken"] is not False
    ns = w.get("metadata", {}).get("namespace")
    for sa in m.of_kind("ServiceAccount"):
        if sa.get("metadata", {}).get("name") == m.service_account(w) and \
                (not ns or not sa["metadata"].get("namespace") or sa["metadata"]["namespace"] == ns):
            return sa.get("automountServiceAccountToken") is not False
    return True


def check(docs):
    c = Checker(docs)
    m = c.m
    hits = m.workloads_with_image(HEADLAMP)
    c.image_deployed("R01-headlamp-deployed", HEADLAMP)
    ok = bool(hits) and all(in_cluster_enabled(m, w, ct) for w, ct in hits)
    c.check("R02-in-cluster-mode", ok, "-in-cluster flag or HEADLAMP_CONFIG_IN_CLUSTER=true" if ok
            else "in-cluster mode not enabled")
    ok = bool(hits) and all(token_mounted(m, w) for w, _ in hits)
    # oracle: that in-cluster mode needs the pod's own ServiceAccount token mounted is a
    # client-go/Kubernetes-internals fact never stated in docs_bundle/ (which only discusses a
    # separate concept: a Service Account bearer token pasted into the Headlamp login UI).
    c.check("R03-sa-token-mounted", ok, "service-account token mounted" if ok
            else "automountServiceAccountToken is false", oracle=True)
    c.exposed("R04-ui-port", HEADLAMP, 4466)
    c.external("R05-ui-external", HEADLAMP, 4466)
    return c.results


if __name__ == "__main__":
    import glob
    import yaml
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "human")
    docs = []
    for f in sorted(glob.glob(os.path.join(d, "*.y*ml"))):
        with open(f, encoding="utf-8") as fh:
            docs += list(yaml.safe_load_all(fh))
    for r in check(docs):
        print(("PASS" if r["passed"] else "FAIL"), r["id"], "-", r["detail"])
