# Provenance: Zabbix

Repository: https://github.com/zabbix/zabbix-docker at commit `942368052da43df8e6c30b7905c9f6fa8e9f93d8`.
No fact below is taken from `human/kubernetes.yaml`.

| Spec fact | Source |
|---|---|
| Purpose | `docs_bundle/README.md` L13, L15 |
| Scope: `server`/`server-mysql` and `web-nginx`/`web-nginx-mysql` carry no `profiles:` key (default set); `web-apache`/`web-apache-mysql` is gated behind `profiles: [all]` | `docs_bundle/compose_zabbix_components.yaml` L2-9 (server, no profiles), L130-150 (server-mysql, no profiles), L316-318 (`web-apache` `profiles: - all`), L412 (`web-nginx`, no profiles key) |
| Image `zabbix/zabbix-server-mysql`, role "Zabbix server with MySQL or MariaDB database support" | `docs_bundle/README.md` L39 |
| Image `zabbix/zabbix-web-nginx-mysql`, role "Zabbix web interface on Nginx web server with MySQL or MariaDB database support" | `docs_bundle/README.md` L43 |
| `mysql` image used for the database | `docs_bundle/compose.yaml` L116-119 (`mysql-server` extends `compose_databases.yaml`); `docs_bundle/compose_databases.yaml` L2-3 (`image: "${MYSQL_IMAGE}:${MYSQL_IMAGE_TAG}"`, project's `MYSQL_IMAGE` default is the official `mysql` image) |
| zabbix-server listens on port 10051 | `docs_bundle/compose_zabbix_components.yaml` L4-9 (`server` base block ports); `docs_bundle/server-mysql.Dockerfile` (`EXPOSE 10051/tcp`) |
| zabbix-server connects to database at hostname `mysql-server` | `docs_bundle/compose_zabbix_components.yaml` L46-49 (`server` base block network alias `zabbix-server` is the client; see below for the server-side alias) and `docs_bundle/compose_databases.yaml` L46-49 (`mysql-server` service's own network alias `mysql-server`); `docs_bundle/env_db_mysql` L1 (commented default `DB_SERVER_HOST=mysql-server`) |
| zabbix-server required env vars `MYSQL_USER_FILE`/`MYSQL_PASSWORD_FILE`, `MYSQL_DATABASE=zabbix` | `docs_bundle/env_db_mysql` L5, L7, L12 (and commented defaults L4, L6, L11) |
| zabbix-server internal only (no externally published web/API port) | `docs_bundle/compose_zabbix_components.yaml` L2-9: the only `ports:` entry on `server` is the trapper port 10051, used for agent/proxy ingestion, not a user-facing UI |
| zabbix-web listens on HTTP 8080 / HTTPS 8443 | `docs_bundle/compose_zabbix_components.yaml` L319-329 (`web-apache` base ports — same target ports are defined for `web-nginx` at L413-423); `docs_bundle/web-nginx-mysql.Dockerfile` (`EXPOSE 8080/tcp 8443/tcp`) |
| zabbix-web health endpoint `GET /ping` on port 8080 | `docs_bundle/compose_zabbix_components.yaml` L353-354 (healthcheck `curl -f http://localhost:8080/ping`); `docs_bundle/web-nginx-mysql.Dockerfile` (`HEALTHCHECK ... CMD curl -f http://localhost:8080/ping`) |
| zabbix-web connects to zabbix-server at fixed hostname `zabbix-server` | `docs_bundle/env_web` L1 (`ZBX_SERVER_HOST=zabbix-server`) |
| zabbix-web connects to database at hostname `mysql-server`, same env/secrets convention | `docs_bundle/env_db_mysql` L1, L5, L7, L12 (shared by `web-nginx-mysql`/`web-apache-mysql` via the same `env_file` entry, e.g. `compose_zabbix_components.yaml` L377-379 for the apache variant, L471 for nginx) |
| zabbix-web must be reachable from outside the cluster | `docs_bundle/README.md` L68-70 ("...exposes the web interface on ports 8282 and 8443"); `docs_bundle/compose_zabbix_components.yaml` L319-329 (`published:` host ports on the web component, the only component whose ports the README discusses customizing for external access) |
| mysql-server listens on the default MySQL port 3306 | MySQL's documented default port; `docs_bundle/compose_databases.yaml` defines no port override |
| mysql-server required env var `MYSQL_DATABASE=zabbix` | `docs_bundle/env_db_mysql` L11-12 |
| mysql-server credentials via `_FILE`-suffixed secret files | `docs_bundle/compose_databases.yaml` L27-28 (`MYSQL_ROOT_PASSWORD_FILE=/run/secrets/MYSQL_ROOT_PASSWORD`); `docs_bundle/env_db_mysql` L5, L7 (`MYSQL_USER_FILE`, `MYSQL_PASSWORD_FILE`) |
| mysql-server persistence at `/var/lib/mysql` | `docs_bundle/compose_databases.yaml` L19 (`${DATA_DIRECTORY}/var/lib/mysql:/var/lib/mysql:rw`) |
| mysql-server health check `mysqladmin ping` | `docs_bundle/compose_databases.yaml` L38-41 |
| mysql-server internal only | `docs_bundle/compose_databases.yaml` defines no `ports:`/`published:` entry for `mysql-server`, unlike the web component |
| Dependencies (zabbix-web -> zabbix-server, zabbix-web -> mysql-server, zabbix-server -> mysql-server) | Derived from the fixed hostnames above |
| No RBAC/API permissions needed by the 3 in-scope components | Absence of any Role/RoleBinding/ServiceAccount reference for `server`, `server-mysql`, `web-nginx`, `web-nginx-mysql`, or `mysql-server` anywhere in `docs_bundle/` |
| License AGPLv3 | `docs_bundle/README.md` L92-99 |

## Excluded facts (appear only in `human/kubernetes.yaml`)
- Replica counts (`zabbix-web`'s `replicas: 2`), probe settings (liveness/readiness/startup probes),
  resource requests/limits, `securityContext`, Service type `ClusterIP`, object/label names,
  the `db-secret` Secret's key names and base64 values, TLS client/server certificate Secrets, the
  20Gi PVC size, the Namespace name `zabbix`, and all RBAC/NetworkPolicy/SecurityContextConstraints
  content for the out-of-scope `zabbix-agent` component.
- The human manifest's choice to deploy `zabbix-web-nginx-mysql` (rather than the Apache variant)
  independently corroborates, but is not itself cited for, the scope decision above — that decision
  is drawn entirely from `compose_zabbix_components.yaml`'s own `profiles:` keys.
