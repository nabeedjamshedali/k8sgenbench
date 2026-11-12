# Grafana

## Purpose
Grafana is an observability and data visualisation web application. Users sign in through a web UI to build dashboards, query data sources and manage alerts. Grafana stores its own configuration, users and dashboards in a database; by default this is an embedded SQLite database kept in the Grafana data directory.

## Components

| Component | Image | Role |
|---|---|---|
| grafana | `grafana/grafana:latest` | Grafana OSS server (web UI and HTTP API) with an embedded SQLite database |

## Component details

### grafana
- Listens on HTTP port 3000.
- The image runs as the non-root user with UID 472 (group 0).
- Data directory: `/var/lib/grafana` (the image sets `GF_PATHS_DATA=/var/lib/grafana`). It holds the SQLite database file `grafana.db` and installed plugins.
- Persistence: `/var/lib/grafana` must be stored on a persistent volume so that users, dashboards and settings survive restarts.
- Configuration: every setting in the Grafana configuration file can be overridden with an environment variable named `GF_<SECTION>_<KEY>` (upper case, with `.` and `-` replaced by `_`).
- Optional environment variables: `GF_SECURITY_ADMIN_USER` and `GF_SECURITY_ADMIN_PASSWORD`, the initial administrator account created on first start (defaults `admin` / `admin`).
- Health checks: `GET /api/health` on port 3000 returns HTTP 200 with `"database": "ok"` when the server is running and can reach its database, and HTTP 503 otherwise. `GET /healthz` returns HTTP 200 when the web server is running.
- Does not use the Kubernetes API.

## Dependencies
- None. With the default configuration Grafana needs no other service.

## External access
- The Grafana web UI (port 3000) must be reachable from outside the cluster.
