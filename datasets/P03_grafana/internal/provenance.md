# Provenance: Grafana

Repository: https://github.com/grafana/grafana at commit `3920186ffd305507ae78ea7f035d0197e71d929f`.
The human manifest is the YAML code block at L96-177 of `docs/sources/setup-grafana/installation/kubernetes/index.md` (abbreviated `k8s-docs` below). Facts are cited from the prose of that page only, never from its YAML blocks. No fact below is taken from `human/grafana.yaml`.

Other abbreviations: `docker-docs` = `docs/sources/setup-grafana/installation/docker/index.md`; `configure-docker` = `docs/sources/setup-grafana/configure-docker.md`; `configure-grafana` = `docs/sources/setup-grafana/configure-grafana/_index.md`; `http-api-other` = `docs/sources/developer-resources/api-reference/http-api/api-legacy/other.md`.

| Spec fact | Source |
|---|---|
| Purpose: web UI, dashboards, sign-in | `k8s-docs` L234-238 (browser shows the Grafana sign-in page; sign in as `admin`) |
| Configuration, users and dashboards stored in an embedded SQLite database by default | `docker-docs` L74; `conf/defaults.ini` L236 (`type = sqlite3`) |
| Image name `grafana/grafana` (Grafana OSS) | `docker-docs` L28 ("Grafana Open Source: `grafana/grafana`"), L15-16; `k8s-docs` L395 (prose example `image: grafana/grafana:12.1.0`); `configure-docker` L112 (tag list for `grafana/grafana`) |
| Tag `latest` | image reference: human manifest (unavoidable; identifies the artefact) |
| Listens on HTTP port 3000 | `Dockerfile` L277 (`EXPOSE 3000`); `conf/defaults.ini` L44 (`protocol = http`), L53 (`http_port = 3000`); `k8s-docs` L49 ("Grafana default port") |
| Runs as UID 472, group 0 | `Dockerfile` L215-216 (`GF_UID="472"`, `GF_GID="0"`), L283 (`USER "$GF_UID"`); L401-403 (default build stage is `final-alpine`) |
| Data directory `/var/lib/grafana`, `GF_PATHS_DATA` | `Dockerfile` L220; `configure-docker` L118-123 |
| `grafana.db` lives in the data directory | `conf/defaults.ini` L16 (data path holds "the sqlite3 db"), L283-284 (`path = grafana.db`, relative to data_path) |
| Plugins live in the data directory | `Dockerfile` L223 (`GF_PATHS_PLUGINS="/var/lib/grafana/plugins"`); `configure-docker` L126 |
| Data directory must be persistent | `docker-docs` L74 (data is lost when the container is removed; set up persistent storage), L84-100 (volume at `/var/lib/grafana`); `k8s-docs` L89 (prose table: "Persistent Volume Claim (PVC): This object stores the data.") |
| `GF_<SECTION>_<KEY>` override convention | `configure-grafana` L85-97; `configure-docker` L118 |
| `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`, defaults `admin`/`admin` | `conf/defaults.ini` L476, L480-484 (`[security]`, `admin_user = admin`, `admin_password = admin`); `configure-grafana` L104-105, L121 (`GF_SECURITY_ADMIN_USER`); `configure-docker` L239 (`GF_SECURITY_ADMIN_PASSWORD__FILE`); `k8s-docs` L238 |
| `GET /api/health` returns 200 with `"database": "ok"`, 503 on failure | `http-api-other` L97-119; `pkg/api/http_server.go` L792-803, L807-809, L820-823, L834-838; `pkg/api/health.go` L17-21 (`SELECT 1` against the database) |
| `GET /healthz` returns 200 when the web server is running | `pkg/api/http_server.go` L770-779 |
| Does not use the Kubernetes API | No Kubernetes API access is described in `k8s-docs` prose; Grafana is a self-contained web server (`conf/defaults.ini` `[server]` L42-63) |
| No dependencies with default configuration | `conf/defaults.ini` L236 (embedded SQLite default); `docker-docs` L43 (runs with a single `docker run`) |
| Web UI reachable from outside the cluster | `k8s-docs` L49 ("Enable port `3000` in your network environment"), L234-236 (open the external IP in a browser), L250 |

Smoke check sources: `/api/health` body as above; `/login` route in `pkg/api/api.go` L88 (`r.Get("/login", hs.LoginView)`) and the literal "Grafana" in `public/views/index.html` L219 (both read with `git show HEAD:<path>`); `grafana.db` location as above.

## Excluded facts (appear only in the human manifest, or mirror its decisions)
- Service type `LoadBalancer` (also mentioned in `k8s-docs` prose L210, but it is a Service-type decision), the port name `http-grafana`, `sessionAffinity: None`.
- Readiness probe on `/robots.txt` and the TCP liveness probe on 3000, with their timings.
- Resource requests `cpu: 250m`, `memory: 750Mi` and the PVC size `1Gi`. The prose "Minimum Hardware Requirements" in `k8s-docs` L36-38 (1 GB disk, 750 MiB memory, 250m CPU) states the same numbers; they are left out because they are the manifest's resource values.
- `securityContext` with `fsGroup: 472` and `supplementalGroups: [0]`. The spec states only the image's UID/GID from the Dockerfile.
- `imagePullPolicy: IfNotPresent`, PVC access mode `ReadWriteOnce`, the object names `grafana` / `grafana-pvc` / `grafana-pv`, the label `app: grafana`.
- The namespace `my-grafana` (`k8s-docs` L59-69 prose recommends a dedicated namespace and names it).
