"""D4 requirement checks for P01, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

WORDPRESS = "wordpress"
MYSQL = "mysql"
SECRET_VARS = {WORDPRESS: ["WORDPRESS_DB_PASSWORD"], MYSQL: ["MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD"]}


def first_env(c, image, name):
    vals = [c.m.env(w, ct, name) for w, ct in c.m.workloads_with_image(image)]
    return vals[0] if vals else None


def db_host_routes_to_mysql(c, rid):
    host = first_env(c, WORDPRESS, "WORDPRESS_DB_HOST") or "mysql"
    name, _, port = host.partition(":")
    port = int(port) if port.isdigit() else 3306
    labels = name.split(".")
    svc_name, svc_ns = labels[0], (labels[1] if len(labels) > 1 and labels[1] != "svc" else None)
    hits = [(s, p) for s, p in c.m.exposed(MYSQL, 3306)
            if s["metadata"]["name"] == svc_name and p.get("port") == port
            and (svc_ns is None or s["metadata"].get("namespace") in (None, svc_ns))]
    c.check(rid, hits, f"WORDPRESS_DB_HOST={host} " + ("routes to mysql:3306" if hits else "does not route to mysql:3306"))


def database_exists(c, rid):
    db_name = first_env(c, WORDPRESS, "WORDPRESS_DB_NAME") or "wordpress"
    created = first_env(c, MYSQL, "MYSQL_DATABASE")
    c.check(rid, created == db_name, f"WORDPRESS_DB_NAME={db_name}, MYSQL_DATABASE={created}")


def credentials_match(c, rid):
    user = first_env(c, WORDPRESS, "WORDPRESS_DB_USER")
    pw = first_env(c, WORDPRESS, "WORDPRESS_DB_PASSWORD")
    if user == "root":
        expected = first_env(c, MYSQL, "MYSQL_ROOT_PASSWORD")
    elif user is not None and user == first_env(c, MYSQL, "MYSQL_USER"):
        expected = first_env(c, MYSQL, "MYSQL_PASSWORD")
    else:
        return c.check(rid, False, f"WORDPRESS_DB_USER={user} is neither root nor MYSQL_USER")
    ok = pw not in (None, "", "?") and pw == expected
    c.check(rid, ok, f"user {user}: password {'matches' if ok else 'does not match or is unresolvable'}")


def from_secret(c, ct, name):
    for e in ct.get("env", []) or []:
        if e.get("name") == name:
            return "secretKeyRef" in (e.get("valueFrom") or {})
    return any("secretRef" in src for src in ct.get("envFrom", []) or [])


def passwords_from_secret(c, rid):
    bad, seen = [], 0
    for image, names in SECRET_VARS.items():
        for w, ct in c.m.workloads_with_image(image):
            for n in names:
                if c.m.env(w, ct, n) is None:
                    continue
                seen += 1
                if not from_secret(c, ct, n):
                    bad.append(n)
    c.check(rid, seen and not bad, f"plain values: {bad}" if bad else f"{seen} password variable(s) from Secret")


def check(docs):
    c = Checker(docs)
    c.image_deployed("R01-wordpress-deployed", WORDPRESS)
    c.image_deployed("R02-mysql-deployed", MYSQL)
    db_host_routes_to_mysql(c, "R03-db-host-routes-to-mysql")
    c.env_set("R04-wp-db-user", WORDPRESS, "WORDPRESS_DB_USER")
    c.env_set("R05-wp-db-password", WORDPRESS, "WORDPRESS_DB_PASSWORD")
    database_exists(c, "R06-database-created")
    credentials_match(c, "R07-credentials-match")
    c.env_set("R08-mysql-root-password", MYSQL, "MYSQL_ROOT_PASSWORD")
    c.persistent("R09-wordpress-persistent", WORDPRESS, "/var/www/html")
    c.persistent("R10-mysql-persistent", MYSQL, "/var/lib/mysql")
    passwords_from_secret(c, "R11-passwords-from-secret")
    c.external("R12-wordpress-external", WORDPRESS, 80)
    return c.results

