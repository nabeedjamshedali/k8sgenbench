# Redaction log: P11_kube-state-metrics
Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.

## README.md -> docs_bundle/README.md
- **embedded Kubernetes manifest**: `apiVersion: apps/v1 kind: DaemonSet spec: template: spec: containers: - image: registry.k8s.io/kube-state-metrics/kube-state-metrics:IMAGE_TAG name: kube-state-metrics args: - --resources=pods - --nod`
- **embedded Kubernetes manifest**: `apiVersion: apps/v1 kind: Deployment spec: template: spec: containers: - image: registry.k8s.io/kube-state-metrics/kube-state-metrics:IMAGE_TAG name: kube-state-metrics args: - --resources=pods - --tr`
- **embedded Kubernetes manifest**: `apiVersion: v1 kind: ServiceAccount metadata: name: kube-state-metrics namespace: your-namespace-where-kube-state-metrics-will-deployed`
- **embedded Kubernetes manifest**: `apiVersion: rbac.authorization.k8s.io/v1 kind: RoleBinding metadata: name: kube-state-metrics namespace: project1 roleRef: apiGroup: rbac.authorization.k8s.io kind: ClusterRole name: view subjects: - `
- **Kubernetes-headed section**: `kube-state-metrics uses [`client-go`](https://github.com/kubernetes/client-go) to talk with Kubernetes clusters. The supported Kubernetes cluster version is determined by [`client-go`](https://github.`
- **Kubernetes-headed section**: `To deploy this project, you can simply run `kubectl apply -f examples/standard` and a Kubernetes service and deployment will be created. (Note: Adjust the apiVersion of some resource if your kubernete`

## docs/README.md -> docs_bundle/docs-README.md
- **embedded Kubernetes manifest**: `apiVersion: rbac.authorization.k8s.io/v1 kind: ClusterRole metadata: name: metrics-reader rules: - nonResourceURLs: - "/metrics" verbs: - get`
- **embedded Kubernetes manifest**: `apiVersion: rbac.authorization.k8s.io/v1 kind: ClusterRoleBinding metadata: name: metrics-reader-rolebinding roleRef: apiGroup: rbac.authorization.k8s.io kind: ClusterRole name: metrics-reader subject`
- **Kubernetes-headed section**: `Kube-State-Metrics' metrics can contain sensitive information about the state of the cluster, which you as an operator might want to additionally protect from unauthorized access. In order to achieve `
