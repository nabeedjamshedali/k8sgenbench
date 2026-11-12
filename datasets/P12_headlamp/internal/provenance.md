# Provenance: Headlamp

Repository: https://github.com/kubernetes-sigs/headlamp at commit `959ce35869e22180f936a941ac7b05dc2db602c7`.
No fact below is taken from `kubernetes-headlamp.yaml`, `kubernetes-headlamp-ingress-sample.yaml`, `kubernetes-headlamp-monitoring.yaml` or the Helm chart.
Paths under `backend/` refer to the Go backend source at the same commit.

| Spec fact | Source |
|---|---|
| Purpose: Kubernetes web UI, list/view resources, logs, exec, resource editor | `README.md` L14-17, L29, L31-33 |
| Deployed in the cluster it manages | `docs/installation/in-cluster/index.md` L6-7 |
| Single container: Go backend serves the front end and proxies to the API server | `Dockerfile` L8-29 (Go backend build), L91-92 (backend binary and front end copied into one image), L102 (`-html-static-dir /headlamp/frontend`); `backend/cmd/headlamp.go` L2404 (`/clusters/{clusterName}/{api:.*}` proxy route), L1613-1632 (front end served at `/`) |
| Image `ghcr.io/headlamp-k8s/headlamp` | `README.md` L8 ("Container images are still at ghcr.io"); `docs/installation/verify-releases.md` L68-72 (`ghcr.io/headlamp-k8s/headlamp`, `:vX.Y.Z`) |
| Tag `latest` | `docs/installation/in-cluster/index.md` L227 (`image: ghcr.io/headlamp-k8s/headlamp:latest`, in prose docs) |
| Listens on port 4466 | `Dockerfile` L99 (`EXPOSE 4466`); `backend/pkg/config/config.go` L26 (`defaultPort = 4466`), L633 |
| Image entrypoint with front end and plugins dir preconfigured | `Dockerfile` L102 (`ENTRYPOINT ["/headlamp/headlamp-server", "-html-static-dir", "/headlamp/frontend", "-plugins-dir", "/headlamp/plugins"]`) |
| Runs as a non-root user | `Dockerfile` L79-89 (creates user `headlamp`), L97 (`USER headlamp`) |
| In-cluster mode via `-in-cluster` | `backend/pkg/config/config.go` L41, L603 (`"Set when running from a k8s cluster"`); `docs/installation/in-cluster/index.md` L119-121 |
| `HEADLAMP_CONFIG_<FLAG>` env vars, flag takes priority | `backend/pkg/config/config.go` L318-322 (env provider strips `HEADLAMP_CONFIG_`, lower-cases, `_` to `-`), L426-432; `docs/installation/in-cluster/oidc.md` L12-16 (examples `HEADLAMP_CONFIG_OIDC_CLIENT_ID` etc.) |
| Connection built from the pod's in-cluster configuration and service account; no kubeconfig needed | `docs/installation/in-cluster/index.md` L119-124; `backend/pkg/kubeconfig/kubeconfig.go` L1280 (`rest.InClusterConfig()`), L1315-1319 (server and CA taken from it); `backend/cmd/headlamp.go` L790-793 (no in-cluster context if this fails). client-go's `InClusterConfig` reads the mounted token at `/var/run/secrets/kubernetes.io/serviceaccount/token` (upstream behaviour; path also in `backend/pkg/kubeconfig/kubeconfig.go` L1211) |
| OIDC flags | `docs/installation/in-cluster/oidc.md` L10-16; `backend/pkg/config/config.go` L661-667 |
| `-base-url` | `docs/installation/base-url.md` L8, L17; `backend/pkg/config/config.go` L626 |
| `-tls-cert-path` / `-tls-key-path`, TLS at the ingress by default | `docs/installation/in-cluster/tls.md` L8, L14-17, L71; `backend/pkg/config/config.go` L711-712 |
| None of the optional flags is required | Defaults in `backend/pkg/config/config.go` L626, L661-667, L711-712 (empty strings / defaults) |
| `HEADLAMP_CONFIG_METRICS_ENABLED=true` enables `/metrics` on the main port | `backend/cmd/headlamp.go` L948-954; `backend/pkg/config/config.go` L702 (`metrics-enabled` defaults to false) |
| No persistence; in-memory context, no kubeconfig written | `docs/installation/in-cluster/index.md` L119-124; front end and plugins in the image: `Dockerfile` L91-94 |
| No dedicated health endpoint; `GET /` serves the UI | `backend/cmd/headlamp.go` L1613-1632 (catch-all `/` serves `index.html`); grep for `healthz`/`/health` in `backend/cmd` finds no route |
| `GET /config` returns JSON incl. clusters | `backend/cmd/headlamp.go` L1279-1281 (route), L2666-2685 (`getConfig`), L188-189 (`json:"clusters"`); `backend/pkg/kubeconfig/kubeconfig.go` L471-472 (in-cluster source `incluster`) |
| Users log in with a bearer token, ServiceAccount token recommended | `docs/installation/index.mdx` L10-13, L17-18, L60; `docs/installation/in-cluster/index.md` L277-279 |
| Log-in through OIDC | `docs/installation/in-cluster/oidc.md` L6, L10-16 |
| Each user's credentials are used; access decided by the user's RBAC | `README.md` L66-68; `docs/installation/index.mdx` L12-13; `backend/pkg/kubeconfig/kubeconfig.go` L1331-1335 (the in-cluster context gets no credentials unless `-unsafe-use-service-account-token` is set) |
| Headlamp does not use its own service account for user requests | `backend/pkg/config/config.go` L651-653 (`"UNSAFE: use the pod's service account token to authenticate all users in-cluster. Disables per-user auth"`, default false); `backend/pkg/kubeconfig/kubeconfig.go` L1333-1335 |
| Optional read of `kube-system/kubeadm-config`, fallback `main` | `backend/pkg/config/config.go` L604-607; `backend/pkg/kubeconfig/kubeconfig.go` L1214-1267 (2 s timeout, errors only logged), L1285-1287, L1321-1323; L104 (`DefaultInClusterContextName = "main"`) |
| Depends only on the Kubernetes API server | `docs/installation/in-cluster/index.md` L105-107 (only a running cluster is assumed), L119-124 |
| Web UI reachable from outside via an ingress | `docs/installation/in-cluster/index.md` L6-7 ("set up an ingress server for having it available to users"), L242-249 |

## Excluded facts (appear only in the human manifests)
- Container port 9090 named `metrics`: the backend serves `/metrics` on the main port (`backend/cmd/headlamp.go` L952); no source outside the manifest mentions 9090.
- Env values `HEADLAMP_CONFIG_TRACING_ENABLED=true`, `HEADLAMP_CONFIG_METRICS_ENABLED=true`, `HEADLAMP_CONFIG_OTLP_ENDPOINT=otel-collector:4317`, `HEADLAMP_CONFIG_SERVICE_NAME`, `HEADLAMP_CONFIG_SERVICE_VERSION`. Only the metrics switch is kept in the spec, as optional, because it is documented in code. The OTLP collector host `otel-collector` is a manifest decision.
- Namespace `kube-system` (also used in the docs' examples, but it is the manifest's choice), Service port 80, object names `headlamp`, label `k8s-app: headlamp`, `replicas: 1`, readiness and liveness probe settings, `nodeSelector: kubernetes.io/os: linux`.
- The `-plugins-dir=/headlamp/plugins` argument (already set by the image entrypoint).
- The Secret `headlamp-admin` of type `kubernetes.io/service-account-token`. The docs describe creating a ServiceAccount `headlamp-admin` bound to `cluster-admin` for users to log in (`docs/installation/index.mdx` L20-37); this is a user log-in procedure, not a requirement of the Headlamp workload, so it is not in the spec.
