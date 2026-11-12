# Provenance: WordPress with MySQL

Repository: https://github.com/kubernetes/website at commit `079a4d63f072a54c317689c957307aaa018cfe34`.
Tutorial page: `content/en/docs/tutorials/stateful-application/mysql-wordpress-persistent-volume.md` (below: "tutorial"). Only the tutorial's prose is cited. The page embeds the two manifests through `code_sample` shortcodes (L120, L127) and quotes the kustomization (L105-112, L143-149); anything visible only in that embedded YAML is treated as manifest-derived. No fact below is taken from `content/en/examples/application/wordpress/`.

The repository contains no Dockerfile or application code for the two images. The environment variables, ports and data paths of the official images are documented upstream, on Docker Hub. The Docker Hub pages are generated from the docker-library documentation repository, which is cited with file and line:

| Upstream source | Repository and commit | Docker Hub page |
|---|---|---|
| `docs/wordpress/content.md`, `docs/wordpress/compose.yaml`, `docs/mysql/content.md` | https://github.com/docker-library/docs at `e13e87076b7dbe957b3ed645671b880cddc09162` | https://hub.docker.com/_/wordpress, https://hub.docker.com/_/mysql |
| `wordpress/wp-config-docker.php`, `wordpress/latest/php8.2/apache/Dockerfile` | https://github.com/docker-library/wordpress at `5ec12a3ef21493a12f3d211e0d69d0c6a30a9794` | (source of the `wordpress` image) |
| `mysql/Dockerfile.oracle` (template for all MySQL image versions) | https://github.com/docker-library/mysql at `2f988f198f35d25b1454fa2504a0e4c348100549` | (source of the `mysql` image) |
| `WordPress/wp-admin/install.php` (used only for smoke.json) | https://github.com/WordPress/WordPress at tag `6.2.1`, commit `d3deffbd707e74b1e8b5a82de4357a5eda94e0a5` | |

Local copies: `datasets/.cache/wordpress-src/{docker-library-docs,docker-library-wordpress,docker-library-mysql,wordpress-core}`.

| Spec fact | Source |
|---|---|
| Purpose: WordPress site and MySQL database, both need persistent storage | tutorial L14-15, L65 |
| WordPress is a PHP blogging tool and CMS backed by MySQL | `docs/wordpress/content.md` L3 |
| WordPress keeps themes, plugins and files on local disk | `docs/wordpress/content.md` L62-67, L71; tutorial L122-123 ("website data files") |
| Image `wordpress:6.2.1-apache` | image reference: human manifest (unavoidable; identifies the artefact). The image name `wordpress` is documented at https://hub.docker.com/_/wordpress; the tag `6.2.1-apache` appears only in the manifest |
| Image `mysql:8.0` | `docs/wordpress/compose.yaml` L17 (`image: mysql:8.0`, the upstream WordPress example); tag also in the human manifest |
| Roles: WordPress on Apache, MySQL database | tutorial L14-15, L116, L122; `docs/wordpress/content.md` L3; the `-apache` variant runs `apache2-foreground` (`wordpress/latest/php8.2/apache/Dockerfile` L176) |
| wordpress listens on HTTP port 80 | `docs/wordpress/content.md` L28-34 (`-p 8080:80`); `docs/wordpress/compose.yaml` L6-7 |
| `WORDPRESS_DB_HOST` is the address of the MySQL server; WordPress reaches the database through it | tutorial L123-124 (prose); `docs/wordpress/content.md` L17 (upstream image doc) |
| `WORDPRESS_DB_HOST` image default `mysql` | `wordpress/wp-config-docker.php` L59 |
| `host:port` form | `wordpress/wp-config-docker.php` L59 passes the value to WordPress `DB_HOST`, which accepts `host:port`. Judgement: upstream WordPress behaviour, not stated in a cited line |
| `WORDPRESS_DB_PASSWORD` sets the database password | tutorial L124-125 (prose); `docs/wordpress/content.md` L19 |
| `WORDPRESS_DB_USER`, `WORDPRESS_DB_NAME` | upstream image doc only: `docs/wordpress/content.md` L18, L20 (https://hub.docker.com/_/wordpress) |
| `WORDPRESS_DB_NAME` default `wordpress`; user and password defaults are placeholders (hence "required") | `wordpress/wp-config-docker.php` L44, L47, L50, L52-56 |
| Database named by `WORDPRESS_DB_NAME` must already exist; WordPress does not create it | `docs/wordpress/content.md` L26 |
| User and password must match an account with access to that database | follows from `docs/wordpress/content.md` L18-19, L26 and `docs/mysql/content.md` L101, L105 |
| `/var/www/html` must be persistent | tutorial L65, L122-123; `docs/wordpress/content.md` L71 ("the `/var/www/html/` data volume"); `wordpress/latest/php8.2/apache/Dockerfile` L168 (`VOLUME /var/www/html`); `docs/wordpress/compose.yaml` L13-14 |
| mysql listens on port 3306 | `mysql/Dockerfile.oracle` L137 (`EXPOSE 3306 33060`); MySQL default port |
| `MYSQL_ROOT_PASSWORD` required, sets the `root` password | tutorial L117-118 (prose); `docs/mysql/content.md` L95-97 |
| `MYSQL_DATABASE` optional, creates a database on first start | upstream image doc only: `docs/mysql/content.md` L99-101, L137 (https://hub.docker.com/_/mysql) |
| `MYSQL_USER` / `MYSQL_PASSWORD` create a user with access to `MYSQL_DATABASE`; both required | upstream image doc only: `docs/mysql/content.md` L103-107 |
| Variables read on first start only | `docs/mysql/content.md` L91, L137 |
| `/var/lib/mysql` must be persistent | tutorial L65, L116-117 ("mounts the PersistentVolume at /var/lib/mysql"); `docs/mysql/content.md` L159; `mysql/Dockerfile.oracle` L132 (`VOLUME /var/lib/mysql`) |
| Database password supplied from a Kubernetes Secret | tutorial L97-103 (Secret stores sensitive data such as a password; create it with a generator), L117-118 ("sets the database password from the Secret"), L124-125 ("sets the database password from the Secret kustomize generated") |
| wordpress depends on mysql | tutorial L123-124 ("WordPress will access the database by Service") |
| WordPress site reachable from outside with a browser | tutorial L227-243 (get the WordPress URL, "load the page in your browser") |
| mysql used only by wordpress, internal only | tutorial L122-125 (only WordPress accesses the database); L227-243 (only the WordPress site is opened externally). Judgement: the prose does not state "internal only" explicitly |

## smoke.json sources
| Check | Source |
|---|---|
| `GET /wp-admin/install.php`, title "WordPress › Installation" | `WordPress/wp-admin/install.php` L73; tutorial L241 ("You should see the WordPress set up page") |
| `POST /wp-admin/install.php?step=2` with `weblog_title`, `user_name`, `admin_password`, `admin_password2`, `admin_email`, `blog_public`; response "Success!" | `WordPress/wp-admin/install.php` L111, L375-426 |
| `wp_options` table created in MySQL | WordPress default table prefix `wp_`; `docs/wordpress/content.md` L21 (`WORDPRESS_TABLE_PREFIX`). The check matches any `*options` table outside the system schemas |

## Excluded facts (appear only in the human manifests or embedded YAML)
- Image tag `6.2.1-apache` (kept as the unavoidable image reference, see above).
- Service name `wordpress-mysql` as the value of `WORDPRESS_DB_HOST`. The prose (tutorial L123-124) says the variable holds "the name of the MySQL Service defined above" without naming it; the name is visible only in the embedded YAML. The image default `mysql` is the only name fixed outside the manifest, so the spec leaves the value to the generator.
- `MYSQL_DATABASE=wordpress`, `MYSQL_USER=wordpress`, `WORDPRESS_DB_USER=wordpress`, and reuse of one Secret key for both `MYSQL_ROOT_PASSWORD` and `MYSQL_PASSWORD`.
- Secret name `mysql-pass` and key `password` (tutorial L108-110 is quoted kustomization YAML, not prose); password placeholder `YOUR_PASSWORD`.
- Service type LoadBalancer (also shown in tutorial output L219-220), headless MySQL Service (`clusterIP: None`), PVC names and size 20Gi (also in tutorial output L188-190), access mode ReadWriteOnce, `strategy: Recreate`, single replica (tutorial L26 mentions "single instance" Pods as a warning, not a requirement), labels `app`/`tier`.
