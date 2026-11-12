# Provenance: Emoji.voto

Repository: https://github.com/BuoyantIO/emojivoto at commit `9799218dbc08ff716554557f53fa71f181c98ff8`.
No fact below is taken from `kustomize/` or `training/`.

| Spec fact | Source |
|---|---|
| Purpose: vote for emoji, leaderboard; web front end + REST API, emoji gRPC API, voting gRPC API | `README.md` L3-10 |
| web is a Go server hosting a React front end | `README.md` L151 ("written with React and bundled with webpack"); `emojivoto-web/cmd/server.go`; `emojivoto-web/web/web.go` L398-424 |
| vote-bot generates traffic by voting through the web API, deployed with the app | `README.md` L72-81; `emojivoto-web/cmd/vote-bot/main.go` L114-129 |
| vote-bot rate about one vote per second (`REQUEST_RATE` default 1) | `emojivoto-web/cmd/vote-bot/main.go` L61-64, L112 |
| Images `buoyantio/emojivoto-web:v11`, `buoyantio/emojivoto-emoji-svc:v11`, `buoyantio/emojivoto-voting-svc:v11` | `docker-compose.yml` L5, L26, L33; published to Docker Hub per `README.md` L119-124 and `common.mk` L23-25 |
| vote-bot uses the web image with a different command | `docker-compose.yml` L17-19 (`image: buoyantio/emojivoto-web:v11`, `entrypoint: emojivoto-vote-bot`); `emojivoto-web/Makefile` L15-18 (vote-bot binary built into the web image) |
| Default entrypoint of the web image starts the web server | `Dockerfile-multi-arch` L45-51 (`ENTRYPOINT $SVC_NAME`, `svc_name=emojivoto-web` from `emojivoto-web/Makefile` L1); `common.mk` L27-28 |
| web listens on `WEB_PORT`; value 8080 | `emojivoto-web/cmd/server.go` L23; `emojivoto-web/web/web.go` L420; `docker-compose.yml` L7, L11-12; `README.md` L62, L178 |
| `EMOJISVC_HOST`, `VOTINGSVC_HOST` are `host:port` gRPC addresses | `emojivoto-web/cmd/server.go` L24-25, L66-71, L77-80 (`grpc.NewClient(host)`); `docker-compose.yml` L8-9 (`emoji-svc:8080`, `voting-svc:8080`); `README.md` L179-180 |
| web exits if `WEB_PORT`, `EMOJISVC_HOST` or `VOTINGSVC_HOST` unset | `emojivoto-web/cmd/server.go` L33-35 |
| `INDEX_BUNDLE` is the bundle served at `/js`; value `dist/index_bundle.js` | `emojivoto-web/cmd/server.go` L26; `emojivoto-web/web/web.go` L366-373, L411; `docker-compose.yml` L10 |
| Bundle at `dist/index_bundle.js` relative to the image working directory | `emojivoto-web/webapp/webpack.config.js` L7-9; `emojivoto-web/Makefile` L10-13 (dist copied into `target/`); `Dockerfile-multi-arch` L46, L50 (`target/` copied to `/usr/local/bin`, `WORKDIR /usr/local/bin`) |
| Without `INDEX_BUNDLE` the script does not load | `emojivoto-web/web/web.go` L366-372 (`ReadFile` of the empty path panics in the `/js` handler) |
| `MESSAGE_OF_THE_DAY` | `emojivoto-web/web/web.go` L350, L399 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` (all components) | `emojivoto-web/cmd/server.go` L28, L38-46; `emojivoto-emoji-svc/cmd/server.go` L32, L42-47; `emojivoto-voting-svc/cmd/server.go` L34, L48-53; `emojivoto-web/cmd/vote-bot/main.go` L35, L67-72 |
| web HTTP routes `/`, `/api/list`, `/api/vote?choice=`, `/api/leaderboard` | `emojivoto-web/web/web.go` L409-415, L99; `emojivoto-web/webapp/js/components/Vote.jsx` L34, L50; `emojivoto-web/webapp/js/components/Leaderboard.jsx` L19; `emojivoto-web/cmd/vote-bot/main.go` L137, L170 |
| `:doughnut:` is a valid shortcode | `emojivoto-emoji-svc/emoji/emoji.go` L22 |
| emoji listens for gRPC on `GRPC_PORT`; value 8080; exits if unset | `emojivoto-emoji-svc/cmd/server.go` L30, L37-39, L72; `docker-compose.yml` L27-28 |
| voting listens for gRPC on `GRPC_PORT`; value 8080; exits if unset | `emojivoto-voting-svc/cmd/server.go` L32, L43-45, L78; `docker-compose.yml` L34-35 |
| `PROM_PORT` optional, `/metrics` on that port, documented port 8801 | `emojivoto-emoji-svc/cmd/server.go` L31, L79-87; `emojivoto-voting-svc/cmd/server.go` L33, L85-93; `README.md` L141-145 |
| Metric `emojivoto_votes_total` | `emojivoto-voting-svc/voting/poll.go` L65-68 |
| `FAILURE_RATE` (doughnut votes only), `ARTIFICIAL_DELAY`, defaults | `emojivoto-voting-svc/cmd/server.go` L35-38, L104-106, L127-149; `emojivoto-voting-svc/api/api.go` L26-47 |
| emoji list kept in memory | `emojivoto-emoji-svc/emoji/emoji.go` L15-16, L134-140 |
| votes kept in memory only, no persistence | `emojivoto-voting-svc/voting/poll.go` L30-34, L70-76 (`inMemoryPoll`); `docker-compose.yml` (no volumes) |
| vote-bot has no listening port | `emojivoto-web/cmd/vote-bot/main.go` (HTTP client only, no listener); `docker-compose.yml` L17-23 (no `ports`) |
| `WEB_HOST` required `host:port` of web; exits if unset | `emojivoto-web/cmd/vote-bot/main.go` L45-48, L100; `docker-compose.yml` L21 (`web:8080`); `README.md` L86, L195 |
| `REQUEST_RATE`, `TTL`, `HOST_OVERRIDE` | `emojivoto-web/cmd/vote-bot/main.go` L50, L52-64, L139-141 |
| Dependencies | `docker-compose.yml` L13-15, L22-23; `emojivoto-web/cmd/server.go` L66-71 |
| web reachable from outside on 8080 | `README.md` L46-50 ("Use the app!"), L62 ("The web app will be running on port 8080 of your docker host"); `docker-compose.yml` L11-12 |
| emoji, voting, vote-bot need not be reachable from outside | `README.md` L6-10 (only web is the front end; the others are back-end APIs); `emojivoto-web/cmd/server.go` L66-71 (web is their client) |
| No dedicated health endpoint; `GET /` serves the page | `emojivoto-web/web/web.go` L330-364, L409 (route list has no health route); `emojivoto-emoji-svc/cmd/server.go`, `emojivoto-voting-svc/cmd/server.go` (no gRPC health service registered) |

## Excluded facts (appear only in the human manifests)
- The registry prefix `docker.l5d.io/` on the images (the repository documents only the Docker Hub names `buoyantio/...`; see note below).
- Service names `emoji-svc`, `voting-svc`, `web-svc`, the namespace `emojivoto`, the concrete values `emoji-svc.emojivoto:8080`, `voting-svc.emojivoto:8080`, `web-svc.emojivoto:80`.
- Service port 80 for web (targetPort 8080), Service type `ClusterIP`, replica counts, CPU requests, labels, ServiceAccounts, and `PROM_PORT=8801` being set on emoji and voting.

## Notes
- The compose file publishes the emoji and voting gRPC ports to the host (L29-30, L36-37). The spec does not require external access for them because the README describes web as the only front end; this is a judgement.
- The hostnames used in compose (`emoji-svc`, `voting-svc`, `web`) are not fixed in code: each address comes from an environment variable with no default, so the spec leaves the names to the generator.
- The human manifests pull `docker.l5d.io/buoyantio/...:v11`, the spec uses `buoyantio/...:v11`. Both carry the project's v11 images (digest equality was not verified). `requirements.py` strips the `docker.l5d.io/` prefix before matching.
