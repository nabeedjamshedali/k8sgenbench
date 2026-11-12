# Zabbix

**Scope note:** zabbix-docker ships many optional components (two proxy variants, a Java gateway,
a web-service reporting container, an SNMP traps DaemonSet, RBAC, NetworkPolicy, etc.). The D4
graded core is exactly the 3 components needed for a minimal working deployment — `zabbix-server`
(backend), `zabbix-web` (Nginx+MySQL web UI), and `mysql-server` (database) — because these are the
MySQL-backed services that carry no Compose `profiles:` restriction in
`compose_zabbix_components.yaml` (i.e. the actual default/minimal service set: `server`/`server-mysql`
at L2-9/L130-150 and `web-nginx`/`web-nginx-mysql` at L412-507 have no `profiles:` key, while
`web-apache`/`web-apache-mysql` at L316-389 is gated behind `profiles: [all]` and so is NOT started
by default). This also matches the vendor's own `kubernetes.yaml`, which deploys
`zabbix-web-nginx-mysql`, not the Apache variant. The rest are optional monitoring-agent or
distributed-proxy features not needed for the base application to run.

## Purpose
Zabbix is an enterprise-class open source distributed monitoring solution: it monitors the health,
integrity and numerous parameters of a network and its servers, and raises alerts on problems.

## Components

| Component | Image | Role |
|---|---|---|
| zabbix-server | `zabbix/zabbix-server-mysql` | Zabbix server with MySQL/MariaDB database support — the monitoring engine/backend |
| zabbix-web | `zabbix/zabbix-web-nginx-mysql` | Zabbix web interface on the Nginx web server, with MySQL/MariaDB database support |
| mysql-server | `mysql` (official image) | The MySQL database that stores Zabbix's configuration and collected data |

(Out of scope for D4 grading, but shipped in `human/kubernetes.yaml`: zabbix-agent, two proxy
variants — sqlite3 and mysql, zabbix-java-gateway, zabbix-web-service, zabbix-snmptraps.)

## Component details

### zabbix-server
- Listens on TCP port 10051 (the "zabbix-trapper" port used by agents/proxies to push data).
- Connects to the database at hostname `mysql-server`. This hostname is fixed by the Compose
  network alias Zabbix's own packaging gives the database service.
- Required database env vars: `MYSQL_USER_FILE`/`MYSQL_PASSWORD_FILE` (paths to credential files,
  the project's documented alternative to plaintext `MYSQL_USER`/`MYSQL_PASSWORD`) and
  `MYSQL_DATABASE` (the schema name, `zabbix` by the project's own default).
- No persistence of its own in the 3-component core (state lives in MySQL).
- Internal only — not reachable from outside the cluster.

### zabbix-web
- Listens on HTTP port 8080 and HTTPS port 8443.
- Health endpoint: `GET /ping` on port 8080 returns HTTP 200 (used by the project's own Docker
  healthcheck).
- Connects to zabbix-server at hostname `zabbix-server` — fixed in the web container's own env
  file (`ZBX_SERVER_HOST=zabbix-server`).
- Connects to the database at hostname `mysql-server` — same fixed hostname as zabbix-server's
  database connection, via the same env-file/secrets convention (`MYSQL_USER_FILE`,
  `MYSQL_PASSWORD_FILE`, `MYSQL_DATABASE=zabbix`).
- Must be reachable from outside the cluster: it is the user-facing web UI, and the project's own
  Docker Compose documentation discusses exposing exactly this component's HTTP/HTTPS ports to the
  host.

### mysql-server
- Listens on the default MySQL port (3306).
- Required env var: `MYSQL_DATABASE` (the Zabbix schema name, `zabbix`).
- Credentials are supplied via `_FILE`-suffixed secret-file env vars
  (`MYSQL_ROOT_PASSWORD_FILE`/equivalents), the project's documented convention for Docker Swarm
  and Kubernetes secrets, rather than plaintext `MYSQL_*_PASSWORD` values.
- Persistence: the data directory `/var/lib/mysql` must be stored on a volume that survives
  restarts; the project's own Compose file mounts a host/volume path there.
- Health check: `mysqladmin ping` succeeds.
- Internal only — not reachable from outside the cluster.

## Dependencies
- zabbix-web depends on zabbix-server (hostname `zabbix-server`) and on mysql-server (hostname
  `mysql-server`).
- zabbix-server depends on mysql-server (hostname `mysql-server`).

## External access
- zabbix-web (ports 8080/8443) must be reachable from outside the cluster — it is the application's
  web UI.
- zabbix-server and mysql-server are internal only.

## Permissions
- None of the 3 in-scope components need any Kubernetes API permissions (no RBAC rules are
  documented for them). The optional, out-of-scope zabbix-agent component does use RBAC/SCC
  permissions in the full stack, but that is outside the D4 graded core.
