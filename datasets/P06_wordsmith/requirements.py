"""D4 requirement checks for P06, derived from fact_sheet.md only."""
import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

WEB = "dockersamples/wordsmith-web"
API = "dockersamples/wordsmith-api"
DB = "postgres"
INITDB = "/docker-entrypoint-initdb.d"
SEED_MARKER = "INSERT INTO nouns"


def reachable_at(c, rid, name, image, port):
    """Service `name` routes to image:port and clients connecting to name:port reach it (Service port or headless)."""
    svc = c.m.named("Service", name)
    if not svc:
        return c.check(rid, False, f"no Service named {name}")
    ports = [p for s, p in c.m.exposed(image, port) if s is svc]
    if not ports:
        return c.check(rid, False, f"Service {name} does not route to {image}:{port}")
    headless = svc["spec"].get("clusterIP") == "None"
    ok = headless or any(p.get("port") == port for p in ports)
    c.check(rid, ok, f"Service {name} {'headless' if headless else 'port ' + str([p.get('port') for p in ports])}")


def db_passwordless(c, rid):
    # oracle: the api service connects with an empty password; that fact lives only in
    # api/src/main/java/Main.java's JDBC connection string, not in docs_bundle/.
    found = []
    for w, ct in c.m.workloads_with_image(DB):
        pw = c.m.env(w, ct, "POSTGRES_PASSWORD")
        auth = c.m.env(w, ct, "POSTGRES_HOST_AUTH_METHOD")
        found.append(pw in (None, "") or auth == "trust")
    c.check(rid, bool(found) and all(found), f"{found}", oracle=True)


def db_seeded(c, rid):
    # oracle: the exact seed marker "INSERT INTO nouns" comes from db/words.sql, which is not
    # part of docs_bundle/ (only the mount path is visible via docker-compose.yml's volumes line).
    seed_in = [d for d in c.m.docs if SEED_MARKER in yaml.safe_dump(d, allow_unicode=True)]
    mounted = any(any(m.get("mountPath", "").rstrip("/") == INITDB for m in ct.get("volumeMounts", []) or [])
                  for _, ct in c.m.workloads_with_image(DB))
    runner = any(d["kind"] in ("Job", "Pod", "Deployment", "StatefulSet") for d in seed_in)
    ok = bool(seed_in) and (mounted or runner)
    c.check(rid, ok, f"seed in {[d['kind'] + '/' + d['metadata'].get('name', '') for d in seed_in]}, "
                     f"{INITDB} mounted={mounted}", oracle=True)


def internal(c, rid, image, port):
    ok, detail = c.m.externally_reachable(image, port)
    c.check(rid, not ok, "internal" if not ok else f"exposed: {detail}")


def check(docs):
    c = Checker(docs)
    c.image_deployed("R01-web-deployed", WEB)
    c.image_deployed("R02-api-deployed", API)
    c.image_deployed("R03-db-deployed", DB)
    reachable_at(c, "R04-api-hostname", "api", API, 8080)
    reachable_at(c, "R05-db-hostname", "db", DB, 5432)
    db_passwordless(c, "R06-db-passwordless")
    db_seeded(c, "R07-db-seeded")
    c.external("R08-web-external", WEB, 80)
    internal(c, "R09-api-internal", API, 8080)
    internal(c, "R10-db-internal", DB, 5432)
    return c.results
