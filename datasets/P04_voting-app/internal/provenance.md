# Provenance: Example Voting App

Repository: https://github.com/dockersamples/example-voting-app at commit `63e9150ca17af4ed05880d4245e486481f73fcb4`.
No fact below is taken from `k8s-specifications/`.

| Spec fact | Source |
|---|---|
| Purpose, five components and their roles | `README.md` L9, L53-57 |
| Images of vote, result, worker | `docker-compose.images.yml` L9, L20, L31 |
| Images `redis:alpine`, `postgres:15-alpine` | `docker-compose.images.yml` L41, L51; `docker-compose.yml` L55, L65 |
| vote listens on port 80 | `vote/Dockerfile` L29 (`EXPOSE 80`), L32 (gunicorn `-b 0.0.0.0:80`) |
| vote connects to hostname `redis` | `vote/app.py` L21 |
| `OPTION_A` / `OPTION_B` and defaults | `vote/app.py` L9-10 |
| vote health check `GET /` | `docker-compose.yml` L13-14 |
| result listens on port 80 | `result/Dockerfile` L21-22 |
| result connection string to `db` | `result/server.js` L21 |
| worker connects to `redis` and `db` with credentials | `worker/Program.cs` L19-20 |
| worker has no listening port | `worker/Dockerfile` (no `EXPOSE`); `docker-compose.yml` L43-52 (no `ports`) |
| redis port 6379 | Redis default port; `worker/Program.cs` L20 connects without a port override |
| redis health check `redis-cli ping` | `healthchecks/redis.sh` |
| db credentials `postgres`/`postgres` | `docker-compose.yml` L66-68 |
| db port 5432 | PostgreSQL default; `result/server.js` L21 uses no port override |
| db data directory and persistence | `docker-compose.yml` L69-70 (named volume `db-data`), L91-92; `README.md` L56 ("backed by a Docker volume") |
| db health check `SELECT 1` | `healthchecks/postgres.sh` |
| Dependencies | `docker-compose.yml` L10-12, L31-33, L46-50 |
| vote and result reachable from outside | `README.md` L17 (vote at :8080, results at :8081); `docker-compose.yml` L21-22, L36-37 |
| redis, db and worker internal only | `docker-compose.yml`: no `ports` on these services; `back-tier` network only (L51-52, L61-62, L75-76) |

## Excluded facts (appear only in the human manifests)
- NodePorts 31000 and 31001, Service types, replica counts, labels, and the use of `emptyDir` for the database volume.
