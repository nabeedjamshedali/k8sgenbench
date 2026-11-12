# Sock Shop

## Purpose
The user-facing part of an online shop that sells socks, built as a set of microservices. A Node.js web front end serves the shop and calls REST services for the product catalogue, shopping carts, orders, payment, shipping and user accounts. Each data-holding service has its own database, and shipping requests are passed through a RabbitMQ queue to a queue consumer. All services communicate using REST over HTTP.

## Components

| Component | Image | Role |
|---|---|---|
| front-end | `weaveworksdemos/front-end:0.3.12` | Node.js web front end; serves the shop pages and proxies the API calls of the browser to the back-end services |
| catalogue | `weaveworksdemos/catalogue:0.3.5` | Go service that lists socks, their tags and product images |
| catalogue-db | `weaveworksdemos/catalogue-db:0.3.0` | MySQL 5.7 database pre-loaded with the sock catalogue |
| carts | `weaveworksdemos/carts:0.4.8` | Java (Spring Boot) service that stores shopping carts |
| carts-db | `mongo:3.4` | MongoDB database of the carts service |
| orders | `weaveworksdemos/orders:0.4.7` | Java (Spring Boot) service that places and stores orders |
| orders-db | `mongo:3.4` | MongoDB database of the orders service |
| payment | `weaveworksdemos/payment:0.4.3` | Go service that authorises payments |
| shipping | `weaveworksdemos/shipping:0.4.8` | Java (Spring Boot) service that accepts shipments and puts them on a queue |
| queue-master | `weaveworksdemos/queue-master:0.3.1` | Java (Spring Boot) service that consumes the shipping queue |
| rabbitmq | `rabbitmq:3.6.8` | RabbitMQ message broker holding the shipping queue |
| user | `weaveworksdemos/user:0.4.4` | Go service for customer accounts, addresses, cards, login and registration |
| user-db | `weaveworksdemos/user-db:0.4.0` | MongoDB database pre-loaded with demo customer accounts |

## Component details

### front-end
- Listens on HTTP port 8079 (the image sets `PORT=8079`).
- Calls the back-end services at fixed hostnames on HTTP port 80: `catalogue`, `carts`, `orders` and `user`. These hostnames are fixed in the application code.
- Optional environment variable `SESSION_REDIS`: when set, user sessions are stored in Redis at hostname `session-db` (default Redis port 6379; the hostname is fixed in the application code). When unset, sessions are kept in the memory of the front-end process.
- Health check: `GET /` on port 8079 returns HTTP 200 (the shop's home page).

### catalogue
- Listens on HTTP port 80 (the image starts the service with `-port=80`).
- Must be reachable at hostname `catalogue` on port 80, because the front end uses that address.
- Connects to MySQL at hostname `catalogue-db` on port 3306, database `socksdb`, user `catalogue_user`, password `default_password`. These connection settings are the built-in default of the service.
- Health check: `GET /health` on port 80.

### catalogue-db
- Listens on port 3306 (MySQL default).
- Must be reachable at hostname `catalogue-db` on port 3306.
- Environment variables: `MYSQL_DATABASE=socksdb` (required, because the bundled data and the catalogue service use this database), and either `MYSQL_ROOT_PASSWORD` or `MYSQL_ALLOW_EMPTY_PASSWORD=true` (required by the MySQL image to initialise).
- On first start the image creates the `catalogue_user` account and loads the sock catalogue.

### carts
- Listens on HTTP port 80 (the image starts the service with `--port=80`).
- Must be reachable at hostname `carts` on port 80, because the front end and the orders service use that address.
- Connects to MongoDB at hostname `carts-db` on port 27017. This is the built-in default of the service.
- Optional environment variable `JAVA_OPTS` (JVM options). The project's reference deployment sets `-Xms64m -Xmx128m -XX:+UseG1GC -Djava.security.egd=file:/dev/urandom -Dspring.zipkin.enabled=false`.
- Health check: `GET /health` on port 80.

### carts-db
- Listens on port 27017 (MongoDB default).
- Must be reachable at hostname `carts-db` on port 27017.

### orders
- Listens on HTTP port 80 (the image starts the service with `--port=80`).
- Must be reachable at hostname `orders` on port 80, because the front end uses that address.
- Connects to MongoDB at hostname `orders-db` on port 27017. This is the built-in default of the service.
- Calls the payment service at `http://payment/paymentAuth` and the shipping service at `http://shipping/shipping`. These hostnames are fixed in the application code.
- Reads customer, address, card and cart data from the user and carts services, using the URLs passed to it in each order request.
- Optional environment variable `JAVA_OPTS`, as for carts.
- Health check: `GET /health` on port 80.

### orders-db
- Listens on port 27017 (MongoDB default).
- Must be reachable at hostname `orders-db` on port 27017.

### payment
- Listens on HTTP port 80 (the image starts the service with `-port=80`).
- Must be reachable at hostname `payment` on port 80, because the orders service uses that address.
- Declines payments above 100 by default.
- Health check: `GET /health` on port 80.

### shipping
- Listens on HTTP port 80 (the image starts the service with `--port=80`).
- Must be reachable at hostname `shipping` on port 80, because the orders service uses that address.
- Publishes each shipment to the RabbitMQ queue `shipping-task` at hostname `rabbitmq` (default AMQP port 5672) with user `guest` and password `guest`. These settings are fixed in the application code.
- Optional environment variable `JAVA_OPTS`, as for carts.
- Health check: `GET /health` on port 80.

### queue-master
- Listens on HTTP port 80 (the image starts the service with `--port=80`).
- Consumes the RabbitMQ queue `shipping-task` at hostname `rabbitmq` (default AMQP port 5672) with user `guest` and password `guest`. These settings are fixed in the application code.
- For each consumed shipment it tries to start a short-lived container from the image `weaveworksdemos/worker` through the Docker Engine API, to simulate the shipping process. The project's Docker Compose deployment gives it access to the host's Docker socket `/var/run/docker.sock` for this. The maintainers describe this as functionality that was added only for demonstration and that is to be removed. The shipping service does not wait for queue-master; it accepts each shipment once it is published to the queue.
- Health check: `GET /health` on port 80.

### rabbitmq
- Listens on port 5672 (AMQP, RabbitMQ default).
- Must be reachable at hostname `rabbitmq` on port 5672.
- The default `guest`/`guest` account must remain usable, because shipping and queue-master use it.

### user
- Listens on HTTP port 80 (the image starts the service with `-port=80`).
- Must be reachable at hostname `user` on port 80, because the front end uses that address.
- Environment variable `MONGO_HOST`: address of its MongoDB database. The image default is `user-db` (default port 27017); the project's reference deployment sets `MONGO_HOST=user-db:27017`.
- Health check: `GET /health` on port 80.

### user-db
- Listens on port 27017 (MongoDB default).
- Must be reachable at hostname `user-db` on port 27017.
- The image contains pre-loaded demo accounts (for example user `user` with password `password`) in its data directory `/data/db-users`.

## Persistence
- The project does not document any data that must survive restarts. Its Docker Compose deployment defines no volumes for any database; the catalogue and the demo accounts are built into the `catalogue-db` and `user-db` images.

## Dependencies
- front-end depends on catalogue, carts, orders and user.
- catalogue depends on catalogue-db.
- carts depends on carts-db.
- orders depends on orders-db, payment and shipping, and reads data from user and carts.
- user depends on user-db.
- shipping and queue-master depend on rabbitmq.

## External access
- The front-end web shop (port 8079) must be reachable from outside the cluster.
- All other components are internal only.
