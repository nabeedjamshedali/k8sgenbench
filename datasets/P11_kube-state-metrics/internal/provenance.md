# Provenance: kube-state-metrics

Repository: https://github.com/kubernetes/kube-state-metrics at commit `8f320e506f530d171b5c1d1e9ed46292396e6768`.
No fact below is taken from `examples/standard/`.

| Spec fact | Source |
|---|---|
| Purpose: listens to the API server, generates metrics about object state (deployments, nodes, pods) | `README.md` L10-14 |
| Metrics served as plaintext at `/metrics` for Prometheus or compatible scrapers | `README.md` L25-28 |
| Does not store or forward metrics itself | `README.md` L210-212 |
| Image `registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.20.0` | `README.md` L101 (Container Image section); also L300, L322 |
| Single Go process | `README.md` L72 (uses `client-go`), L350-353 (`go get`); `Dockerfile` L12, L16 (one binary as entrypoint) |
| Main port 8080, `/metrics`, `--port` default 8080 | `README.md` L25-26; `docs/developer/cli-arguments.md` L75 |
| Telemetry port 8081, self metrics, `--telemetry-port` default 8081 | `README.md` L145-147; `docs/developer/cli-arguments.md` L86 |
| Image entrypoint `--port=8080 --telemetry-port=8081`; ports exposed | `Dockerfile` L16, L18 |
| `/healthz` and `/livez` on main port, `/readyz` on telemetry port, and their meaning and probe recommendations | `README.md` L392-398 |
| `--resources` and its default list | `docs/developer/cli-arguments.md` L76 |
| `--namespaces` empty by default | `docs/developer/cli-arguments.md` L68 |
| `--auth-filter`, off by default; TokenReview and SubjectAccessReview per scrape | `docs/developer/cli-arguments.md` L44; `docs/README.md` L117-120 |
| No persistence; snapshot held in memory | `README.md` L210-211 ("It holds an entire snapshot of Kubernetes state in memory") |
| Runs in a pod with a service account token with read-only access to the cluster | `README.md` L367-368 |
| Lists and watches the exported resources | `internal/store/builder.go` L744-755 (client-go reflector over a ListWatch); `internal/store/pod.go` L2050-2058 (List/Watch on pods); `docs/developer/guide.md` L18 (resources are granted the verbs `list` and `watch`) |
| All namespaces (cluster-wide) by default | `docs/developer/cli-arguments.md` L68 (`--namespaces` defaults to ""); `README.md` L402-434 (restricting to namespaces is the special "limited privileges" setup) |
| API group of each default resource | Go API import in each store file: core `k8s.io/api/core/v1` (`configmap.go` L22, `limitrange.go` L22, `namespace.go` L27, `node.go` L29, `persistentvolumeclaim.go` L28, `persistentvolume.go` L28, `pod.go` L32, `replicationcontroller.go` L23, `resourcequota.go` L22, `secret.go` L23, `service.go` L22); `apps/v1` (`daemonset.go` L22, `deployment.go` L27, `replicaset.go` L28, `statefulset.go` L27); `batch/v1` (`cronjob.go` L31, `job.go` L28); `autoscaling/v2` (`horizontalpodautoscaler.go` L22); `certificates/v1` (`certificatesigningrequest.go` L27); `coordination/v1` (`lease.go` L22); `discovery/v1` (`endpointslice.go` L25); `networking/v1` (`ingress.go` L28, `networkpolicy.go` L22); `policy/v1` (`poddisruptionbudget.go` L22); `storage/v1` (`storageclass.go` L25, `volumeattachment.go` L22); `admissionregistration/v1` (`mutatingadmissionpolicy.go`, `mutatingadmissionpolicybinding.go`, `mutatingwebhookconfiguration.go`, `validatingadmissionpolicy.go`, `validatingadmissionpolicybinding.go`, `validatingwebhookconfiguration.go`, all L22). All files under `internal/store/`. The Go package `k8s.io/api/<x>/v1` corresponds to API group `<x>.k8s.io` for certificates, coordination, discovery, networking, storage and admissionregistration, and to `apps`, `batch`, `autoscaling`, `policy` and core as named. |
| Dependency on the API server only | `README.md` L10, L367-368 |
| Both ports scraped by Prometheus from inside the cluster | `README.md` L380 ("a specific Prometheus scrape config ... that picks up both metrics endpoints") |
| No external access required | Judgement: `README.md` L380 and `docs/README.md` L117 describe the metrics as sensitive and scraped by Prometheus; no doc asks for external exposure |

## Excluded facts (appear only in the human manifests)
- Namespace `kube-system`, object names, labels (`app.kubernetes.io/*`), replica count 1, headless Service (`clusterIP: None`), port names `http-metrics` and `telemetry`.
- Probe settings (liveness on `/livez` via the main port, readiness on `/readyz` via the telemetry port, delays and timeouts). The endpoints themselves are in the spec from `README.md`; the probe configuration is not.
- securityContext (`runAsUser: 65534`, read-only root filesystem, dropped capabilities, seccomp), `automountServiceAccountToken` settings, `nodeSelector: kubernetes.io/os: linux`.
- The ClusterRole rules as written. Note that the human ClusterRole also grants `list`/`watch` on serviceaccounts, endpoints, ingressclasses and the RBAC resources (roles, rolebindings, clusterroles, clusterrolebindings), which are optional (non-default) resources per `docs/README.md` L69-77, and `create` on tokenreviews and subjectaccessreviews, which are used only with `--auth-filter`. These are not in the spec as requirements.

## Notes
- `docs/README.md` L41 lists Endpoint metrics under "Default Resources" and L73 lists EndpointSlice under "Optional Resources", which contradicts the generated `--help` output in `docs/developer/cli-arguments.md` L76 (default includes `endpointslices`, not `endpoints`). The spec follows `cli-arguments.md`, which is generated from the binary.
- README L226-227 recommends 250MiB memory and 0.1 cores; per the rules, resource values are not in the spec.
