# Provenance: TeaStore

Repository: https://github.com/DescartesResearch/TeaStore at commit `34b37f7e7be433ce72d5f9455e66922a13116749`.
No fact below is taken from `examples/kubernetes/`. Paths below are abbreviated: `svc/<x>` = `services/tools.descartes.teastore.<x>`, `rc` = `utilities/tools.descartes.teastore.registryclient/src/main/java/tools/descartes/teastore/registryclient`, `base` = `utilities/tools.descartes.teastore.dockerbase`.

| Spec fact | Source |
|---|---|
| Purpose: reference/test application, emulated tea store with generated data | `README.md` L3; `GET_STARTED.md` L30, L41 |
| Five services plus registry, REST communication, service list | `GET_STARTED.md` L32-37; `README.md` L5 |
| Pre-configured MariaDB database image | `GET_STARTED.md` L60, L109-110; `utilities/tools.descartes.teastore.database/Dockerfile` L1 (`FROM mariadb:10.4.12`) |
| Images of all seven components | `GET_STARTED.md` L77-97; `examples/docker/docker-compose_default.yaml` L4, L8, L14, L23, L30, L37, L44 |
| Roles: auth (login, logout, isloggedin, cart, placeorder) | `svc/auth/src/main/java/.../auth/rest/AuthUserActionsRest.java` L45, L72, L132, L163, L180; `AuthCartRest.java` L40 |
| Roles: image generates and serves images; recommender trains on orders | `svc/image/src/main/java/.../image/rest/ImageProviderEndpoint.java` L45, L59, L84; `svc/recommender/src/main/java/.../recommender/servlet/TrainingSynchronizer.java` L168-169, L184 |
| Role: persistence generates data when database is empty | `svc/persistence/src/main/java/.../persistence/daemons/InitialDataGenerationDaemon.java` L66-74 |
| Java/Tomcat services, port 8080 | `base/Dockerfile` L1 (`FROM tomcat:...`), L50 (`EXPOSE 8080`); every `svc/*/Dockerfile` L1 (`FROM descartesresearch/teastore-base`); `examples/docker/docker-compose_default.yaml` L5-6, L15-16, L24-25, L31-32, L38-39, L45-46 |
| Context path `/tools.descartes.teastore.<service>/` | `svc/*/pom.xml` `<finalName>` (auth L56, image L59, persistence L75, recommender L51, registry L96, webui L47); `GET_STARTED.md` L136 |
| Services register with the registry under their service name with `host:port`, heartbeats | `rc/RegistryClient.java` L156-163, L240-245, L290-292; `rc/RegistryClient.java` L65 (heartbeat interval); `rc/Service.java` L25-41; `GET_STARTED.md` L39 |
| Services look up other services' addresses from the registry | `rc/RegistryClient.java` L189-208 |
| `REGISTRY_HOST`, `REGISTRY_PORT`: meaning, mandatory | `GET_STARTED.md` L62-63, L81, L85, L88, L91, L95 |
| Registry URL built from `REGISTRY_HOST:REGISTRY_PORT` | `base/start.sh` L9 |
| Defaults `REGISTRY_HOST 127.0.0.1`, `REGISTRY_PORT 8080`, `SERVICE_PORT 8080`, `DB_HOST 127.0.0.1`, `DB_PORT 3306`, `USE_POD_IP false` | `base/Dockerfile` L18-24 |
| `HOST_NAME` meaning; OS hostname if unset | `GET_STARTED.md` L64; `base/start.sh` L11-21; `rc/RegistryClient.java` L85-95, L294-303 |
| `USE_POD_IP=true` alternative, recommended for Kubernetes | `GET_STARTED.md` L65, L82, L86, L89, L92, L96; `rc/RegistryClient.java` L79-87; `base/start.sh` L22 |
| `SERVICE_PORT` is the registered port and must match the port other services reach | `GET_STARTED.md` L66, L104; `rc/RegistryClient.java` L96-101; `base/start.sh` L3 |
| Registered address must be known/reachable | `GET_STARTED.md` L102 |
| Startup order does not matter, services retry | `GET_STARTED.md` L100-101; `InitialDataGenerationDaemon.java` L80-97 |
| Registry REST path `/tools.descartes.teastore.registry/rest/services/` | `base/start.sh` L9; `svc/registry/src/main/java/.../registry/rest/RegistryREST.java` L31; `svc/registry/src/main/webapp/WEB-INF/web.xml` L20 |
| Registry needs only `SERVICE_PORT`/`HOST_NAME`, not `REGISTRY_HOST` | `GET_STARTED.md` L77-79, L108; `examples/docker/docker-compose_default.yaml` L3-6 (no environment) |
| db port 3306 | `utilities/tools.descartes.teastore.database/Dockerfile` L12; `examples/docker/docker-compose_default.yaml` L9-10 |
| db creates `teadb`, user `teauser`/`teapassword`; no configuration needed | `utilities/tools.descartes.teastore.database/setup.sql` L1-3; `utilities/tools.descartes.teastore.database/Dockerfile` L5; `GET_STARTED.md` L97-98, L110 |
| Persistence connects as `teauser`/`teapassword` to `teadb` (fixed) | `svc/persistence/src/main/resources/META-INF/persistence.xml` L19-20; `svc/persistence/src/main/java/.../persistence/repository/EMFManager.java` L48 |
| Data generated on startup when empty; compose runs db without a volume | `InitialDataGenerationDaemon.java` L66-74; `examples/docker/docker-compose_default.yaml` L7-12 (no `volumes`) |
| `DB_HOST`, `DB_PORT` meaning, required for persistence | `GET_STARTED.md` L67-68, L88; `base/start.sh` L23-24; `EMFManager.java` L110-136 |
| Persistence registers only after data generation | `InitialDataGenerationDaemon.java` L66-76 |
| Health: persistence `/rest/generatedb/finished` | `svc/persistence/src/main/java/.../persistence/rest/DatabaseGenerationEndpoint.java` L37, L104-112; `svc/persistence/src/main/webapp/WEB-INF/web.xml` L21 |
| Health: auth `/rest/ready/isready` | `svc/auth/src/main/java/.../auth/rest/ReadyRest.java` L27, L37-41; `svc/auth/src/main/webapp/WEB-INF/web.xml` L21 |
| Health: image `/rest/image/finished` | `ImageProviderEndpoint.java` L34, L83-91; `svc/image/src/main/webapp/WEB-INF/web.xml` L21 |
| Health: recommender `/rest/train/isready` | `svc/recommender/src/main/java/.../recommender/rest/TrainEndpoint.java` L32, L99-107; `svc/recommender/src/main/webapp/WEB-INF/web.xml` L21 |
| Health: webui `/rest/ready/isready` | `svc/webui/src/main/java/.../webui/rest/ReadyRest.java` L27, L37-41; `svc/webui/src/main/webapp/WEB-INF/web.xml` L22 |
| Recommender options and defaults | `GET_STARTED.md` L71-72, L93; `base/Dockerfile` L25-26 |
| `PROXY_NAME`/`PROXY_PORT` | `GET_STARTED.md` L69-70, L83, L123; `base/start.sh` L27-30 |
| WebUI served at `/tools.descartes.teastore.webui/`, `/` redirects | `GET_STARTED.md` L136; `svc/webui/Dockerfile` L7 |
| WebUI status page | `svc/webui/src/main/java/.../webui/servlet/StatusServlet.java` L39, L67-80 |
| auth, image, recommender use persistence | `AuthCartRest.java` L60; `AuthUserActionsRest.java` L96; `svc/image/src/main/java/.../image/setup/ImageProviderStartup.java` L61; `svc/recommender/src/main/java/.../recommender/servlet/RecommenderStartup.java` L73 |
| webui uses persistence, auth, image, recommender | `svc/webui/src/main/java/.../webui/servlet/IndexServlet.java` L56, L58, L60; `svc/webui/src/main/java/.../webui/servlet/CartServlet.java` L88; `rc/rest/LoadBalancedStoreOperations.java` L131; `rc/rest/LoadBalancedImageOperations.java` L108; `rc/rest/LoadBalancedRecommenderOperations.java` L45 |
| All services depend on registry | `GET_STARTED.md` L101 ("all services need the Registry service") |
| persistence depends on db | `GET_STARTED.md` L109 |
| WebUI reachable from outside | `GET_STARTED.md` L136; `examples/docker/docker-compose_default.yaml` L50-51 |

## Excluded facts (appear only in the human manifests)
- NodePort 30080 and the Service type of the WebUI, labels (`app=teastore`, `run=...`), object names `teastore-*`, absence of replicas/resources/probes.
- The use of Service DNS names as `HOST_NAME` values (`teastore-persistence`, ...) and as `REGISTRY_HOST`/`DB_HOST` values. The spec only says the registered address must be reachable; the names are left to the generator. The compose file uses different names (`persistence`, `registry`, `db`), confirming the names are not fixed in code.
- The ClusterIP-vs-Ribbon choice discussed in `GET_STARTED.md` L142-147 is not stated as a requirement: it is framed in terms of Kubernetes Service types and the human manifest choice. The spec presents only `HOST_NAME` and `USE_POD_IP` neutrally.

## Notes
- `examples/docker/docker-compose_default.yaml` L11-12 also publishes the database port 3306 on the host. The spec does not require that, and does not claim that the other components are internal only.
- `GET_STARTED.md` L81 lists `REGISTRY_PORT` and `SERVICE_PORT` as mandatory, but the image sets both to `8080` by default (`base/Dockerfile` L18, L22) and neither the compose file nor the human manifest sets them. The spec gives the defaults.
