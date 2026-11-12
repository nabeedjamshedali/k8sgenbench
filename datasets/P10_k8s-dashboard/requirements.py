"""D4 requirement checks for P10, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker, Component

DASHBOARD = "kubernetesui/dashboard"
SCRAPER = "kubernetesui/metrics-scraper"
SCRAPER_SVC = "dashboard-metrics-scraper"
CSRF = "kubernetes-dashboard-csrf"
KEY_HOLDER = "kubernetes-dashboard-key-holder"
SETTINGS = "kubernetes-dashboard-settings"
# oracle note: the image paths above are NOT in docs_bundle/ (README.md, dashboard-arguments.md,
# integrations.md never name an image). The component names ARE: "kubernetes-dashboard" (README
# proxy URL) and "dashboard-metrics-scraper" (integrations.md). Downstream checks therefore select
# workloads by Component (exact image OR documented name), so they test the documented fact rather
# than failing on an un-discoverable image path.
DASH_C = Component("kubernetes-dashboard", "dashboard", image=DASHBOARD)
SCR_C = Component("dashboard-metrics-scraper", "metrics-scraper", image=SCRAPER)


def argv(c):
    return [str(a) for a in (c.get("command") or []) + (c.get("args") or [])]


def flag(c, name):
    """Value of --name=value or --name value; True for a bare boolean flag; None if absent."""
    a = argv(c)
    for i, x in enumerate(a):
        if x == f"--{name}":
            nxt = a[i + 1] if i + 1 < len(a) else None
            return nxt if nxt is not None and not nxt.startswith("-") else True
        if x.startswith(f"--{name}="):
            return x.split("=", 1)[1]
    return None


def env_entry(c, name):
    return next((e for e in c.get("env", []) or [] if e.get("name") == name), None)


def ns_of(o):
    return (o.get("metadata") or {}).get("namespace")


def effective_namespace(c):
    """Namespace the dashboard will use for its state: ('fieldref', None) or ('value', ns)."""
    v = flag(c, "namespace")
    if isinstance(v, str):
        return "value", v
    e = env_entry(c, "POD_NAMESPACE")
    if e:
        if (e.get("valueFrom") or {}).get("fieldRef", {}).get("fieldPath") == "metadata.namespace":
            return "fieldref", None
        if "value" in e:
            return "value", str(e["value"])
    return "value", "kube-system"


def same_ns(a, b):
    return (a or "default") == (b or "default")


def check(docs):
    c = Checker(docs)
    m = c.m
    c.image_deployed("R01-dashboard-deployed", DASHBOARD, oracle=True)
    c.image_deployed("R02-scraper-deployed", SCRAPER, oracle=True)
    c.image_deployed("R01b-dashboard-component-present", DASH_C)
    c.image_deployed("R02b-scraper-component-present", SCR_C)
    c.exposed("R03-dashboard-https-port-in-cluster", DASH_C, 8443)

    dash = m.workloads_with_image(DASH_C)
    scr = m.workloads_with_image(SCR_C)
    dash_ns = ns_of(dash[0][0]) if dash else None

    tls = [flag(ct, "auto-generate-certificates") not in (None, "false")
           or (flag(ct, "tls-cert-file") not in (None, True) and flag(ct, "tls-key-file") not in (None, True))
           for _, ct in dash]
    c.check("R04-dashboard-serves-https", dash and all(tls),
            "certificate flags present" if dash and all(tls) else "no --auto-generate-certificates or --tls-cert-file/--tls-key-file")

    res = []
    for w, ct in dash:
        kind, v = effective_namespace(ct)
        if kind == "fieldref":
            res.append((True, "POD_NAMESPACE from metadata.namespace"))
        elif ns_of(w) is None:
            res.append((False, f"dashboard uses namespace {v}, workload namespace not set in manifest"))
        else:
            res.append((v == ns_of(w), f"dashboard uses namespace {v}, runs in {ns_of(w)}"))
    c.check("R05-dashboard-namespace-setting", res and all(r[0] for r in res), "; ".join(r[1] for r in res) or "no dashboard")

    def obj_in_ns(kind, name):
        return any(o.get("metadata", {}).get("name") == name and same_ns(ns_of(o), dash_ns) for o in m.of_kind(kind))

    # oracle: the CSRF Secret's existence and exact name are internal implementation details of
    # kubernetes-dashboard's Go source, never mentioned in README.md/dashboard-arguments.md/integrations.md.
    c.check("R06-csrf-secret-exists", dash and obj_in_ns("Secret", CSRF),
            f"Secret {CSRF} {'present' if obj_in_ns('Secret', CSRF) else 'missing'} in dashboard namespace",
            oracle=True)

    # oracle (R07-R09): that the dashboard reaches the scraper via a Service named exactly
    # dashboard-metrics-scraper with a single unnamed port, that the scraper listens on 8000, and that
    # it must run cluster-wide all come from Go source (sidecar/restclient.go, scraper:server.go) and
    # the unbundled scraper README; docs_bundle/ only links the scraper repo by name.
    c.service_named("R07-scraper-service-name", SCRAPER_SVC, SCR_C, 8000, oracle=True)
    svc = m.named("Service", SCRAPER_SVC)
    ok, detail = False, f"no Service named {SCRAPER_SVC}"
    if svc:
        hits = [p for w, _ in scr for p in m.service_targets(svc, w, 8000)]
        ports = svc.get("spec", {}).get("ports", []) or []
        unnamed = any(not p.get("name") for p in hits) and len([p for p in ports if not p.get("name")]) == 1
        ok = same_ns(ns_of(svc), dash_ns) and unnamed
        detail = f"namespace {ns_of(svc)} vs dashboard {dash_ns}; unnamed port to 8000: {unnamed}"
    c.check("R08-scraper-service-same-ns-unnamed-port", ok, detail, oracle=True)

    scoped = [env_entry(ct, "POD_NAMESPACE") is not None or flag(ct, "namespace") is not None or "-n" in argv(ct)
              for _, ct in scr]
    c.check("R09-scraper-cluster-wide", scr and not any(scoped),
            "scraper not namespace-scoped" if scr and not any(scoped) else "POD_NAMESPACE or --namespace set on scraper",
            oracle=True)

    wr = []
    for w, ct in scr:
        db = flag(ct, "db-file")
        d = os.path.dirname(db) if isinstance(db, str) else "/tmp"
        ro = (ct.get("securityContext") or {}).get("readOnlyRootFilesystem") is True
        mounted = any(vm.get("mountPath", "").rstrip("/") == d.rstrip("/") for vm in ct.get("volumeMounts", []) or [])
        wr.append(not ro or mounted)
    # oracle: the --db-file flag and its default /tmp path are documented only in
    # dashboard-metrics-scraper's own repo, which is not part of docs_bundle/.
    c.check("R10-scraper-db-writable", wr and all(wr), "db directory writable" if wr and all(wr) else "read-only root filesystem without a volume for the db directory",
            oracle=True)

    # oracle: that the dashboard needs get/update on Secrets (for its own CSRF token and
    # encryption key) is internal to its Go source; docs_bundle/ never mentions "csrf" or a
    # key-holder Secret.
    c.rbac("R11-dashboard-csrf-secret-get-update", DASH_C, ["get", "update"], ["secrets"], oracle=True)

    def get_and_create_or_exists(rid, resource, kind, name, oracle=False):
        if not dash:
            return c.check(rid, False, f"no workload runs {DASH_C}", oracle)
        w = dash[0][0]
        get = m.rbac_allows(w, "get", resource)
        create = m.rbac_allows(w, "create", resource)
        exists = obj_in_ns(kind, name)
        c.check(rid, get and (create or exists), f"get={get} create={create} {kind} {name} pre-created={exists}", oracle)

    # oracle: the key-holder Secret and settings ConfigMap names/roles are undocumented outside
    # kubernetes-dashboard's own source.
    get_and_create_or_exists("R12-dashboard-key-holder", "secrets", "Secret", KEY_HOLDER, oracle=True)
    get_and_create_or_exists("R13-dashboard-settings-configmap", "configmaps", "ConfigMap", SETTINGS, oracle=True)
    # oracle: that the dashboard proxies through the API server's services/proxy subresource is
    # not stated anywhere in docs_bundle/.
    c.rbac("R14-dashboard-service-proxy", DASH_C, ["get"], ["services/proxy"], oracle=True)
    c.rbac("R15-scraper-metrics-api", SCR_C, ["list"], ["nodes", "pods"], group="metrics.k8s.io", cluster_wide=True)

    # port-agnostic: the scraper port (8000) is not in docs_bundle/ (see R07-R09 note).
    ext, detail = m.externally_reachable_any_port(SCR_C)
    c.check("R16-scraper-internal", scr and not ext, detail)
    return c.results


if __name__ == "__main__":
    import yaml
    docs = []
    for f in sys.argv[1:]:
        with open(f, encoding="utf-8") as fh:
            docs += [d for d in yaml.safe_load_all(fh) if d]
    for r in check(docs):
        print(("PASS" if r["passed"] else "FAIL"), r["id"], "-", r["detail"])
