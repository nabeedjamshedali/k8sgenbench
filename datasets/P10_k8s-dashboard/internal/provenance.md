# Provenance: Kubernetes Dashboard

Repository: https://github.com/kubernetes/dashboard at tag `v2.7.0`, commit `42deb6b32a27296ac47d1f9839a68fab6053e5fc` (paths below without prefix).
Metrics scraper source: https://github.com/kubernetes-sigs/dashboard-metrics-scraper at tag `v1.0.8`, commit `5dfe71eca5b783e9b726e9a6b0f73c8db89eaf5e` (paths prefixed `scraper:`).
No fact below is taken from `aio/deploy/` (recommended, alternative, head manifests or the Helm chart).

| Spec fact | Source |
|---|---|
| Purpose: web-based UI to manage applications and the cluster | `README.md` L22 |
| Dashboard proxies to the API server and passes the user's auth information; bearer token login | `docs/user/access-control/README.md` L9-10, L24, L46-48 |
| Scraper role: scrape and store a small window of Metrics Server metrics | `scraper:README.md` L3; `docs/user/integrations.md` L7, L11 |
| Image `kubernetesui/dashboard:v2.7.0` | `Makefile` L32-33 (`RELEASE_IMAGE = kubernetesui/dashboard`, `RELEASE_VERSION = v2.7.0`); `docs/developer/release-procedures.md` L20 |
| Image `kubernetesui/metrics-scraper`, tag = release tag | `scraper:hack/deploy.sh` L4, L11; tag `v1.0.8` of the scraper repository. The pairing of dashboard v2.7.0 with scraper v1.0.8 is stated only in deployment files (`aio/deploy/recommended.yaml` L278, Helm `values.yaml` L260): image reference: human manifest (unavoidable; identifies the artefact) |
| Go server serving Angular UI and REST API | `dashboard.go` L165-171; `src/app/frontend/index.html` L31 (`<kd-root>`) |
| HTTPS on port 8443 | `dashboard.go` L50 (`--port` default 8443), L174-185; `docs/common/dashboard-arguments.md` L10; `docs/user/access-control/README.md` L30 |
| HTTPS only with a certificate; `--auto-generate-certificates` generates one in memory | `dashboard.go` L64, L145-163; `docs/user/installation.md` L11; `docs/common/dashboard-arguments.md` L3, L16 |
| `--tls-cert-file`/`--tls-key-file` in `/certs` | `dashboard.go` L53, L155-158; `docs/common/dashboard-arguments.md` L13-15; `docs/user/installation.md` L19, L29-32 |
| Without certificate: plain HTTP on 9090 | `dashboard.go` L49, L186-189; `aio/Dockerfile` L38-39 (`EXPOSE 9090 8443`, entrypoint sets `--insecure-bind-address=0.0.0.0`) |
| Login disabled over plain HTTP | `docs/common/dashboard-arguments.md` L27 (`enable-insecure-login` default false); `docs/user/accessing-dashboard/README.md` L129-135 |
| Optional custom certificate Secret `kubernetes-dashboard-certs` with `tls.crt`/`tls.key` | `docs/user/installation.md` L13-16, L19; `src/app/backend/auth/api/types.go` L27-28 |
| `--namespace`, fallback `POD_NAMESPACE`, then `kube-system` | `dashboard.go` L71; `docs/common/dashboard-arguments.md` L24 |
| State and scraper lookup use that namespace | `src/app/backend/client/csrf/manager.go` L37, L49; `src/app/backend/auth/jwe/keyholder.go` L146; `src/app/backend/settings/manager.go` L51, L92; `src/app/backend/integration/metric/sidecar/restclient.go` L49, L60 |
| CSRF Secret `kubernetes-dashboard-csrf`, key `csrf`; must exist (panic), filled if empty | `src/app/backend/client/api/types.go` L33, L36; `src/app/backend/client/csrf/manager.go` L36-52; called at startup via `src/app/backend/client/manager.go` L492-496, L517-527, L588-595 and `dashboard.go` L96 |
| Key holder Secret `kubernetes-dashboard-key-holder`: read, created if missing, recreated on delete | `src/app/backend/auth/api/types.go` L24-25; `src/app/backend/auth/jwe/keyholder.go` L112-140; `dashboard.go` L199 |
| Settings ConfigMap `kubernetes-dashboard-settings`: read, created with defaults if missing; saves use user credentials | `src/app/backend/settings/api/types.go` L26-27; `src/app/backend/settings/manager.go` L50-56, L91-93; `src/app/backend/settings/handler.go` L87 (read with service account), L99 (save with request client) |
| In-cluster config unless `--apiserver-host`/`--kubeconfig` | `src/app/backend/client/manager.go` L499-503; `docs/common/dashboard-arguments.md` L17, L23 |
| Scraper reached through service proxy, Service `dashboard-metrics-scraper` in own namespace, no port name | `src/app/backend/integration/metric/sidecar/restclient.go` L46-67; `aio/develop/npm-command.sh` L52 (`.../services/dashboard-metrics-scraper:/proxy/`, empty port name); `docs/common/dashboard-arguments.md` L20 |
| Single unnamed Service port needed | Follows from the empty port name above and Kubernetes API server service-proxy behaviour (the proxy selects the Service port whose name equals the requested port name). Upstream Kubernetes behaviour, not a line in this repository |
| `--sidecar-host` replaces service proxy | `dashboard.go` L59; `src/app/backend/integration/metric/sidecar/client.go` L260-280; `docs/common/dashboard-arguments.md` L20 |
| Health check `/healthz` every 30 s; metrics disabled if unhealthy | `src/app/backend/integration/metric/sidecar/restclient.go` L64; `dashboard.go` L63, L120-123; `docs/user/integrations.md` L7 |
| `GET /health` returns `{"running":true}` when API server reachable | `dashboard.go` L167; `src/app/backend/health/handler.go` L28-30; `src/app/backend/health/manager.go` L35-39; `src/app/backend/health/api/types.go` L18 |
| `GET /api/v1/integration/sidecar/state` returns `connected` | `src/app/backend/integration/handler.go` L33-39, L50; `src/app/backend/integration/manager.go` L57-63; `src/app/backend/integration/api/types.go` L25, L48; `src/app/backend/integration/metric/manager.go` L119-121 (uses the service-account client); `src/app/backend/handler/apihandler.go` L110-116 |
| `GET /metrics` | `dashboard.go` L171 |
| Scraper port 8000, no port flag | `scraper:server.go` L100 (`ListenAndServe(":8000", ...)`), L45-52 (flag list); `scraper:README.md` L5-14. Note: `scraper:Dockerfile` L41 says `EXPOSE 8080`, which contradicts the code; the code is authoritative |
| Scrapes every minute, nodes and pods cluster-wide, SQLite `/tmp/metrics.db`, 15 min retention | `scraper:server.go` L46-48, L83, L104-118, L131-151, L160-161; `scraper:README.md` L9-11 |
| Metrics API provided by metrics-server, installed separately | `README.md` L57; `docs/user/integrations.md` L11-12 |
| Scraper keeps running without metrics-server | `scraper:server.go` L113-117 (`break` leaves only the `select`; the loop continues), L135-138 (error logged); HTTP server started independently at L95-101 |
| `--namespace`/`POD_NAMESPACE` scope scraper and skip nodes | `scraper:server.go` L51-52, L131-139; `scraper:README.md` L14 |
| Scraper in-cluster config unless `--kubeconfig` | `scraper:server.go` L45, L67-68; `scraper:README.md` L8 |
| Scraper: any non-`/api/v1/dashboard/` path returns 200 `URL: <path>` | `scraper:pkg/api/api.go` L15-27 |
| UI page title `Kubernetes Dashboard` (smoke check) | `src/app/frontend/index.html` L22 |
| Dependencies | `dashboard.go` L96-102 (fatal if API server unreachable); `docs/user/integrations.md` L7, L11; `README.md` L57 |
| Dashboard permissions (own namespace: CSRF Secret get/update, key holder get/create, settings ConfigMap get/create, services/proxy get) | Code paths cited above (csrf/manager.go L38, L49; keyholder.go L128, L136; settings/manager.go L51, L92; restclient.go L48-65). Also listed in prose in `docs/user/access-control/README.md` L12-17 |
| No other access needed for the dashboard service account | `docs/user/access-control/README.md` L9-10; `README.md` L28 ("minimal set of RBAC privileges needed to run") |
| Scraper permissions: list node and pod metrics in all namespaces | `scraper:server.go` L134, L143; `docs/user/access-control/README.md` L17 |
| Access via `kubectl proxy` / `port-forward`; NodePort only for single-node development | `README.md` L40-50; `docs/user/accessing-dashboard/README.md` L12-14, L50-61, L63-65 |
| Scraper internal only | `docs/user/accessing-dashboard/README.md` describes access to the dashboard only; the scraper is reached only via the API server proxy (`restclient.go` L46-67) |

## Excluded facts (appear only in the human manifests, or in docs that restate the manifests)
- Service port 443 for the dashboard and its Service name `kubernetes-dashboard` (also shown in `docs/user/accessing-dashboard/README.md` L47, L55, L82-97, but only as a description of the shipped manifest), Service type ClusterIP.
- The namespace name `kubernetes-dashboard`. The spec only requires the dashboard's `--namespace` to match the namespace it runs in.
- Replica counts, `revisionHistoryLimit`, `imagePullPolicy: Always`, liveness probes (HTTPS `/` on 8443 and HTTP `/` on 8000), `securityContext` (`runAsUser: 1001`, `runAsGroup: 2001`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, seccomp `RuntimeDefault`), `nodeSelector` and the master toleration, labels `k8s-app`.
- The `emptyDir` volumes at `/tmp` for both containers and the comment "Create on-disk volume to store exec logs" (the dashboard backend code does not write to `/tmp`; for the scraper the spec states only that `/tmp/metrics.db` must be writable).
- The exact Role/ClusterRole rules: `resourceNames` lists, the `delete` verb on secrets, `update` on the ConfigMap, `proxy` on `services`, the heapster entries, and `get`/`watch` on metrics. The spec describes the API calls the code makes instead.
- Pre-created empty Secrets `kubernetes-dashboard-certs` and `kubernetes-dashboard-key-holder` and the empty ConfigMap `kubernetes-dashboard-settings` (the code creates the latter two itself if allowed). The CSRF Secret is in the spec because the code requires it.
- The shared ServiceAccount for both components.
