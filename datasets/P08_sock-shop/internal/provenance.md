# Provenance: Sock Shop

Repository: https://github.com/microservices-demo/microservices-demo at commit `9dff06fae4981921caec6a62393a6ebfce4b3e3f` (cited as `mdemo:`).
No fact below is taken from `deploy/kubernetes/`.

Service repositories (shallow clones in `datasets/.cache/sock-shop-src/`, each at the tag of the image version used in the deployment files):

| Prefix | Repository | Tag | Commit |
|---|---|---|---|
| `front-end:` | https://github.com/microservices-demo/front-end | 0.3.12 | `b2308a3ecc70b9ac97b93ce73985e57d5d0c186b` |
| `catalogue:` | https://github.com/microservices-demo/catalogue | 0.3.5 | `93452255c62cac6e44f5d86376d7cb3c5409e162` |
| `carts:` | https://github.com/microservices-demo/carts | 0.4.8 | `d0a55c9f483269034ab9f2473c1a738b2d7d422b` |
| `orders:` | https://github.com/microservices-demo/orders | 0.4.7 | `e97ec6530811c92babbcb4227cf2d77896b5c26d` |
| `payment:` | https://github.com/microservices-demo/payment | 0.4.3 | `923c8b030364fd4e217c54cd1e30150b7cad4266` |
| `shipping:` | https://github.com/microservices-demo/shipping | 0.4.8 | `c3bc9015fdbfce1265370502c4fd19b45120550e` |
| `queue-master:` | https://github.com/microservices-demo/queue-master | 0.3.1 | `ca72773d51ca4676306e6c5f25835990f3753748` |
| `user:` | https://github.com/microservices-demo/user | 0.4.7 | `1968fe09635e320bb573260a27711f08f7a4a43a` |

`compose` below means `mdemo:deploy/docker-compose/docker-compose.yml`.

| Spec fact | Source |
|---|---|
| Purpose: user-facing part of an online shop that sells socks | `mdemo:README.md` L5 |
| Built with Spring Boot, Go kit and Node.js | `mdemo:README.md` L7 |
| Services roughly defined by e-commerce function; all communicate using REST over HTTP | `mdemo:internal-docs/design.md` L27, L29 |
| front-end puts together all the microservices | `front-end:README.md` L7 |
| Image `weaveworksdemos/front-end:0.3.12` | compose L5 |
| Image `weaveworksdemos/catalogue:0.3.5` | compose L30 |
| Image `weaveworksdemos/catalogue-db:0.3.0`; MySQL 5.7 base | compose L39; `catalogue:docker/catalogue-db/Dockerfile` L1 |
| Image `weaveworksdemos/carts:0.4.8` | compose L47 |
| Image `mongo:3.4` for carts-db and orders-db | compose L60, L86 |
| Image `weaveworksdemos/orders:0.4.7` | compose L73 |
| Image `weaveworksdemos/shipping:0.4.8` | compose L99 |
| Image `weaveworksdemos/queue-master:0.3.1` | compose L112 |
| Image `rabbitmq:3.6.8` | compose L125 |
| Image `weaveworksdemos/payment:0.4.3` | compose L137 |
| Image `weaveworksdemos/user:0.4.4` | compose L146 |
| Image `weaveworksdemos/user-db:0.4.0`; MongoDB base | compose L157; `user:docker/user-db/Dockerfile` L1 |
| catalogue role (list, size, item, tags, images) | `catalogue:transport.go` L32-36; `front-end:api/catalogue/index.js` L10-23 |
| carts role | `carts:README.md` L4 |
| orders role (place and store orders) | `front-end:api/orders/index.js` L22, L122; `orders:src/main/resources/application.properties` L2 |
| payment role (`POST /paymentAuth`) | `payment:transport.go` L29 |
| shipping role (accept shipment, put on queue) | `shipping:src/main/java/works/weave/socks/shipping/controllers/ShippingController.java` L37-48 |
| queue-master role (reads shipping queue) | `queue-master:README.md` L7-9 |
| user role (customers, addresses, cards, login, register) | `user:api/transport.go` L38-80 |
| front-end listens on 8079 | `front-end:Dockerfile` L3-4; `front-end:server.js` L55 |
| front-end calls `http://catalogue`, `http://carts`, `http://orders`, `http://user` | `front-end:api/endpoints.js` L18-26 (domain suffix is empty unless `--domain` is passed, L6-15) |
| `SESSION_REDIS` switches to Redis sessions at `session-db`; otherwise in-memory sessions | `front-end:server.js` L22-29; `front-end:config.js` L8-21 (L16 `host: "session-db"`) |
| Redis default port 6379 | Redis default; `front-end:config.js` L16 sets no port |
| front-end `GET /` returns the home page | `front-end:server.js` L21 (`express.static("public")`); `front-end:public/index.html` L14-16 |
| catalogue listens on 80 | `catalogue:docker/catalogue/Dockerfile-release` L13, L37 (release image built from this file, `catalogue:scripts/build.sh` L44) |
| catalogue DSN `catalogue_user:default_password@tcp(catalogue-db:3306)/socksdb` | `catalogue:cmd/cataloguesvc/main.go` L46 |
| catalogue `GET /health` | `catalogue:transport.go` L36, L82 |
| catalogue-db port 3306 | MySQL default; `catalogue:cmd/cataloguesvc/main.go` L46 |
| `MYSQL_DATABASE=socksdb`; `MYSQL_ROOT_PASSWORD` / `MYSQL_ALLOW_EMPTY_PASSWORD` | compose L42-45; MySQL image documentation (one of the root-password variables is required) |
| catalogue-db creates `catalogue_user` and loads data on first start | `catalogue:docker/catalogue-db/Dockerfile` L7; `catalogue:docker/catalogue-db/data/dump.sql` L1-3, L31 |
| carts listens on 80 | `carts:docker/carts/Dockerfile` L25 (`--port=80`); `carts:src/main/resources/application.properties` L1 |
| carts MongoDB at `carts-db:27017` | `carts:src/main/resources/application.properties` L2 |
| `JAVA_OPTS` value for carts, orders, shipping | compose L57-58, L83-84, L109-110; `carts:docker/carts/Dockerfile` L24 (image default) |
| carts `GET /health` | `carts:src/main/java/works/weave/socks/cart/controllers/HealthCheckController.java` L23 |
| orders listens on 80 | `orders:docker/orders/Dockerfile` L11; `orders:src/main/resources/application.properties` L1 |
| orders MongoDB at `orders-db:27017` | `orders:src/main/resources/application.properties` L2 |
| orders calls `http://payment/paymentAuth` and `http://shipping/shipping` | `orders:src/main/java/works/weave/socks/orders/config/OrdersConfigurationProperties.java` L9, L12, L16, L73 |
| orders reads customer, address, card and cart data from URLs in the order request | `front-end:api/orders/index.js` L60-75; `orders:src/main/java/works/weave/socks/orders/controllers/OrdersController.java` L100 |
| orders `GET /health` | `orders:src/main/java/works/weave/socks/orders/controllers/HealthCheckController.java` L23 |
| payment listens on 80 | `payment:docker/payment/Dockerfile-release` L13, L22 (release image, `payment:scripts/build.sh` L35) |
| payment declines payments over 100 by default | `payment:cmd/paymentsvc/main.go` L26 |
| payment `GET /health` | `payment:transport.go` L36 |
| shipping listens on 80 | `shipping:docker/shipping/Dockerfile` L25; `shipping:src/main/resources/application.properties` L1 |
| shipping uses `rabbitmq`, queue `shipping-task`, `guest`/`guest` | `shipping:src/main/resources/application.properties` L2; `shipping:.../configuration/RabbitMqConfiguration.java` L18, L25, L28-29 |
| shipping accepts shipments even if the queue is down | `shipping:.../controllers/ShippingController.java` L43-48 |
| shipping `GET /health` | `shipping:.../controllers/ShippingController.java` L52 |
| queue-master listens on 80 | `queue-master:docker/queue-master/Dockerfile` L7; `queue-master:src/main/resources/application.properties` L1 |
| queue-master uses `rabbitmq`, queue `shipping-task`, `guest`/`guest` | `queue-master:src/main/java/works/weave/socks/queuemaster/configuration/RabbitMqConfiguration.java` L17, L22, L25-26 |
| queue-master spawns `weaveworksdemos/worker` containers through the Docker API | `queue-master:src/main/java/works/weave/socks/queuemaster/DockerSpawner.java` L23-24, L30-35, L47-49; `.../ShippingTaskHandler.java` L15-16; `queue-master:README.md` L7-9 |
| Compose mounts the host Docker socket into queue-master | compose L114-115 |
| Docker-container shipping is demo-only and to be removed | `queue-master:README.md` L31-32 |
| queue-master `GET /health` | `queue-master:.../controllers/HealthCheckController.java` L27 |
| rabbitmq port 5672 | RabbitMQ default AMQP port; shipping and queue-master set no port (`RabbitMqConfiguration.java` in both) |
| rabbitmq `guest`/`guest` account must stay usable | RabbitMQ image default account; credentials hard-coded in shipping and queue-master (rows above) |
| user listens on 80 | `user:docker/user/Dockerfile-release` L27, L36 |
| `MONGO_HOST` meaning and image default `user-db` | `user:db/mongodb/mongodb.go` L29; `user:docker/user/Dockerfile-release` L24 |
| Reference deployment sets `MONGO_HOST=user-db:27017` | compose L154-155 |
| user `GET /health` | `user:api/transport.go` L92 |
| user-db port 27017 | MongoDB default; compose L155 |
| user-db pre-loaded accounts in `/data/db-users` | `user:docker/user-db/Dockerfile` L4-15; `user:docker/user-db/scripts/customer-insert.js` L24-26 |
| demo account `user` / `password` | `user:api/service_test.go` L30-32 (hash of `password` with the salt of user `user` equals the stored hash) |
| No documented persistence; no volumes for databases in compose | compose L38-45, L59-71, L85-97, L124-135, L156-168 (no `volumes`; only `tmpfs` for `/tmp` on carts-db, orders-db, user-db) |
| Dependencies | `front-end:api/endpoints.js` L18-26; `catalogue:cmd/cataloguesvc/main.go` L46; `carts:` and `orders:` `application.properties` L2; `OrdersConfigurationProperties.java` L12, L16; `user:docker/user/Dockerfile-release` L24; shipping and queue-master `RabbitMqConfiguration.java` |
| front-end reachable from outside | `mdemo:README.md` L5 ("user-facing part"); compose L11-15 (only the edge-router in front of front-end publishes ports) |
| All other components internal only | compose: no `ports` on any service except edge-router (L13-15) |

## Excluded facts (appear only in the human manifests)
- NodePort 30001 and the Service type of front-end; replica counts; resource requests and limits; liveness/readiness probe settings; labels; the namespace `sock-shop`; `nodeSelector beta.kubernetes.io/os: linux`; `runAsUser: 10001`/`runAsNonRoot`, capability lists and `readOnlyRootFilesystem`; `emptyDir` (memory) volumes for `/tmp`; `prometheus.io/scrape` annotations.
- `SESSION_REDIS=true` on front-end and the `session-db` component with image `redis:alpine` (compose uses in-memory sessions; the spec states only the code behaviour of `SESSION_REDIS`).
- The `rabbitmq-exporter` sidecar (`kbudde/rabbitmq-exporter`, port 9090) and the RabbitMQ management port 15672 / `-management` image tag.
- `ZIPKIN=zipkin.jaeger.svc.cluster.local` on shipping; `JAVA_OPTS` on queue-master; the env var `mongo=user-db:27017` on user (the code reads `MONGO_HOST`).
- Catalogue `command: ["/app"]` with `-port=80` (equivalent to the image default, not needed in the spec), and `MYSQL_ROOT_PASSWORD=fake_password`.
- Image tags that differ from compose: human uses `weaveworksdemos/user:0.4.7`, `weaveworksdemos/user-db:0.3.0`, `mongo` (no tag) and `rabbitmq:3.6.8-management`; the spec uses the compose references.

## Deliberately left out (in compose, not in the spec)
- `edge-router` (`weaveworksdemos/edge-router:0.1.1`): a reverse proxy in front of front-end in the compose deployment only. The spec requires front-end itself to be reachable from outside.
- `user-sim` (`weaveworksdemos/load-test:0.1.1`): a load generator, not part of the application.
- Container hardening in compose (`cap_drop`, `cap_add`, `read_only`, `tmpfs`), because the spec rules do not cover security settings.
