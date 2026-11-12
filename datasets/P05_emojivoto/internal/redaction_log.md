# Redaction log: P05_emojivoto
Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.

## README.md -> docs_bundle/README.md
- **Kubernetes-headed section**: `Deploy the application to Minikube using the Linkerd2 service mesh. 1. Install the `linkerd` CLI ```bash curl https://run.linkerd.io/install | sh ``` 1. Install Linkerd2 ```bash linkerd install | kube`
- **Kubernetes-headed section**: `To deploy standalone to an existing cluster: ```bash kubectl apply -k github.com/BuoyantIO/emojivoto/kustomize/deployment ````
- **Kubernetes-headed section**: `The `emoji` and `voting` services are [gRPC](https://grpc.io/) applications which have [Protocol Buffers (protobuf)](https://developers.google.com/protocol-buffers) definition files. These `.proto` fi`
- **Kubernetes-headed section**: `The `web-svc` deployment of emojivoto is a React application that is hosted by a Go server. We can use [`linkerd profile auto creation`](https://linkerd.io/2/tasks/setting-up-service-profiles/#auto-cr`

## docker-compose.yml -> docs_bundle/docker-compose.yml
- no redactions

## Dockerfile-multi-arch -> docs_bundle/Dockerfile-multi-arch
- no redactions
