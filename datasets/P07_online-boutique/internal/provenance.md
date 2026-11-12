# Provenance: Online Boutique

Repository: https://github.com/GoogleCloudPlatform/microservices-demo at commit `38e7348eb289eb5b87c0c6e8cb19ced0449dc389`.
No fact below is taken from `release/kubernetes-manifests.yaml`, `kubernetes-manifests/`, `kustomize/` or `helm-chart/`, except the image tag, which is marked.

## General

| Spec fact | Source |
|---|---|
| Purpose (web e-commerce demo: browse, add to cart, purchase) | `README.md` L6-7 |
| 11 microservices in different languages talking over gRPC | `README.md` L17-18 |
| Roles and languages of all 11 services | `README.md` L27-37 (architecture table) |
| frontend needs no login and generates session IDs | `README.md` L27; `src/frontend/middleware.go` L85-101 |
| Image naming `<prefix>/<service>:<tag>` | `docs/releasing/make-release-artifacts.sh` L68-71 (`image="$REPO_PREFIX/$svcname:$TAG"` for every directory in `src/`) |
| Registry prefix `us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo` | `docs/releasing/README.md` L34, L52; `docs/releasing/make-release.sh` L32 |
| Tag `v0.10.7` | image reference: human manifest (unavoidable; identifies the artefact). Not documented elsewhere in the checkout. |
| Redis image `redis:alpine` | `docs/releasing/make-release-artifacts.sh` L109-110 ("we use the official `redis:alpine` Docker image") |
| All gRPC services register `grpc.health.v1` health service | `src/checkoutservice/main.go` L143-144; `src/productcatalogservice/server.go` L144-145; `src/shippingservice/main.go` L93-94; `src/currencyservice/server.js` L186; `src/paymentservice/server.js` L96; `src/emailservice/email_server.py` L127; `src/recommendationservice/recommendation_server.py` L144; `src/adservice/src/main/java/hipstershop/AdService.java` L60; `src/cartservice/src/Startup.cs` L75 |
| `*_SERVICE_ADDR` values are `host:port` gRPC targets | `src/frontend/main.go` L225-231 and `src/checkoutservice/main.go` L211-217 (`grpc.NewClient(addr, ...)`); `src/recommendationservice/recommendation_server.py` L135 (`grpc.insecure_channel(catalog_addr)`) |

## frontend

| Spec fact | Source |
|---|---|
| HTTP port 8080, `PORT` override | `src/frontend/main.go` L39, L127-130, L171; `src/frontend/Dockerfile` L43 (`EXPOSE 8080`) |
| Required `PRODUCT_CATALOG_SERVICE_ADDR`, `CURRENCY_SERVICE_ADDR`, `CART_SERVICE_ADDR`, `RECOMMENDATION_SERVICE_ADDR`, `CHECKOUT_SERVICE_ADDR`, `SHIPPING_SERVICE_ADDR`, `AD_SERVICE_ADDR`, `SHOPPING_ASSISTANT_SERVICE_ADDR` | `src/frontend/main.go` L132-139 |
| Process exits if one is unset or empty | `src/frontend/main.go` L217-221 (`panic`) |
| Shopping assistant address only contacted by the chat endpoint | `src/frontend/main.go` L141-147 (no gRPC connection for it), L163 (`/bot` route); `src/frontend/handlers.go` L464-472 |
| Health check `GET /_healthz` returns `ok` | `src/frontend/main.go` L161 |
| Optional `ENABLE_PROFILER`, `ENABLE_TRACING`, `COLLECTOR_SERVICE_ADDR`, `BASE_URL` | `src/frontend/main.go` L111, L113-125, L178 |
| Optional `ENABLE_ASSISTANT`, `CYMBAL_BRANDING`, `FRONTEND_MESSAGE`, `ENV_PLATFORM` | `src/frontend/handlers.go` L46-48, L93-98 |
| Optional `PACKAGING_SERVICE_URL` | `src/frontend/packaging_info.go` L43; `src/frontend/handlers.go` L188-196 |
| Must be reachable from outside | `README.md` L111-117 ("Access the web frontend in a browser using the frontend's external IP") |

## cartservice

| Spec fact | Source |
|---|---|
| gRPC port 7070 via `ASPNETCORE_HTTP_PORTS=7070` | `src/cartservice/src/Dockerfile` L40-42 |
| `REDIS_ADDR` is Redis `host:port`; in-memory fallback if unset | `src/cartservice/src/Startup.cs` L29, L34-41, L51-56 (message "Redis cache host(hostname+port) was not specified") |
| Stores carts in Redis | `README.md` L28 |
| Health reports NOT_SERVING when store unreachable | `src/cartservice/src/services/HealthCheckService.cs` L33-37 |
| Optional Spanner / AlloyDB stores | `src/cartservice/src/Startup.cs` L30-32, L42-50 |

## productcatalogservice

| Spec fact | Source |
|---|---|
| gRPC port 3550, `PORT` override | `src/productcatalogservice/server.go` L49, L115-116; `src/productcatalogservice/Dockerfile` L43 |
| Catalog from bundled `products.json`; AlloyDB optional | `src/productcatalogservice/catalog_loader.go` L37-47; `README.md` L29 |
| Optional `EXTRA_LATENCY` | `src/productcatalogservice/server.go` L88-94 |

## currencyservice

| Spec fact | Source |
|---|---|
| `PORT` read with no default; binds `[::]:${PORT}` | `src/currencyservice/server.js` L83, L188-189 |
| Image exposes 7000 | `src/currencyservice/Dockerfile` L43 (no `ENV PORT` in the Dockerfile) |
| Exchange rates bundled in the image | `src/currencyservice/server.js` L105-111 (`./data/currency_conversion.json`) |

## paymentservice

| Spec fact | Source |
|---|---|
| `PORT` read with no default; binds `[::]:${port}` | `src/paymentservice/index.js` L70-73; `src/paymentservice/server.js` L60-61 |
| Image exposes 50051 | `src/paymentservice/Dockerfile` L43 (no `ENV PORT` in the Dockerfile) |
| Mock charge returning a transaction ID | `README.md` L31; `src/paymentservice/charge.js` |

## shippingservice

| Spec fact | Source |
|---|---|
| gRPC port 50051, `PORT` override | `src/shippingservice/main.go` L37, L72-75; `src/shippingservice/Dockerfile` L43 |

## emailservice

| Spec fact | Source |
|---|---|
| gRPC port 8080, `PORT` override | `src/emailservice/email_server.py` L129-131; `src/emailservice/Dockerfile` L53 |

## checkoutservice

| Spec fact | Source |
|---|---|
| gRPC port 5050, `PORT` override | `src/checkoutservice/main.go` L46, L105-108; `src/checkoutservice/Dockerfile` L43 |
| Required `SHIPPING_SERVICE_ADDR`, `PRODUCT_CATALOG_SERVICE_ADDR`, `CART_SERVICE_ADDR`, `CURRENCY_SERVICE_ADDR`, `EMAIL_SERVICE_ADDR`, `PAYMENT_SERVICE_ADDR` | `src/checkoutservice/main.go` L111-116 |
| Process exits if one is unset | `src/checkoutservice/main.go` L202-208 (`panic`) |
| Optional `ENABLE_PROFILER`, `ENABLE_TRACING`, `COLLECTOR_SERVICE_ADDR` | `src/checkoutservice/main.go` L90-103, L164 |

## recommendationservice

| Spec fact | Source |
|---|---|
| gRPC port 8080, `PORT` override | `src/recommendationservice/recommendation_server.py` L130, L148; `src/recommendationservice/Dockerfile` L52-53 |
| Required `PRODUCT_CATALOG_SERVICE_ADDR`, exits if unset | `src/recommendationservice/recommendation_server.py` L131-133 |

## adservice

| Spec fact | Source |
|---|---|
| gRPC port 9555, `PORT` override | `src/adservice/src/main/java/hipstershop/AdService.java` L54; `src/adservice/Dockerfile` L43 |
| `DISABLE_STATS`, `DISABLE_TRACING`; exporters not implemented | `src/adservice/src/main/java/hipstershop/AdService.java` L195-220 |

## loadgenerator

| Spec fact | Source |
|---|---|
| No listening port | `src/loadgenerator/Dockerfile` (no `EXPOSE`); L52 runs `locust --headless` |
| `FRONTEND_ADDR` used as `http://${FRONTEND_ADDR}`; `USERS` default 10, `RATE` default 1 | `src/loadgenerator/Dockerfile` L52 |
| Sends shopping flows to the frontend | `README.md` L37; `src/loadgenerator/locustfile.py` L34-72 |

## redis-cart

| Spec fact | Source |
|---|---|
| Port 6379 | Redis default port; `REDIS_ADDR` is host+port (`src/cartservice/src/Startup.cs` L53) |

## Profiler and tracing

| Spec fact | Source |
|---|---|
| Go services start the profiler unless `DISABLE_PROFILER` | `src/productcatalogservice/server.go` L78-83; `src/shippingservice/main.go` L65-70 |
| Node services start the profiler unless `DISABLE_PROFILER` | `src/currencyservice/server.js` L28-39; `src/paymentservice/index.js` L21-31 |
| Profiler needs a Google Cloud project off GCP | `src/productcatalogservice/server.go` L184, `src/shippingservice/main.go` L170 ("ProjectID must be set if not running on GCP.") |
| Python services: `DISABLE_PROFILER` honoured, start-up is a no-op | `src/emailservice/email_server.py` L139-163, L171-177; `src/recommendationservice/recommendation_server.py` L43-67, L101-107 |
| Tracing only with `ENABLE_TRACING=1` and `COLLECTOR_SERVICE_ADDR` | `src/productcatalogservice/server.go` L69, L163; `src/currencyservice/server.js` L50, L61; `src/paymentservice/index.js` L34, L47; `src/emailservice/email_server.py` L181-182; `src/recommendationservice/recommendation_server.py` L114-116 |
| shippingservice `DISABLE_TRACING`/`DISABLE_STATS`, exporters unavailable | `src/shippingservice/main.go` L57-63, L84-90 |

## Optional features, dependencies, persistence, access

| Spec fact | Source |
|---|---|
| Shopping assistant is an optional add-on using Gemini | `README.md` L135 |
| It requires `PROJECT_ID`, `REGION`, `ALLOYDB_*` and calls Gemini | `src/shoppingassistantservice/shoppingassistantservice.py` L27-33, L22, L72 |
| frontend dependencies | `src/frontend/main.go` L132-147 |
| checkoutservice dependencies | `src/checkoutservice/main.go` L111-123; `README.md` L34 |
| recommendationservice depends on productcatalogservice | `src/recommendationservice/recommendation_server.py` L131-136 |
| cartservice depends on Redis | `README.md` L28; `src/cartservice/src/Startup.cs` L34-40 |
| loadgenerator depends on frontend | `README.md` L37; `src/loadgenerator/Dockerfile` L52 |
| No documented persistence requirement | No README, docs or source file in the checkout states that cart data must survive restarts (judgement from absence) |
| Only the frontend is external | `README.md` L111-117 names only the frontend's external IP; all other services are reached by address variables from other services |

## Excluded facts (appear only in the human manifests)
- Service names and Service ports (for example `emailservice:5000`, `frontend:80`, `redis-cart:6379`), the `frontend-external` LoadBalancer, all Service types.
- The specific `*_SERVICE_ADDR`, `REDIS_ADDR` and `FRONTEND_ADDR` values, and `SHOPPING_ASSISTANT_SERVICE_ADDR=shoppingassistantservice:80`.
- `USERS=10`, `RATE=1` as explicit settings (the defaults are cited from the Dockerfile), the busybox `frontend-check` init container of the loadgenerator.
- The choice of which services get `DISABLE_PROFILER=1` / `ENABLE_PROFILER=0`.
- ServiceAccounts, securityContext (runAsUser 1000, readOnlyRootFilesystem, dropped capabilities), resource requests and limits, gRPC/HTTP/TCP probe settings including the `shop_session-id` probe cookie, `terminationGracePeriodSeconds`, the Istio annotation, `replicas: 1`, labels.
- `emptyDir` for `/data` in redis-cart.
