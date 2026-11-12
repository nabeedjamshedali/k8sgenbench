"""D4 requirement checks for P01 (Zabbix), derived from internal/fact_sheet.md only.

Graded core is 3 components: zabbix-server, zabbix-web (nginx+mysql variant -- see
internal/fact_sheet.md's scope note for why nginx rather than apache), and mysql-server.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

SERVER = "zabbix/zabbix-server-mysql"
WEB = "zabbix/zabbix-web-nginx-mysql"
MYSQL = "mysql"

SERVER_PORT = 10051
WEB_PORT = 8080


def check(docs):
    c = Checker(docs)

    # Components deployed
    c.image_deployed("R01-server-deployed", SERVER)
    c.image_deployed("R02-web-deployed", WEB)
    c.image_deployed("R03-mysql-deployed", MYSQL)

    # zabbix-web -> zabbix-server: hostname `zabbix-server` is fixed in the web container's own
    # env file (ZBX_SERVER_HOST=zabbix-server, docs_bundle/env_web L1). Not a Service name
    # requirement in Kubernetes (the env var just needs to resolve), so this is checked as a
    # self-consistency fact: the web component's ZBX_SERVER_HOST env var must equal the literal
    # hostname `zabbix-server`. Since a model could satisfy this many ways (a Service named
    # zabbix-server, a headless Service, etc.) and the docs only fix the hostname STRING (not that
    # it must be a Service of that exact name), we check the env var value directly.
    c.env_equals("R04-web-server-hostname", WEB, "ZBX_SERVER_HOST", "zabbix-server")

    # zabbix-server and zabbix-web -> mysql-server: hostname `mysql-server` is the project's own
    # documented default (docs_bundle/env_db_mysql L1, commented `DB_SERVER_HOST=mysql-server`).
    # That default is only honored if DB_SERVER_HOST is left UNSET; if a model's manifest sets it
    # explicitly, it must equal "mysql-server" to actually reach the database. Not an oracle check:
    # the default is documented, unredacted, in docs_bundle/env_db_mysql.
    for rid, image in (("R05-server-db-hostname", SERVER), ("R06-web-db-hostname", WEB)):
        hits = c.m.workloads_with_image(image)
        vals = [c.m.env(w, cc, "DB_SERVER_HOST") for w, cc in hits]
        ok = bool(hits) and all(v in (None, "mysql-server") for v in vals)
        c.check(rid, ok, f"DB_SERVER_HOST={vals}" if hits else f"no workload runs {image}")

    # Required mysql env var
    c.env_set("R07-mysql-database-set", MYSQL, "MYSQL_DATABASE")

    # Persistence: mysql-server's data directory
    c.persistent("R08-mysql-persistent", MYSQL, "/var/lib/mysql")

    # External reachability: zabbix-web's HTTP port must be reachable from outside the cluster
    c.external("R09-web-external", WEB, WEB_PORT)

    # zabbix-server and mysql-server are internal only (negative checks, informational)
    ok, detail = c.m.externally_reachable(SERVER, SERVER_PORT)
    c.check("R10-server-internal-only", not ok, detail)
    ok, detail = c.m.externally_reachable(MYSQL, 3306)
    c.check("R11-mysql-internal-only", not ok, detail)

    return c.results


if __name__ == "__main__":
    import yaml

    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "human", "kubernetes.yaml")
    docs = list(yaml.safe_load_all(open(path, encoding="utf-8")))
    results = check(docs)
    for r in results:
        tag = "[oracle] " if r["oracle"] else ""
        print(f"{'PASS' if r['passed'] else 'FAIL'} {tag}{r['id']}: {r['detail']}")
