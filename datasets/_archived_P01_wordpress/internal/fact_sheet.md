# WordPress with MySQL

## Purpose
A WordPress web site backed by a MySQL database. WordPress is a PHP blogging tool and content management system; it stores its content in MySQL and its files (themes, plugins, uploads) on local disk. Both the database data and the WordPress files must survive restarts.

## Components

| Component | Image | Role |
|---|---|---|
| wordpress | `wordpress:6.2.1-apache` | WordPress served by Apache httpd |
| mysql | `mysql:8.0` | MySQL database that stores the WordPress data |

## Component details

### wordpress
- Listens on HTTP port 80.
- Environment variables (read by the image's `wp-config.php`):
  - `WORDPRESS_DB_HOST`: address of the MySQL server, as `host` or `host:port`. Required; the image default `mysql` only works if the database is reachable under that name.
  - `WORDPRESS_DB_USER`: MySQL user name. Required.
  - `WORDPRESS_DB_PASSWORD`: password of that MySQL user. Required.
  - `WORDPRESS_DB_NAME`: name of the database. Optional, default `wordpress`.
- The database named by `WORDPRESS_DB_NAME` must already exist on the MySQL server; the WordPress container does not create it.
- `WORDPRESS_DB_USER` and `WORDPRESS_DB_PASSWORD` must match an account on the MySQL server that has access to that database.
- Persistence: `/var/www/html` holds the WordPress installation, themes, plugins and uploaded files and must be stored on a persistent volume.

### mysql
- Listens on port 3306.
- Environment variables (read by the image's entrypoint on first start):
  - `MYSQL_ROOT_PASSWORD`: password of the MySQL `root` account. Required.
  - `MYSQL_DATABASE`: name of a database to create on first start. Optional.
  - `MYSQL_USER` and `MYSQL_PASSWORD`: create a user with full access to the database named by `MYSQL_DATABASE`. Optional; both must be set for the user to be created.
- Persistence: the data directory `/var/lib/mysql` must be stored on a persistent volume.

## Secrets
- The database password is sensitive and must be supplied to both components from a Kubernetes Secret, not written as a plain value in the workload definitions.

## Dependencies
- wordpress depends on mysql.

## External access
- The WordPress web site (port 80) must be reachable from outside the cluster with a browser.
- mysql is used only by wordpress and is internal only.
