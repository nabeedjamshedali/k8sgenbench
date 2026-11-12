# Emoji.voto

## Purpose
A microservice application where users vote for their favourite emoji and see the votes on a leaderboard. A Go web server serves a React front end and a REST API; it calls two gRPC back-end services, one that lists and finds emoji and one that records votes and returns the leaderboard. A bundled traffic generator (vote-bot) casts votes continuously through the web API.

## Components

| Component | Image | Role |
|---|---|---|
| web | `buoyantio/emojivoto-web:v11` | Web front end and REST API; calls the emoji and voting services over gRPC |
| emoji | `buoyantio/emojivoto-emoji-svc:v11` | gRPC API for listing and finding emoji |
| voting | `buoyantio/emojivoto-voting-svc:v11` | gRPC API for casting votes and reading the leaderboard |
| vote-bot | `buoyantio/emojivoto-web:v11` (same image as web, different command) | Traffic generator that lists the emoji and votes through the web API about once per second |

## Component details

### web
- Listens on HTTP port 8080. The port is set by the required environment variable `WEB_PORT`; set `WEB_PORT=8080`.
- Required environment variable `EMOJISVC_HOST`: the `host:port` address of the emoji service's gRPC port.
- Required environment variable `VOTINGSVC_HOST`: the `host:port` address of the voting service's gRPC port.
- The server exits at start-up if `WEB_PORT`, `EMOJISVC_HOST` or `VOTINGSVC_HOST` is unset.
- Environment variable `INDEX_BUNDLE`: path of the JavaScript bundle served at `/js`. Inside the image the bundle is at `dist/index_bundle.js` relative to the working directory; set `INDEX_BUNDLE=dist/index_bundle.js`. Without it the page loads but the front end script does not.
- Optional environment variables: `MESSAGE_OF_THE_DAY` (text shown on the page), `OTEL_EXPORTER_OTLP_ENDPOINT` (OpenTelemetry trace collector; tracing is not required).
- HTTP routes: `GET /` (web page), `GET /api/list` (JSON list of emoji), `/api/vote?choice=<shortcode>` (cast a vote, e.g. `choice=:doughnut:`), `GET /api/leaderboard` (JSON vote counts).

### emoji
- Listens for gRPC on port 8080. The port is set by the required environment variable `GRPC_PORT`; set `GRPC_PORT=8080`. The server exits at start-up if it is unset.
- Optional environment variable `PROM_PORT`: when set, the service also serves Prometheus metrics at `/metrics` on that port (the project documents port 8801).
- Optional environment variable `OTEL_EXPORTER_OTLP_ENDPOINT` (trace collector).
- Keeps its emoji list in memory; no persistent data.

### voting
- Listens for gRPC on port 8080. The port is set by the required environment variable `GRPC_PORT`; set `GRPC_PORT=8080`. The server exits at start-up if it is unset.
- Optional environment variable `PROM_PORT`: when set, the service also serves Prometheus metrics at `/metrics` on that port, including the vote counter `emojivoto_votes_total` (the project documents port 8801).
- Optional environment variables: `FAILURE_RATE` (fraction 0.0-1.0 of `:doughnut:` votes that fail on purpose; default 0), `ARTIFICIAL_DELAY` (Go duration added to each vote; default `0ms`), `OTEL_EXPORTER_OTLP_ENDPOINT` (trace collector).
- Votes are kept in memory only; they are lost when the service restarts. No persistent volume is needed.

### vote-bot
- Runs the `emojivoto-vote-bot` program from the web image instead of the image's default entrypoint (which starts the web server).
- No listening port.
- Required environment variable `WEB_HOST`: the `host:port` address of the web component's HTTP port. The program exits if it is unset.
- Optional environment variables: `REQUEST_RATE` (votes per second, default 1), `TTL` (stop after this many seconds; default runs forever), `HOST_OVERRIDE` (HTTP Host header to send).

## Dependencies
- web depends on emoji and voting.
- vote-bot depends on web.
- emoji and voting have no dependencies.

## External access
- The web component (HTTP port 8080) must be reachable from outside the cluster.
- emoji, voting and vote-bot are used only inside the application and need not be reachable from outside.

## Health endpoints
- The services expose no dedicated health endpoint. `GET /` on the web port returns HTTP 200 with the web page.
