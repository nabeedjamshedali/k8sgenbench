"""Helpers for D4 requirement checks. Components are located by container image, never by object name."""
import base64

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Pod", "Job", "CronJob"}
EXTERNAL_SERVICE_TYPES = {"NodePort", "LoadBalancer"}


class Component:
    """Selector usable anywhere an image is accepted: matches the exact image repository (if given)
    OR any workload identifiable by one of `tokens` (see Manifests.workloads_named_like). Use when the
    exact image path is not in docs_bundle/ but the component's name is, so that downstream checks
    test the documented fact rather than silently failing on an un-discoverable image path."""

    def __init__(self, *tokens, image=None):
        self.tokens = tokens
        self.image = image

    def __str__(self):
        return self.tokens[0]

    def rsplit(self, *a, **kw):
        return str(self).rsplit(*a, **kw)


class Manifests:
    def __init__(self, docs):
        self.docs = [d for d in docs if isinstance(d, dict) and d.get("kind")]

    def of_kind(self, *kinds):
        return [d for d in self.docs if d["kind"] in kinds]

    def named(self, kind, name):
        return next((d for d in self.of_kind(kind) if d.get("metadata", {}).get("name") == name), None)

    def pod_spec(self, w):
        spec = w.get("spec", {})
        if w["kind"] == "Pod":
            return spec
        if w["kind"] == "CronJob":
            return spec.get("jobTemplate", {}).get("spec", {}).get("template", {}).get("spec", {})
        return spec.get("template", {}).get("spec", {})

    def pod_labels(self, w):
        if w["kind"] == "Pod":
            return w.get("metadata", {}).get("labels", {}) or {}
        if w["kind"] == "CronJob":
            return w["spec"].get("jobTemplate", {}).get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}) or {}
        return w.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}) or {}

    def containers(self, w, init=False):
        ps = self.pod_spec(w)
        return list(ps.get("containers", []) or []) + (list(ps.get("initContainers", []) or []) if init else [])

    def workloads_with_image(self, image):
        """Workloads with a container whose image repository matches `image` (tag and registry prefix ignored)."""
        if isinstance(image, Component):
            hits = self.workloads_with_image(image.image) if image.image else []
            for t in image.tokens:
                hits += [h for h in self.workloads_named_like(t) if not any(h[0] is x[0] and h[1] is x[1] for x in hits)]
            return hits
        want = repo(image)
        return [(w, c) for w in self.of_kind(*WORKLOAD_KINDS) for c in self.containers(w)
                if repo(c.get("image", "")) == want]

    def workloads_named_like(self, token):
        """Workloads identifiable as `token` by workload name, container name, or image repo
        basename (ignoring the leading path/registry) -- used when the project's own exact
        registry path is NOT recoverable from docs_bundle/ (e.g. only per-service Dockerfiles are
        bundled, with no final push-image declaration), but the canonical service name itself IS
        (e.g. a Dockerfile literally named `<token>.Dockerfile`). This is a fairer, still-real
        structural-presence check in that situation: it does not credit a model for guessing an
        un-discoverable fact, but it does require an actual workload recognisable as that service.
        """
        want = token.lower()
        hits = []
        for w in self.of_kind(*WORKLOAD_KINDS):
            wname = (w.get("metadata", {}).get("name") or "").lower()
            for c in self.containers(w):
                cname = (c.get("name") or "").lower()
                img_base = repo(c.get("image", "")).rsplit("/", 1)[-1].lower()
                if want in (wname, cname, img_base):
                    hits.append((w, c))
        return hits

    def services_for(self, w):
        labels = self.pod_labels(w)
        ns = w.get("metadata", {}).get("namespace")
        out = []
        for s in self.of_kind("Service"):
            sel = s.get("spec", {}).get("selector") or {}
            sns = s.get("metadata", {}).get("namespace")
            if ns and sns and ns != sns:
                continue
            if sel and all(labels.get(k) == v for k, v in sel.items()):
                out.append(s)
        return out

    def container_port_names(self, c):
        return {p.get("name"): p.get("containerPort") for p in c.get("ports", []) or [] if p.get("name")}

    def service_targets(self, svc, w, container_port):
        """Service ports on `svc` that route to `container_port` of the pods of `w`."""
        names = {}
        for c in self.containers(w):
            names.update(self.container_port_names(c))
        hits = []
        for p in svc.get("spec", {}).get("ports", []) or []:
            tp = p.get("targetPort", p.get("port"))
            if isinstance(tp, str):
                tp = names.get(tp)
            if tp == container_port:
                hits.append(p)
        return hits

    def exposed(self, image, container_port):
        """(service, port) pairs routing to `container_port` of the component running `image`."""
        return [(s, p) for w, _ in self.workloads_with_image(image) for s in self.services_for(w)
                for p in self.service_targets(s, w, container_port)]

    def externally_reachable(self, image, container_port):
        for s, _ in self.exposed(image, container_port):
            if s["spec"].get("type", "ClusterIP") in EXTERNAL_SERVICE_TYPES:
                return True, f"Service {s['metadata']['name']} type {s['spec']['type']}"
        svc_names = {s["metadata"]["name"]: {p.get("port") for p in s["spec"].get("ports", [])}
                     for s, _ in self.exposed(image, container_port)}
        for ing in self.of_kind("Ingress"):
            for b in ingress_backends(ing):
                port = b.get("port", {}).get("number")
                if b.get("name") in svc_names and (port is None or port in svc_names[b["name"]]):
                    return True, f"Ingress {ing['metadata']['name']} -> {b['name']}"
        for r in self.of_kind("HTTPRoute"):
            for rule in r.get("spec", {}).get("rules", []) or []:
                for b in rule.get("backendRefs", []) or []:
                    if b.get("name") in svc_names:
                        return True, f"HTTPRoute {r['metadata']['name']} -> {b['name']}"
        return False, "no NodePort/LoadBalancer Service, Ingress or HTTPRoute routes to it"

    def externally_reachable_any_port(self, image):
        """Like externally_reachable, but over every Service selecting the component, whatever port."""
        svcs = {id(s): s for w, _ in self.workloads_with_image(image) for s in self.services_for(w)}
        for s in svcs.values():
            if s["spec"].get("type", "ClusterIP") in EXTERNAL_SERVICE_TYPES:
                return True, f"Service {s['metadata']['name']} type {s['spec']['type']}"
        names = {s["metadata"]["name"] for s in svcs.values()}
        for ing in self.of_kind("Ingress"):
            if any(b.get("name") in names for b in ingress_backends(ing)):
                return True, f"Ingress {ing['metadata']['name']}"
        for r in self.of_kind("HTTPRoute"):
            if any(b.get("name") in names for rule in r.get("spec", {}).get("rules", []) or []
                   for b in rule.get("backendRefs", []) or []):
                return True, f"HTTPRoute {r['metadata']['name']}"
        return False, "no NodePort/LoadBalancer Service, Ingress or HTTPRoute routes to it"

    def routes_any_port(self, svc, image):
        """True if Service `svc` selects a workload running `image` (any port)."""
        return any(svc is s for w, _ in self.workloads_with_image(image) for s in self.services_for(w))

    def env(self, w, c, name):
        """Resolved value of env var `name` in container `c` of workload `w`; None if unset, '?' if unresolvable."""
        for e in c.get("env", []) or []:
            if e.get("name") != name:
                continue
            if "value" in e:
                return str(e["value"])
            ref = e.get("valueFrom", {})
            if "secretKeyRef" in ref:
                return self.secret_value(ref["secretKeyRef"]["name"], ref["secretKeyRef"]["key"])
            if "configMapKeyRef" in ref:
                return self.configmap_value(ref["configMapKeyRef"]["name"], ref["configMapKeyRef"]["key"])
            return "?"
        for src in c.get("envFrom", []) or []:
            prefix = src.get("prefix", "")
            if not name.startswith(prefix):
                continue
            key = name[len(prefix):]
            if "secretRef" in src:
                v = self.secret_value(src["secretRef"]["name"], key)
            elif "configMapRef" in src:
                v = self.configmap_value(src["configMapRef"]["name"], key)
            else:
                v = None
            if v is not None:
                return v
        return None

    def secret_value(self, name, key):
        s = self.named("Secret", name)
        if not s:
            return "?"
        if key in (s.get("stringData") or {}):
            return str(s["stringData"][key])
        if key in (s.get("data") or {}):
            try:
                return base64.b64decode(s["data"][key]).decode()
            except Exception:
                return "?"
        return None

    def configmap_value(self, name, key):
        cm = self.named("ConfigMap", name)
        if not cm:
            return "?"
        v = (cm.get("data") or {}).get(key)
        return None if v is None else str(v)

    def mounts_persistent(self, w, c, path):
        """True if `path` in container `c` is backed by a PVC or a volumeClaimTemplate."""
        mount = next((m for m in c.get("volumeMounts", []) or [] if m.get("mountPath", "").rstrip("/") == path.rstrip("/")), None)
        if not mount:
            return False, f"nothing mounted at {path}"
        vname = mount.get("name")
        if w["kind"] == "StatefulSet":
            if any(t.get("metadata", {}).get("name") == vname for t in w["spec"].get("volumeClaimTemplates", []) or []):
                return True, "volumeClaimTemplate"
        vol = next((v for v in self.pod_spec(w).get("volumes", []) or [] if v.get("name") == vname), None)
        if vol and "persistentVolumeClaim" in vol:
            claim = vol["persistentVolumeClaim"].get("claimName")
            return (self.named("PersistentVolumeClaim", claim) is not None,
                    f"PVC {claim}" + ("" if self.named("PersistentVolumeClaim", claim) else " (not defined)"))
        if vol and "ephemeral" in vol:
            return False, "generic ephemeral volume"
        return False, f"volume type {sorted(k for k in (vol or {}) if k != 'name') or 'missing'}"


    def service_account(self, w):
        return self.pod_spec(w).get("serviceAccountName") or self.pod_spec(w).get("serviceAccount") or "default"

    def rbac_allows(self, w, verb, resource, group="", cluster_wide=False):
        """True if the workload's ServiceAccount is bound to a rule granting `verb` on `group/resource`.

        With cluster_wide=True only ClusterRoleBindings count.
        """
        sa = self.service_account(w)
        ns = w.get("metadata", {}).get("namespace")
        kinds = ("ClusterRoleBinding",) if cluster_wide else ("ClusterRoleBinding", "RoleBinding")
        for b in self.of_kind(*kinds):
            subjects = b.get("subjects", []) or []
            if not any(s.get("kind") == "ServiceAccount" and s.get("name") == sa
                       and (not ns or not s.get("namespace") or s.get("namespace") == ns) for s in subjects):
                continue
            ref = b.get("roleRef", {})
            role = self.named(ref.get("kind"), ref.get("name"))
            for rule in (role or {}).get("rules", []) or []:
                if (match(group, rule.get("apiGroups", [])) and match(resource, rule.get("resources", []))
                        and match(verb, rule.get("verbs", []))):
                    return True
        return False


def match(value, allowed):
    return "*" in (allowed or []) or value in (allowed or [])


def repo(image):
    """Image repository without tag/digest and without a leading registry host.

    Two images match if they name the same repository on any registry: a registry
    mirror (e.g. `docker.l5d.io/buoyantio/emojivoto-web`) matches the upstream name
    (`buoyantio/emojivoto-web`), while two different repositories on the same
    registry (e.g. `.../microservices-demo/frontend` vs `.../other/frontend`) do not.
    """
    image = image.split("@")[0]
    last = image.rsplit("/", 1)[-1]
    if ":" in last:
        image = image[: len(image) - len(last)] + last.split(":")[0]
    parts = image.split("/")
    if len(parts) > 1 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        parts = parts[1:]
    elif len(parts) == 1:
        parts = ["library"] + parts  # docker.io/library/<image>, e.g. "mysql"
    return "/".join(parts)


def ingress_backends(ing):
    spec = ing.get("spec", {})
    if spec.get("defaultBackend", {}).get("service"):
        yield spec["defaultBackend"]["service"]
    for rule in spec.get("rules", []) or []:
        for p in rule.get("http", {}).get("paths", []) or []:
            if p.get("backend", {}).get("service"):
                yield p["backend"]["service"]


class Checker:
    """Collects requirement results as (id, passed, detail)."""

    def __init__(self, docs):
        self.m = Manifests(docs)
        self.results = []

    def check(self, rid, passed, detail="", oracle=False):
        """`oracle=True` marks a check whose fact is NOT recoverable from docs_bundle/ (e.g. an
        exact hostname or env var name that exists only in application source code). Such checks
        still run, for diagnostic interest, but are excluded from the main D4 score: a model was
        never given that fact, so it would be unfair to grade it on guessing it correctly.
        """
        self.results.append({"id": rid, "passed": bool(passed), "detail": detail, "oracle": oracle})

    def image_deployed(self, rid, image, oracle=False):
        hits = self.m.workloads_with_image(image)
        self.check(rid, hits, f"{len(hits)} workload(s)" if hits else f"no workload runs {image}", oracle)

    def component_present(self, rid, token, oracle=False):
        """Like image_deployed, but matches by service-name token (see workloads_named_like) rather
        than an exact image repository. Use when the project's own exact image path isn't
        recoverable from docs_bundle/, but the service's canonical name is."""
        hits = self.m.workloads_named_like(token)
        self.check(rid, hits, f"{len(hits)} workload(s)" if hits else f"no workload identifiable as '{token}'", oracle)

    def service_named(self, rid, name, image, container_port, oracle=False):
        svc = self.m.named("Service", name)
        if not svc:
            return self.check(rid, False, f"no Service named {name}", oracle)
        ok = any(svc is s for s, _ in self.m.exposed(image, container_port))
        self.check(rid, ok, f"Service {name} routes to {image}:{container_port}" if ok
                   else f"Service {name} does not route to {image}:{container_port}", oracle)

    def exposed(self, rid, image, container_port, oracle=False):
        hits = self.m.exposed(image, container_port)
        self.check(rid, hits, f"via Service {hits[0][0]['metadata']['name']}" if hits
                   else f"no Service routes to {image}:{container_port}", oracle)

    def external(self, rid, image, container_port, oracle=False):
        ok, detail = self.m.externally_reachable(image, container_port)
        self.check(rid, ok, detail, oracle)

    def env_equals(self, rid, image, name, expected, oracle=False):
        found = [self.m.env(w, c, name) for w, c in self.m.workloads_with_image(image)]
        ok = bool(found) and all(v == expected for v in found)
        self.check(rid, ok, f"{name}={found}", oracle)

    def env_set(self, rid, image, name, oracle=False):
        found = [self.m.env(w, c, name) for w, c in self.m.workloads_with_image(image)]
        ok = bool(found) and all(v not in (None, "") for v in found)
        self.check(rid, ok, f"{name} {'set' if ok else 'missing'} in {len(found)} container(s)", oracle)

    def rbac(self, rid, image, verbs, resources, group="", cluster_wide=False, oracle=False):
        hits = self.m.workloads_with_image(image)
        missing = [f"{v} {group + '/' if group else ''}{r}" for w, _ in hits[:1] for r in resources for v in verbs
                   if not self.m.rbac_allows(w, v, r, group, cluster_wide)]
        ok = bool(hits) and not missing
        self.check(rid, ok, "granted" if ok else (f"missing: {', '.join(missing)}" if hits else f"no workload runs {image}"), oracle)

    def persistent(self, rid, image, path, oracle=False):
        res = [self.m.mounts_persistent(w, c, path) for w, c in self.m.workloads_with_image(image)]
        ok = bool(res) and all(r[0] for r in res)
        self.check(rid, ok, "; ".join(r[1] for r in res) or f"no workload runs {image}", oracle)
