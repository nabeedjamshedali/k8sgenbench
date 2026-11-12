# Kubernetes Dashboard

## Purpose
A general purpose, web-based UI for Kubernetes clusters. Users manage and troubleshoot the applications running in the cluster, and the cluster itself, from a browser. The dashboard acts as a proxy to the Kubernetes API server and passes each user's credentials (a bearer token entered on the login page) to it, so what a user can see and do is decided by that user's own Kubernetes permissions. A second component, the metrics scraper, collects CPU and memory usage from the Kubernetes Metrics API and keeps a short history so that the dashboard can draw usage graphs.

## Components

| Component | Image | Role |
|---|---|---|
| dashboard | `kubernetesui/dashboard:v2.7.0` | Go web server that serves the Angular UI and a REST API backed by the Kubernetes API |
| metrics-scraper | `kubernetesui/metrics-scraper:v1.0.8` | Go service that polls the Metrics API every minute, stores the samples in a SQLite file and serves them to the dashboard over HTTP |

## Component details

### dashboard
- Serves the UI and its API over HTTPS on port 8443. It does so only when it has a TLS certificate: either start it with the flag `--auto-generate-certificates` (it then generates a self-signed certificate in memory) or pass `--tls-cert-file` and `--tls-key-file` naming files in the certificate directory `/certs`. Without a certificate it serves plain HTTP on port 9090 instead, and the login page is disabled on plain HTTP. The HTTPS setup is required here.
- Optional custom certificates: a Secret named `kubernetes-dashboard-certs` holding `tls.crt` and `tls.key`, mounted at `/certs`, used together with `--tls-cert-file=/tls.crt --tls-key-file=/tls.key` (paths relative to `/certs`). With `--auto-generate-certificates` alone no certificate files are needed.
- The flag `--namespace=<namespace>` tells the dashboard in which namespace it keeps its own state (the Secrets and ConfigMap below) and where it looks for the metrics scraper. If the flag is not given, it uses the environment variable `POD_NAMESPACE`, and if that is unset it uses `kube-system`. It must be set to the namespace the dashboard runs in.
- State it keeps in that namespace (names fixed in the code):
  - Secret `kubernetes-dashboard-csrf`: must exist before the dashboard starts; the dashboard exits with an error if it is missing. The dashboard reads the key `csrf` and, if it is empty, writes a generated token back into the Secret.
  - Secret `kubernetes-dashboard-key-holder`: stores the encryption key for login tokens. The dashboard reads it, creates it if it does not exist, and recreates it if it is deleted.
  - ConfigMap `kubernetes-dashboard-settings`: stores UI settings. The dashboard reads it and creates it with default settings if it does not exist. Saving settings from the UI is done with the logged-in user's credentials.
- Connects to the Kubernetes API server with in-cluster configuration (its service account) unless `--apiserver-host` or `--kubeconfig` is given.
- Reaches the metrics scraper through the Kubernetes API server's service proxy, using a Service named `dashboard-metrics-scraper` in the dashboard's own namespace (the name is fixed in the code). The request gives only the Service name and no port name, so that Service must have a single unnamed port that routes to the scraper's port 8000. The flag `--sidecar-host=<protocol://address:port>` replaces this with a direct address. The dashboard checks the scraper by requesting `/healthz` every 30 seconds; if the scraper is unreachable, graphs are disabled and the rest of the UI keeps working.
- Health endpoint: `GET /health` on the HTTPS port returns HTTP 200 with JSON `{"running":true}` when the dashboard can reach the API server.
- `GET /api/v1/integration/sidecar/state` returns JSON with `"connected": true` when the dashboard can reach the metrics scraper.
- Prometheus metrics: `GET /metrics`.

### metrics-scraper
- Listens on HTTP port 8000 (fixed in the code; the flag list has no port option).
- Every minute it lists node metrics and pod metrics for the whole cluster from the Metrics API (`metrics.k8s.io`) and stores them in the SQLite file `/tmp/metrics.db` (flag `--db-file`). Samples older than 15 minutes are deleted (flag `--metric-duration`). The file must be writable; it does not need to survive restarts.
- The Metrics API is provided by metrics-server, which is a separate cluster add-on and not part of this application. Without it the scraper keeps running and serving HTTP, logs scrape errors, and the dashboard shows no graphs.
- If the flag `--namespace` or the environment variable `POD_NAMESPACE` is set, the scraper only collects pod metrics for that namespace and skips node metrics. For cluster-wide graphs, set neither.
- Connects to the Kubernetes API server with in-cluster configuration unless `--kubeconfig` is given.
- Health check: any `GET` path that is not under `/api/v1/dashboard/`, for example `GET /healthz`, returns HTTP 200 with the body `URL: <path>`.

## Dependencies
- dashboard depends on the Kubernetes API server and, for graphs, on metrics-scraper.
- metrics-scraper depends on the Kubernetes API server and on the Metrics API (metrics-server), which must be installed separately.

## Permissions (Kubernetes API)
- dashboard, with its own service account, in its own namespace:
  - reads and updates the Secret `kubernetes-dashboard-csrf`;
  - reads the Secret `kubernetes-dashboard-key-holder`, and creates it when it does not exist;
  - reads the ConfigMap `kubernetes-dashboard-settings`, and creates it when it does not exist;
  - sends GET requests through the service proxy (`services/proxy`) to the `dashboard-metrics-scraper` Service.
- All other API requests from the dashboard are made with the logged-in user's token, so the dashboard's service account needs no further access to cluster resources.
- metrics-scraper lists node metrics and pod metrics in all namespaces from the `metrics.k8s.io` API.

## External access
- Users reach the dashboard's HTTPS port through `kubectl proxy` (the API server's service proxy) or `kubectl port-forward`. Exposing it outside the cluster is not required; the project describes NodePort exposure as suitable only for single-node development setups.
- The metrics scraper is internal only.
