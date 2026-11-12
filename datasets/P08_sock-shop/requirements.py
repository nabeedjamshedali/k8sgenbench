"""D4 requirement checks for P08, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

FRONT_END = "weaveworksdemos/front-end"
CATALOGUE = "weaveworksdemos/catalogue"
CATALOGUE_DB = "weaveworksdemos/catalogue-db"
CARTS = "weaveworksdemos/carts"
ORDERS = "weaveworksdemos/orders"
PAYMENT = "weaveworksdemos/payment"
SHIPPING = "weaveworksdemos/shipping"
QUEUE_MASTER = "weaveworksdemos/queue-master"
USER = "weaveworksdemos/user"
USER_DB = "weaveworksdemos/user-db"
MONGO = "mongo"
RABBITMQ = "rabbitmq"


def service_at(c, rid, name, image, container_port, service_port, oracle=False):
    """A Service named `name` exposes `service_port` and routes it to `container_port` of `image`."""
    svc = c.m.named("Service", name)
    if not svc:
        return c.check(rid, False, f"no Service named {name}", oracle)
    ports = [p for s, p in c.m.exposed(image, container_port) if s is svc]
    ok = any(p.get("port") == service_port for p in ports)
    c.check(rid, ok, f"Service {name}:{service_port} -> {image}:{container_port}" if ok
            else f"Service {name} does not route port {service_port} to {image}:{container_port}", oracle)


def service_named_for(c, rid, name, image):
    """A Service named `name` selects the component running `image` (any port)."""
    svc = c.m.named("Service", name)
    ok = bool(svc) and c.m.routes_any_port(svc, image)
    c.check(rid, ok, f"Service {name} selects {image}" if ok
            else (f"Service {name} does not select {image}" if svc else f"no Service named {name}"))


def mongo_service(c, rid, name):
    """carts-db and orders-db both run the mongo image; the named Service must route 27017 to a mongo workload."""
    service_at(c, rid, name, MONGO, 27017, 27017)


def root_password_option(c, rid):
    found = []
    for w, ct in c.m.workloads_with_image(CATALOGUE_DB):
        vals = {n: c.m.env(w, ct, n) for n in ("MYSQL_ROOT_PASSWORD", "MYSQL_ALLOW_EMPTY_PASSWORD", "MYSQL_RANDOM_ROOT_PASSWORD")}
        found.append(any(v not in (None, "") for v in vals.values()))
    c.check(rid, bool(found) and all(found), f"root password option set in {sum(found)}/{len(found)} container(s)")


def rabbit_guest(c, rid):
    bad = []
    hits = c.m.workloads_with_image(RABBITMQ)
    for w, ct in hits:
        for n in ("RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS"):
            v = c.m.env(w, ct, n)
            if v not in (None, "guest"):
                bad.append(f"{n}={v}")
    c.check(rid, bool(hits) and not bad, "guest account kept" if hits and not bad
            else (", ".join(bad) or f"no workload runs {RABBITMQ}"))


def check(docs):
    c = Checker(docs)
    c.image_deployed("R01-front-end-deployed", FRONT_END)
    c.image_deployed("R02-catalogue-deployed", CATALOGUE)
    c.image_deployed("R03-catalogue-db-deployed", CATALOGUE_DB)
    c.image_deployed("R04-carts-deployed", CARTS)
    c.image_deployed("R05-orders-deployed", ORDERS)
    c.image_deployed("R06-payment-deployed", PAYMENT)
    c.image_deployed("R07-shipping-deployed", SHIPPING)
    c.image_deployed("R08-queue-master-deployed", QUEUE_MASTER)
    c.image_deployed("R09-rabbitmq-deployed", RABBITMQ)
    c.image_deployed("R10-user-deployed", USER)
    c.image_deployed("R11-user-db-deployed", USER_DB)
    mongo = c.m.workloads_with_image(MONGO)
    c.check("R12-two-mongo-databases", len(mongo) >= 2, f"{len(mongo)} mongo workload(s)")
    # oracle: the backends' container port 80 (each image's CMD `-port=80`) and the front-end's
    # 8079 (`PORT=8079` in its Dockerfile) are not in docs_bundle/ (README.md + docker-compose.yml
    # only; compose declares no container ports for them). The hostnames ARE in the bundle (compose
    # `hostname:`), so a port-agnostic scored counterpart follows each oracle check.
    for rid, name, image in [("R13", "catalogue", CATALOGUE), ("R15", "carts", CARTS), ("R17", "orders", ORDERS),
                             ("R19", "payment", PAYMENT), ("R20", "shipping", SHIPPING), ("R22", "user", USER)]:
        service_at(c, f"{rid}-{name}-hostname", name, image, 80, 80, oracle=True)
        service_named_for(c, f"{rid}b-{name}-hostname-service", name, image)
    service_at(c, "R14-catalogue-db-hostname", "catalogue-db", CATALOGUE_DB, 3306, 3306)
    mongo_service(c, "R16-carts-db-hostname", "carts-db")
    mongo_service(c, "R18-orders-db-hostname", "orders-db")
    service_at(c, "R21-rabbitmq-hostname", "rabbitmq", RABBITMQ, 5672, 5672)
    service_at(c, "R23-user-db-hostname", "user-db", USER_DB, 27017, 27017)
    c.env_equals("R24-catalogue-db-database", CATALOGUE_DB, "MYSQL_DATABASE", "socksdb")
    root_password_option(c, "R25-catalogue-db-root-password")
    rabbit_guest(c, "R26-rabbitmq-guest-account")
    c.external("R27-front-end-external", FRONT_END, 8079, oracle=True)
    ok, detail = c.m.externally_reachable_any_port(FRONT_END)
    c.check("R27b-front-end-external-any-port", ok, detail)
    return c.results
