# Redaction log: P12_headlamp
Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.

## README.md -> docs_bundle/README.md
- no redactions

## docs/installation/in-cluster/index.md -> docs_bundle/in-cluster-install.md
- **embedded Kubernetes manifest**: `config: clusterInventory: enabled: true accessProvidersConfig: providers: - name: secretreader execConfig: apiVersion: client.authentication.k8s.io/v1 command: /access-plugins/secretreader/bin/secretr`
- **Kubernetes-headed section**: `We also maintain a simple/vanilla [file](https://github.com/kubernetes-sigs/headlamp/blob/main/kubernetes-headlamp.yaml) for setting up a Headlamp deployment and service. Be sure to review it and chan`
- **Kubernetes-headed section**: `When Headlamp runs with the `-in-cluster` flag (the default for the Helm chart and the sample deployment YAML), it automatically creates a cluster context named `main` from the pod's service account. `
- **Kubernetes-headed section**: `If you need to use more than one kubeconfig file at the same time, you can list each file path with a ":" separator in the `-kubeconfig` argument: ```yaml config: extraArgs: - -kubeconfig=/headlamp/ku`
- **Kubernetes-headed section**: `With the instructions in the previous section, the Headlamp service should be running, but you still need the ingress server as mentioned. We provide a sample ingress YAML file for this purpose, but y`

## Dockerfile -> docs_bundle/Dockerfile
- no redactions
