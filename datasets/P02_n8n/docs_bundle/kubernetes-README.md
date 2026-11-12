# n8n-kubernetes-hosting
[Kubernetes deployment instructions removed from this bundle]
## Prerequisites

Self-hosting n8n requires technical knowledge, including:

* Setting up and configuring servers and containers
* Managing application resources and scaling
* Securing servers and applications
* Configuring n8n

n8n recommends self-hosting for expert users. Mistakes can lead to data loss, security issues, and downtime. If you aren't experienced at managing servers, n8n recommends [n8n Cloud](https://n8n.io/cloud/).

## Upgrade Considerations

### PostgreSQL 18

`postgres-deployment.yaml` runs `postgres:18`.

**Installing fresh:** nothing to do. Apply the manifests as usual.

**Upgrading an existing cluster:** this is a major version upgrade and it is breaking. Postgres 18
cannot open a data directory written by 16, and moving the folder does not help, because the check
is on the format and not the path. The pod stays in `CrashLoopBackOff` with
`FATAL: database files are incompatible with server`. Nothing is deleted, and you can pin the image
back to `postgres:16` at any point.

Follow the official guide,
[Upgrading a PostgreSQL Cluster](https://www.postgresql.org/docs/18/upgrading.html). It covers the
three supported methods and which to pick.

For a small cluster, dump and restore is usually simplest. n8n is offline while you do it:

```bash
# 0. The Postgres superuser name, as set in postgres-secret.yaml
POSTGRES_USER=changeUser

# 1. Export, with the old image still running
kubectl exec -n n8n deploy/postgres -- pg_dumpall -U "$POSTGRES_USER" > n8n-backup.sql

# 2. Check the export worked. This must print 1
grep -c "PostgreSQL database cluster dump complete" n8n-backup.sql

# 3. Stop n8n, so it cannot rebuild its schema against the empty database and
#    collide with the import
[Kubernetes deployment instructions removed from this bundle]
# 4. Delete Postgres and ONLY its claim, then recreate just Postgres. The guard
#    repeats the check, so a failed export stops here instead of deleting
[Kubernetes deployment instructions removed from this bundle]
# 5. Import
kubectl exec -i -n n8n deploy/postgres -- psql -U "$POSTGRES_USER" -d n8n < n8n-backup.sql

# 6. Import done, start n8n again
[Kubernetes deployment instructions removed from this bundle]
## Contributions

Please open PRs to the `main` branch.
