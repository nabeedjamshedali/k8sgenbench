# Provenance: n8n with PostgreSQL

Repository: https://github.com/n8n-io/n8n-hosting at commit `7a22e91a7660e5e443c296d148f3ca8eec880aa3`.
No fact below is taken from `kubernetes/*.yaml`.

Upstream sources:
- n8n documentation: https://github.com/n8n-io/n8n-docs at commit `4a84a4229f694c8565dcd0a9cd0af37623fa2cbc` (published at https://docs.n8n.io). Paths below are relative to `docs/deploy/host-n8n/`; `ENV/` stands for `configure-n8n/basic-configuration/use-environment-variables/`.
- n8n source: https://github.com/n8n-io/n8n at tag `n8n@2.43.5`, commit `d811f5e87dfc164999f34d75b17017876d41a54a` (used only to confirm the health endpoints).
- PostgreSQL image documentation: https://hub.docker.com/_/postgres (image defaults).

| Spec fact | Source |
|---|---|
| Purpose: workflow automation platform | n8n-hosting `README.md` L3 |
| Web editor reached on port 5678 | n8n-docs `install-options/install-with-docker.md` L66, L89 |
| PostgreSQL instead of the default SQLite; stores credentials, executions, workflows | n8n-docs `install-options/install-with-docker.md` L93; n8n-hosting `README.md` L16 |
| Two components, n8n and postgres | n8n-hosting `docker-compose/withPostgres/README.md` L3; `docker-compose/withPostgres/docker-compose.yml` L6, L27 |
| Image `n8nio/n8n` | n8n-docs `install-options/install-with-docker.md` L71, L120, L135-138 (`docker pull n8nio/n8n:<version>`) |
| n8n version `2.43.5` | n8n-hosting `docker-compose/withPostgres/.env` L1, used as image tag in `docker-compose/withPostgres/docker-compose.yml` L28 |
| Image `postgres:18` | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L7; `README.md` L14 ("The templates here deploy **18**") |
| n8n listens on 5678; `N8N_PORT` default 5678; `N8N_PROTOCOL` default `http` | n8n-docs `ENV/deployment.md` L79, L81; n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L40-41 |
| `DB_TYPE=postgresdb`, default `sqlite` | n8n-docs `ENV/database.md` L32; n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L31 |
| `DB_POSTGRESDB_HOST` is the postgres address (compose uses its service name) | n8n-docs `ENV/database.md` L48; n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L32 |
| `DB_POSTGRESDB_PORT=5432` | n8n-docs `ENV/database.md` L49 (default 5432); n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L33 |
| `DB_POSTGRESDB_DATABASE=n8n` | n8n-docs `ENV/database.md` L47 (default `n8n`); n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L34 with `.env` L5 (`POSTGRES_DB=n8n`) |
| `DB_POSTGRESDB_USER` / `DB_POSTGRESDB_PASSWORD` must match a postgres account | n8n-docs `ENV/database.md` L50-51; n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L35-36 (set from the same variables passed to postgres at L13-14) |
| Account needs all privileges on database `n8n` and CREATE on schema `public` | n8n-hosting `docker-compose/withPostgres/init-data.sh` L8-9 |
| `N8N_ENCRYPTION_KEY` optional; random key generated on first launch | n8n-docs `ENV/deployment.md` L65; n8n-hosting `docker-compose/withPostgresAndWorker/docker-compose.yml` L19 (set explicitly in the queue-mode setup) |
| `/home/node/.n8n` holds the encryption key and must persist; credentials unreadable without it | n8n-docs `install-options/install-with-docker.md` L81, L96-98; `ENV/deployment.md` L76; n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L45; `docker-compose/withPostgres/README.md` L86-87 |
| n8n runs as UID/GID 1000; data directory must be writable by it | n8n-hosting `docker-compose/subfolderWithSSL/docker-compose.yml` L21-25 (`chown -R 1000:1000 /home/node/.n8n` before n8n starts), L58 |
| Task runner runs as child process by default (internal mode); no separate component required | n8n-docs `configure-n8n/set-up-task-runners.md` L65, L70; `ENV/task-runners.md` L37 (default `internal`) |
| `GET /healthz` returns 200 when reachable; `GET /healthz/readiness` returns 200 only when DB connected and migrated | n8n-docs `keep-n8n-running/monitor-n8n.md` L15, L22, L30; n8n source `packages/cli/src/abstract-server.ts` L151-153, L157-164; n8n-hosting `charts/n8n/README.md` L159 (chart documentation, not a manifest) |
| postgres listens on 5432 | PostgreSQL default; n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L33 |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` superuser created on first start, required by the image | PostgreSQL image documentation; n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L10-11; `.env` L3-4 |
| `POSTGRES_DB=n8n` | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L12; `.env` L5 |
| `PGDATA` must point into the mounted volume because postgres:18 moved its default data directory; compose uses `/var/lib/postgresql/data` | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L15-17; `docker-compose/withPostgres/README.md` L32-34 |
| Optional non-superuser account via `POSTGRES_NON_ROOT_USER` / `POSTGRES_NON_ROOT_PASSWORD` and an init script in `/docker-entrypoint-initdb.d/` | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L13-14, L20, L35-36; `docker-compose/withPostgres/init-data.sh` L5-10 |
| postgres data directory `/var/lib/postgresql/data` must persist | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L1-2, L19 (named volume `db_storage`); `docker-compose/withPostgres/README.md` L67-71 (database volume) |
| postgres health check `pg_isready` | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L21-22 |
| n8n depends on postgres and starts after it is healthy | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L46-48 |
| n8n reachable from outside on 5678 | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L40-41; n8n-docs `install-options/install-with-docker.md` L76 |
| postgres internal only | n8n-hosting `docker-compose/withPostgres/docker-compose.yml` L6-25 (no `ports`) |

## Excluded facts (appear only in the human manifests)
- Service names `postgres-service` and `n8n`, the headless postgres Service (`clusterIP: None`), the `LoadBalancer` Service type, and the namespace `n8n` (used in `DB_POSTGRESDB_HOST=postgres-service.n8n.svc.cluster.local`).
- Replica counts, the `Recreate` and `RollingUpdate` strategies, resource requests and limits, PVC sizes (2Gi and 300Gi), access modes and labels.
- The `busybox:1.36` init container that runs `chown 1000:1000`; the spec states only the UID requirement, sourced from the compose setup.
- The container command `sleep 5; n8n start`.
- `PGDATA=/var/lib/postgresql/data/pgdata` (the spec uses the compose value and allows a subdirectory).
- `POSTGRES_HOST` and `POSTGRES_PORT` on the postgres container, the unused `n8n-secret` and `postgres-secret` volumes, and the Secret values `changeNonRootUser` / `changeNonRootPassword`.
- The manifest's variant of the init script (psql variables, `ALTER ROLE ... LOGIN`, `GRANT ALL ON SCHEMA public`); the spec describes the compose script's grants.

## Not included although present in non-manifest sources
- The external task runner (`n8nio/runners`, `N8N_RUNNERS_MODE=external`, `N8N_RUNNERS_AUTH_TOKEN`, port 5679) used by all compose setups (`docker-compose/withPostgres/docker-compose.yml` L37-39, L50-57). Left out so that the scope matches the two-component application under study; the spec states that the default internal mode needs no extra component.
- `GENERIC_TIMEZONE`, `TZ`, `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS` from the docs' `docker run` example: not required for operation.
