# Example Voting App

## Purpose
A distributed voting application. Users vote between two options in a web page; votes are queued in Redis, a background worker moves them into PostgreSQL, and a second web page shows the results in real time.

## Components

| Component | Image | Role |
|---|---|---|
| vote | `dockersamples/examplevotingapp_vote` | Python (Flask/gunicorn) web front end where users cast votes |
| result | `dockersamples/examplevotingapp_result` | Node.js web app that shows live results |
| worker | `dockersamples/examplevotingapp_worker` | .NET background worker that consumes votes from Redis and stores them in PostgreSQL |
| redis | `redis:alpine` | Queue that collects new votes |
| db | `postgres:15-alpine` | PostgreSQL database that stores the votes |

## Component details

### vote
- Listens on HTTP port 80.
- Connects to Redis at hostname `redis` on the default Redis port 6379. The hostname is fixed in the application code.
- Optional environment variables: `OPTION_A` (default `Cats`) and `OPTION_B` (default `Dogs`), the two voting options.
- Health check: `GET /` on port 80 returns HTTP 200.

### result
- Listens on HTTP port 80 (the image sets `PORT=80`).
- Connects to PostgreSQL at hostname `db` on port 5432, user `postgres`, password `postgres`, database `postgres`. These connection settings are fixed in the application code.

### worker
- No listening port.
- Connects to Redis at hostname `redis` and to PostgreSQL at hostname `db` with user `postgres` and password `postgres`. These settings are fixed in the application code.

### redis
- Listens on port 6379.
- Health check: `redis-cli ping` returns `PONG`.

### db
- Listens on port 5432.
- Environment variables: `POSTGRES_USER=postgres` and `POSTGRES_PASSWORD=postgres` (required, because the other components use these credentials).
- Persistence: the data directory `/var/lib/postgresql/data` must be stored on a persistent volume so that votes survive restarts.
- Health check: `psql` query `SELECT 1` succeeds.

## Dependencies
- vote depends on redis.
- result depends on db.
- worker depends on redis and db.

## External access
- The vote web page (port 80) and the result web page (port 80) must be reachable from outside the cluster.
- redis, db and worker are internal only.
