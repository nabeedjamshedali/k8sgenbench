# kube-state-metrics

## Purpose
A cluster add-on that listens to the Kubernetes API server and generates Prometheus metrics about the state of Kubernetes objects such as deployments, nodes and pods. It exposes the metrics as plaintext on an HTTP `/metrics` endpoint for Prometheus or a compatible scraper. It does not store or forward metrics itself.

## Components

| Component | Image | Role |
|---|---|---|
| kube-state-metrics | `registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.20.0` | Single Go process that watches the Kubernetes API and serves metrics about object state |

## Component details

### kube-state-metrics
- Listens on HTTP port 8080 (main port), which serves the object-state metrics at `/metrics`. Configured with `--port` (default 8080).
- Listens on HTTP port 8081 (telemetry port), which serves the exporter's own process and list/watch metrics at `/metrics`. Configured with `--telemetry-port` (default 8081).
- The image's entrypoint already starts the process with `--port=8080 --telemetry-port=8081`; no further arguments or environment variables are required.
- Health endpoints:
  - `GET /healthz` on port 8080 returns 200 if the application is running (recommended for a startup probe).
  - `GET /livez` on port 8080 returns 200 if the application is not affected by an outage of the Kubernetes API server (recommended for a liveness probe).
  - `GET /readyz` on port 8081 returns 200 when the application is ready to expose metrics (recommended for a readiness probe).
- Optional command-line arguments: `--resources` (comma-separated list of resource types to export; defaults to the list below), `--namespaces` (namespaces to watch; empty by default, meaning all namespaces), `--auth-filter` (off by default; when enabled, every scrape is authenticated and authorized through TokenReview and SubjectAccessReview requests to the API server).
- Persistence: none. The application holds a snapshot of cluster state in memory and rebuilds it from the API server after a restart.

## Kubernetes API access
kube-state-metrics runs inside a pod and talks to the Kubernetes API server with the pod's service account token; it needs read-only access to the cluster. With the default configuration it lists and watches the following resource types in all namespaces (cluster-wide):

| API group | Resources |
|---|---|
| core (`""`) | configmaps, limitranges, namespaces, nodes, persistentvolumeclaims, persistentvolumes, pods, replicationcontrollers, resourcequotas, secrets, services |
| `apps` | daemonsets, deployments, replicasets, statefulsets |
| `batch` | cronjobs, jobs |
| `autoscaling` | horizontalpodautoscalers |
| `certificates.k8s.io` | certificatesigningrequests |
| `coordination.k8s.io` | leases |
| `discovery.k8s.io` | endpointslices |
| `networking.k8s.io` | ingresses, networkpolicies |
| `policy` | poddisruptionbudgets |
| `storage.k8s.io` | storageclasses, volumeattachments |
| `admissionregistration.k8s.io` | mutatingadmissionpolicies, mutatingadmissionpolicybindings, mutatingwebhookconfigurations, validatingadmissionpolicies, validatingadmissionpolicybindings, validatingwebhookconfigurations |

## Dependencies
- The Kubernetes API server (in-cluster). No other components.

## Access
- Both ports (8080 and 8081) must be reachable from inside the cluster so that Prometheus can scrape both metrics endpoints.
- No access from outside the cluster is required.
