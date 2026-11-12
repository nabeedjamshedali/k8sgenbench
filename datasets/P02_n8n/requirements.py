"""D4 requirement checks for P02, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

N8N = "n8nio/n8n"
DB = "postgres"


def n8n_env(c, name):
    return [c.m.env(w, ct, name) for w, ct in c.m.workloads_with_image(N8N)]


def db_env(c, name):
    return [c.m.env(w, ct, name) for w, ct in c.m.workloads_with_image(DB)]


def check_default(c, rid, name, expected):
    """Passes if the variable equals `expected` or is unset (n8n's documented default is `expected`)."""
    found = n8n_env(c, name)
    ok = bool(found) and all(v in (None, expected) for v in found)
    c.check(rid, ok, f"{name}={found}")


def check_db_host(c, rid):
    found = n8n_env(c, "DB_POSTGRESDB_HOST")
    targets = {s["metadata"]["name"]: s.get("metadata", {}).get("namespace") for s, _ in c.m.exposed(DB, 5432)}
    ok = bool(found) and bool(targets)
    for v in found:
        if not v or v == "?":
            ok = False
            continue
        parts = v.split(".")
        name = parts[0]
        ns = parts[1] if len(parts) > 1 else None
        if name not in targets or (ns and targets[name] and ns != targets[name]):
            ok = False
    c.check(rid, ok, f"DB_POSTGRESDB_HOST={found}; Services routing to postgres:5432: {sorted(targets)}")


def check_credentials(c, rid):
    user, pw = n8n_env(c, "DB_POSTGRESDB_USER"), n8n_env(c, "DB_POSTGRESDB_PASSWORD")
    accounts = set()
    for u_var, p_var in (("POSTGRES_USER", "POSTGRES_PASSWORD"), ("POSTGRES_NON_ROOT_USER", "POSTGRES_NON_ROOT_PASSWORD")):
        for u, p in zip(db_env(c, u_var), db_env(c, p_var)):
            if u_var == "POSTGRES_USER" and u is None:
                u = "postgres"
            if u not in (None, "?") and p not in (None, "?"):
                accounts.add((u, p))
    pairs = list(zip(user, pw))
    ok = bool(pairs) and all(p in accounts for p in pairs)
    c.check(rid, ok, f"n8n uses user {[u for u, _ in pairs]}; postgres accounts {sorted(a for a, _ in accounts)}")


def check_pgdata(c, rid):
    found = db_env(c, "PGDATA")
    base = "/var/lib/postgresql/data"
    ok = bool(found) and all(v and (v.rstrip("/") == base or v.startswith(base + "/")) for v in found)
    c.check(rid, ok, f"PGDATA={found}")


def check(docs):
    c = Checker(docs)
    c.image_deployed("R01-n8n-deployed", N8N)
    c.image_deployed("R02-postgres-deployed", DB)
    c.env_equals("R03-db-type", N8N, "DB_TYPE", "postgresdb")
    check_db_host(c, "R04-db-host-routes-to-postgres")
    check_default(c, "R05-db-port", "DB_POSTGRESDB_PORT", "5432")
    check_default(c, "R06-db-name", "DB_POSTGRESDB_DATABASE", "n8n")
    check_credentials(c, "R07-db-credentials-match")
    c.env_set("R08-postgres-password", DB, "POSTGRES_PASSWORD")
    c.env_equals("R09-postgres-db", DB, "POSTGRES_DB", "n8n")
    check_pgdata(c, "R10-pgdata-in-volume")
    c.persistent("R11-postgres-persistent", DB, "/var/lib/postgresql/data")
    c.persistent("R12-n8n-persistent", N8N, "/home/node/.n8n")
    c.external("R13-n8n-external", N8N, 5678)
    return c.results
