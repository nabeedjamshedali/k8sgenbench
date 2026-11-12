# n8n with PostgreSQL

## Purpose
n8n is a workflow automation platform. Users build and run workflows in a web editor. In this setup n8n stores its workflows, credentials and execution history in a PostgreSQL database instead of its bundled SQLite file.

## Components

| Component | Image | Role |
|---|---|---|
| n8n | `n8nio/n8n:2.43.5` | Application that serves the web editor and API and runs workflows |
| postgres | `postgres:18` | PostgreSQL database that stores n8n's data |

## Component details

### n8n
- Listens on HTTP port 5678 (`N8N_PORT`, default `5678`; `N8N_PROTOCOL`, default `http`).
- Required environment variables:
  - `DB_TYPE=postgresdb` (the default is `sqlite`, which would not use PostgreSQL).
  - `DB_POSTGRESDB_HOST`: the address at which n8n reaches the postgres component. The value is up to you.
  - `DB_POSTGRESDB_PORT=5432`.
  - `DB_POSTGRESDB_DATABASE=n8n`.
  - `DB_POSTGRESDB_USER` and `DB_POSTGRESDB_PASSWORD`: a PostgreSQL account with full privileges on the `n8n` database and permission to create objects in its `public` schema. This can be the PostgreSQL superuser or a separate non-superuser account (see postgres below). The values are up to you, but they must match an account that exists in postgres.
- Optional environment variable: `N8N_ENCRYPTION_KEY`, the key used to encrypt stored credentials. If it is not set, n8n generates a random key on first start and saves it in its data directory.
- Persistence: the directory `/home/node/.n8n` holds the encryption key and other instance data, and must be stored on a persistent volume. Without it, credentials saved in the database become unreadable after a restart.
- The image runs as the `node` user (UID 1000 and GID 1000); the data directory must be writable by that user.
- Code nodes run in a task runner that n8n starts as a child process by default (internal mode); no separate runner component is required.
- Health checks: `GET /healthz` on port 5678 returns HTTP 200 when the instance is reachable. `GET /healthz/readiness` returns HTTP 200 only when the database is connected and migrated.

### postgres
- Listens on port 5432.
- Environment variables:
  - `POSTGRES_USER` and `POSTGRES_PASSWORD`: the superuser account created on first start (required by the image).
  - `POSTGRES_DB=n8n`: the database created on first start, which n8n uses.
  - `PGDATA`: `postgres:18` changed its default data directory. Set `PGDATA` to `/var/lib/postgresql/data` (or a directory below it) so that the data lands in the persistent volume described below.
- Optional separate account for n8n: the project's Docker Compose setup does not let n8n log in as the superuser. It passes `POSTGRES_NON_ROOT_USER` and `POSTGRES_NON_ROOT_PASSWORD` to the postgres container and runs an initialisation script from `/docker-entrypoint-initdb.d/` on first start that creates this user and grants it all privileges on the `n8n` database and `CREATE` on schema `public`. n8n then connects with this account.
- Persistence: the data directory `/var/lib/postgresql/data` must be stored on a persistent volume so that workflows, credentials and executions survive restarts.
- Health check: `pg_isready -h localhost -U <POSTGRES_USER> -d n8n` succeeds.

## Dependencies
- n8n depends on postgres. It should start after postgres accepts connections.

## External access
- The n8n web editor and API (port 5678) must be reachable from outside the cluster.
- postgres is internal only.
