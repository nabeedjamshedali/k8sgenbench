"""D4 requirement checks for P09, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

PREFIX = "descartesresearch/teastore-"
REGISTRY = PREFIX + "registry"
DB = PREFIX + "db"
PERSISTENCE = PREFIX + "persistence"
AUTH = PREFIX + "auth"
IMAGE = PREFIX + "image"
RECOMMENDER = PREFIX + "recommender"
WEBUI = PREFIX + "webui"
SERVICES = [("persistence", PERSISTENCE), ("auth", AUTH), ("image", IMAGE),
            ("recommender", RECOMMENDER), ("webui", WEBUI)]


def resolves_to(m, host, image, container_port, service_port):
    """True if `host` (DNS name, possibly a pod-in-headless-service name) names a Service on `service_port`
    that routes to `container_port` of the component running `image`."""
    if not host or host == "?":
        return False
    labels = host.split(".")[:2]
    for svc, port in m.exposed(image, container_port):
        if svc["metadata"]["name"] in labels and str(port.get("port")) == str(service_port):
            return True
    return False


def raw_env(c, name):
    return next((e for e in c.get("env", []) or [] if e.get("name") == name), None)


def address_check(c, rid, image, var, target_image, target_port, port_var, default_port):
    m = c.m
    hits = m.workloads_with_image(image)
    if not hits:
        return c.check(rid, False, f"no workload runs {image}")
    bad = []
    for w, ct in hits:
        host = m.env(w, ct, var)
        port = m.env(w, ct, port_var) or default_port
        if not resolves_to(m, host, target_image, target_port, port):
            bad.append(f"{var}={host}, {port_var}={port}")
    c.check(rid, not bad, "; ".join(bad) or f"{var} reaches {target_image}:{target_port}")


def registered_address_check(c, rid, image):
    m = c.m
    hits = m.workloads_with_image(image)
    if not hits:
        return c.check(rid, False, f"no workload runs {image}")
    bad = []
    for w, ct in hits:
        port = m.env(w, ct, "SERVICE_PORT") or "8080"
        if (m.env(w, ct, "USE_POD_IP") or "").lower() == "true" and port == "8080":
            continue
        e = raw_env(ct, "HOST_NAME")
        if e and e.get("valueFrom", {}).get("fieldRef", {}).get("fieldPath") == "status.podIP" and port == "8080":
            continue
        host = m.env(w, ct, "HOST_NAME")
        if not resolves_to(m, host, image, 8080, port):
            bad.append(f"HOST_NAME={host}, SERVICE_PORT={port}, USE_POD_IP={m.env(w, ct, 'USE_POD_IP')}")
    c.check(rid, not bad, "; ".join(bad) or "registered address reachable")


def check(docs):
    c = Checker(docs)
    c.image_deployed("R01-registry-deployed", REGISTRY)
    c.image_deployed("R02-db-deployed", DB)
    c.image_deployed("R03-persistence-deployed", PERSISTENCE)
    c.image_deployed("R04-auth-deployed", AUTH)
    c.image_deployed("R05-image-deployed", IMAGE)
    c.image_deployed("R06-recommender-deployed", RECOMMENDER)
    c.image_deployed("R07-webui-deployed", WEBUI)
    for i, (name, image) in enumerate(SERVICES):
        address_check(c, f"R{8 + i:02d}-{name}-registry-host", image, "REGISTRY_HOST", REGISTRY, 8080,
                      "REGISTRY_PORT", "8080")
    for i, (name, image) in enumerate(SERVICES):
        registered_address_check(c, f"R{13 + i:02d}-{name}-registered-address", image)
    address_check(c, "R18-persistence-db-host", PERSISTENCE, "DB_HOST", DB, 3306, "DB_PORT", "3306")
    c.external("R19-webui-external", WEBUI, 8080)
    return c.results
