# Redaction log: P02_n8n
Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.

## README.md -> docs_bundle/README.md
- **Kubernetes-headed section**: `The official n8n Helm chart for production Kubernetes deployments. ```bash helm install n8n oci://ghcr.io/n8n-io/n8n-helm-chart/n8n -f my-values.yaml ``` See the [chart README](./charts/n8n/README.md)`
- **Kubernetes-headed section**: `See [`kubernetes/`](./kubernetes/) for raw Kubernetes manifest examples used in cloud provider tutorials (AWS, Azure, GCP).`

## kubernetes/README.md -> docs_bundle/kubernetes-README.md
- **Kubernetes-headed section**: `> **For production Kubernetes deployments, use the official [n8n Helm chart](../charts/n8n/).** The raw manifests below are intended for tutorial-based deployments and simple setups. Get up and runnin`
- **Kubernetes-headed section**: `kubectl scale deploy/n8n --replicas=0 -n n8n`
- **Kubernetes-headed section**: `grep -q "PostgreSQL database cluster dump complete" n8n-backup.sql \ && kubectl delete deploy/postgres pvc/postgresql-pv -n n8n \ && kubectl apply -f postgres-claim0-persistentvolumeclaim.yaml -f post`
- **Kubernetes-headed section**: `kubectl scale deploy/n8n --replicas=1 -n n8n ``` One thing specific to this setup, which that guide cannot tell you: **only `postgresql-pv` should be deleted.** Keep the `n8n-claim0` claim, it holds n`

## docker-compose/withPostgres/docker-compose.yml -> docs_bundle/docker-compose-withPostgres.yml
- no redactions

## docker-compose/withPostgres/.env -> docs_bundle/withPostgres.env
- no redactions

## docker-compose/withPostgres/init-data.sh -> docs_bundle/init-data.sh
- no redactions
