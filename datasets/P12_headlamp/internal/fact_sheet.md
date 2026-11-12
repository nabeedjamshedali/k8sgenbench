# Headlamp

## Purpose
Headlamp is a web UI for Kubernetes. It is deployed inside the cluster it manages and lets users list, view, create, edit and delete cluster resources, view logs and open terminals in containers from a browser. A single container runs a Go backend that serves the web front end and proxies the UI's requests to the Kubernetes API server.

## Components

| Component | Image | Role |
|---|---|---|
| headlamp | `ghcr.io/headlamp-k8s/headlamp` (tag `latest`, or a release tag `vX.Y.Z`) | Web UI and backend server |

## Component details

### headlamp
- Listens on HTTP port 4466. The image starts `/headlamp/headlamp-server` with the bundled front end and plugins directory already configured, and runs as a non-root user.
- In-cluster mode is required: the server must be started with the `-in-cluster` flag (or the environment variable `HEADLAMP_CONFIG_IN_CLUSTER=true`). Every server flag can also be set as an environment variable named `HEADLAMP_CONFIG_<FLAG>` (upper case, `-` replaced by `_`); a flag takes priority over the environment variable.
- In in-cluster mode Headlamp builds its connection to the cluster from the pod's standard in-cluster configuration (API server address, CA certificate and service-account token mounted into the pod). The service-account token must therefore be mounted into the pod. No kubeconfig file is needed.
- Optional flags for additional features: `-oidc-client-id`, `-oidc-client-secret`, `-oidc-idp-issuer-url`, `-oidc-callback-url`, `-oidc-scopes` (log-in through an OpenID Connect provider), `-base-url` (serve under a path prefix such as `/headlamp`), `-tls-cert-path` / `-tls-key-path` (terminate TLS in the container instead of at the ingress). None of these is required.
- Optional environment variable `HEADLAMP_CONFIG_METRICS_ENABLED=true` enables a Prometheus metrics endpoint at `/metrics` on port 4466.
- Persistence: none required. Headlamp keeps its in-cluster context in memory and writes no kubeconfig file; the front end and plugins are part of the image.
- Health: there is no dedicated health endpoint. `GET /` on port 4466 returns the web UI, and `GET /config` returns the backend's JSON configuration, including the in-cluster cluster.

## Authentication and Kubernetes API permissions
- Users log in by pasting a bearer token (the documented way is a ServiceAccount token created for the user) or through OIDC if it is configured. Headlamp sends each user's own credentials to the Kubernetes API server, so what a user can see and change is decided by the RBAC permissions of that user's token.
- Headlamp does not use its own service account to access cluster resources on behalf of users.
- At start-up, Headlamp tries to read the ConfigMap `kubeadm-config` in namespace `kube-system` with the pod's service account to name its cluster context. If the read is not allowed or the ConfigMap does not exist, the context is named `main`. This read is optional.

## Dependencies
- The Kubernetes API server of the cluster Headlamp runs in. No other services are required.

## External access
- The web UI on port 4466 must be reachable by users from outside the cluster (the maintainers expose it through an ingress).
