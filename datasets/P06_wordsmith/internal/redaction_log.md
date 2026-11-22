# Redaction log: P06_wordsmith
Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.

## README.md -> docs_bundle/README.md
- **Kubernetes-headed section**: `You can deploy the same app to Kubernetes using the [Kustomize configuration](./kustomization.yaml). It will define all of the necessary Deployment and Service objects and a ConfigMap to provide the d`

## docker-compose.yml -> docs_bundle/docker-compose.yml
- **excluded fact: api replica count (also in README, excluded per the no-replica-count rule)**: `replicas: 5`

## api/Dockerfile -> docs_bundle/api.Dockerfile
- no redactions

## web/Dockerfile -> docs_bundle/web.Dockerfile
- no redactions
