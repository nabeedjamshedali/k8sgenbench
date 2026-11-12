# Online Boutique

## Purpose
A web-based e-commerce demo application. Users browse products, add them to a shopping cart and purchase them. It consists of 11 microservices, written in different languages, that talk to each other over gRPC (one of them is a load generator that imitates user traffic), plus a Redis store for shopping carts.

## Components

All application images are published under the registry prefix `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/` as `<prefix>/<service>:<tag>`. Use tag `v0.10.7`.

| Component | Image | Role |
|---|---|---|
| frontend | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/frontend:v0.10.7` | Go HTTP server that serves the website. Needs no login; it generates a session ID for each user automatically |
| cartservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/cartservice:v0.10.7` | C# service that stores the items in each user's cart in Redis and retrieves them |
| productcatalogservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/productcatalogservice:v0.10.7` | Go service that provides the product list from a JSON file bundled in the image, product search and single-product lookup |
| currencyservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/currencyservice:v0.10.7` | Node.js service that converts money amounts between currencies, using exchange rates bundled in the image |
| paymentservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/paymentservice:v0.10.7` | Node.js service that charges a credit card (mock) and returns a transaction ID |
| shippingservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/shippingservice:v0.10.7` | Go service that gives shipping cost estimates and ships orders (mock) |
| emailservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/emailservice:v0.10.7` | Python service that sends order confirmation emails (mock) |
| checkoutservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/checkoutservice:v0.10.7` | Go service that retrieves the user's cart, prepares the order and orchestrates payment, shipping and the email notification |
| recommendationservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/recommendationservice:v0.10.7` | Python service that recommends other products based on the cart |
| adservice | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/adservice:v0.10.7` | Java service that provides text ads based on context words |
| loadgenerator | `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/loadgenerator:v0.10.7` | Python/Locust client that continuously sends requests imitating user shopping flows to the frontend |
| redis-cart | `redis:alpine` | Redis store used by cartservice for cart data |

## Component details

All gRPC services register the standard gRPC health service (`grpc.health.v1.Health/Check`) on their listening port. Every `*_SERVICE_ADDR` variable below is the `host:port` of the named service's gRPC endpoint; the address is configurable and is not fixed in code.

### frontend
- Listens on HTTP port 8080 (env var `PORT`, default `8080`).
- Required environment variables. The process exits at startup if any of them is unset or empty:
  - `PRODUCT_CATALOG_SERVICE_ADDR`: address of productcatalogservice.
  - `CURRENCY_SERVICE_ADDR`: address of currencyservice.
  - `CART_SERVICE_ADDR`: address of cartservice.
  - `RECOMMENDATION_SERVICE_ADDR`: address of recommendationservice.
  - `CHECKOUT_SERVICE_ADDR`: address of checkoutservice.
  - `SHIPPING_SERVICE_ADDR`: address of shippingservice.
  - `AD_SERVICE_ADDR`: address of adservice.
  - `SHOPPING_ASSISTANT_SERVICE_ADDR`: `host:port` of the optional shopping assistant service (see "Optional features"). It must be set even when the assistant is not deployed; it is only contacted when the assistant chat endpoint is used.
- Health check: `GET /_healthz` on port 8080 returns HTTP 200 with body `ok`.
- Optional, disabled by default: `ENABLE_PROFILER=1` (Google Cloud Profiler), `ENABLE_TRACING=1` with `COLLECTOR_SERVICE_ADDR` (OpenTelemetry trace collector), `ENABLE_ASSISTANT`, `CYMBAL_BRANDING`, `FRONTEND_MESSAGE`, `PACKAGING_SERVICE_URL`, `ENV_PLATFORM`, `BASE_URL`.

### cartservice
- Listens on gRPC port 7070 (the image sets `ASPNETCORE_HTTP_PORTS=7070`).
- Environment variable `REDIS_ADDR`: `host:port` of the Redis store. Required for the intended setup; if it is unset the service falls back to an in-memory cart store.
- Its gRPC health check reports NOT_SERVING when the cart store (Redis) cannot be reached.
- Optional alternatives to Redis, not used here: Google Cloud Spanner (`SPANNER_PROJECT`, `SPANNER_CONNECTION_STRING`) and AlloyDB (`ALLOYDB_PRIMARY_IP`).

### productcatalogservice
- Listens on gRPC port 3550 (env var `PORT`, default `3550`).
- Loads the catalog from the `products.json` file in the image. Loading from AlloyDB (`ALLOYDB_CLUSTER_NAME` and related variables) is optional and not used here.
- Optional: `EXTRA_LATENCY` (a Go duration added to each request).

### currencyservice
- Listens on gRPC port 7000. The listening port is read from env var `PORT`, which has no default in code and must be set (the image exposes 7000).

### paymentservice
- Listens on gRPC port 50051. The listening port is read from env var `PORT`, which has no default in code and must be set (the image exposes 50051).

### shippingservice
- Listens on gRPC port 50051 (env var `PORT`, default `50051`).

### emailservice
- Listens on gRPC port 8080 (env var `PORT`, default `8080`).

### checkoutservice
- Listens on gRPC port 5050 (env var `PORT`, default `5050`).
- Required environment variables. The process exits at startup if any of them is unset or empty: `PRODUCT_CATALOG_SERVICE_ADDR`, `SHIPPING_SERVICE_ADDR`, `PAYMENT_SERVICE_ADDR`, `EMAIL_SERVICE_ADDR`, `CURRENCY_SERVICE_ADDR`, `CART_SERVICE_ADDR` (addresses of the corresponding services).
- Optional, disabled by default: `ENABLE_PROFILER=1`, `ENABLE_TRACING=1` with `COLLECTOR_SERVICE_ADDR`.

### recommendationservice
- Listens on gRPC port 8080 (env var `PORT`, default `8080`).
- Required environment variable `PRODUCT_CATALOG_SERVICE_ADDR`: address of productcatalogservice. The process exits at startup if it is unset.

### adservice
- Listens on gRPC port 9555 (env var `PORT`, default `9555`).

### loadgenerator
- No listening port.
- Required environment variable `FRONTEND_ADDR`: `host:port` of the frontend's HTTP endpoint; requests are sent to `http://${FRONTEND_ADDR}`.
- Optional: `USERS` (number of simulated users, default 10) and `RATE` (users spawned per second, default 1).

### redis-cart
- Listens on the default Redis port 6379.

## Profiler and tracing in the backend services
- productcatalogservice, shippingservice, currencyservice and paymentservice start the Google Cloud Profiler agent unless the environment variable `DISABLE_PROFILER` is set (any value). The profiler needs a Google Cloud project; when the application does not run on Google Cloud, set `DISABLE_PROFILER` on these four services.
- emailservice and recommendationservice also honour `DISABLE_PROFILER`, but their profiler start-up is currently a no-op.
- Tracing is optional and off unless `ENABLE_TRACING=1` and `COLLECTOR_SERVICE_ADDR` are set (productcatalogservice, currencyservice, paymentservice, emailservice, recommendationservice). shippingservice and adservice accept `DISABLE_TRACING` and `DISABLE_STATS`; their tracing and stats exporters are not implemented.

## Optional features (not deployed)
- Shopping assistant (`shoppingassistantservice`, Gemini-based): an optional add-on that needs Google Cloud (it requires `PROJECT_ID`, `REGION` and `ALLOYDB_*` settings and calls Gemini models). It is not part of this deployment.

## Dependencies
- frontend depends on productcatalogservice, currencyservice, cartservice, recommendationservice, checkoutservice, shippingservice and adservice.
- checkoutservice depends on productcatalogservice, shippingservice, paymentservice, emailservice, currencyservice and cartservice.
- recommendationservice depends on productcatalogservice.
- cartservice depends on redis-cart.
- loadgenerator depends on frontend.

## Persistence
- No component has a documented requirement for persistent storage. Cart contents are kept in Redis.

## External access
- The frontend website (port 8080) must be reachable from outside the cluster.
- All other components are internal only.
