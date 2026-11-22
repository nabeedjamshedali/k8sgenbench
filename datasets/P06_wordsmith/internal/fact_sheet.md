# Wordsmith

## Purpose
A demo application that builds random sentences. A Go web application serves a single page; the page asks the web application for random nouns, verbs and adjectives, the web application forwards these requests to a Java REST API, and the API reads a random word from a PostgreSQL database.

## Components

| Component | Image | Role |
|---|---|---|
| web | `dockersamples/wordsmith-web` | Go web application that serves the static page and forwards word requests to the api |
| api | `dockersamples/wordsmith-api` | Java REST API that returns a random word read from the database |
| db | `postgres:10.0-alpine` | PostgreSQL database that stores the words |

## Component details

### web
- Listens on HTTP port 80.
- Serves the static web page at `/`.
- Forwards every request under `/words/` to the api at hostname `api` on port 8080, with the `/words` prefix removed (for example `/words/noun` is sent to `/noun`). The hostname and port are fixed in the application code. The web application resolves the hostname `api` itself and connects directly to one of the returned addresses on port 8080.

### api
- Listens on HTTP port 8080.
- Endpoints: `GET /noun`, `GET /verb` and `GET /adjective` each return a random word from the database as JSON, for example `{"word":"whale"}`.
- Connects to PostgreSQL at hostname `db` on port 5432, database `postgres`, user `postgres`, with an empty password. These connection settings are fixed in the application code.

### db
- Listens on port 5432.
- Must accept connections from the api for user `postgres` without a password. The `postgres:10.0-alpine` image does this when `POSTGRES_PASSWORD` is not set.
- On first start the database must be initialised with the SQL script in Appendix A (tables `nouns`, `verbs`, `adjectives` and their words). The `postgres` image runs `*.sql` files placed in `/docker-entrypoint-initdb.d` when it initialises an empty data directory.
- The words are static seed data that is recreated on initialisation; the database does not need persistent storage.

## Dependencies
- web depends on api.
- api depends on db.

## External access
- The web page (port 80) must be reachable from outside the cluster.
- api and db are internal only.

## Health endpoints
- None of the components exposes a dedicated health endpoint.

## Appendix A: database initialisation script (`words.sql`)

```sql
CREATE TABLE nouns (word TEXT NOT NULL);
CREATE TABLE verbs (word TEXT NOT NULL);
CREATE TABLE adjectives (word TEXT NOT NULL);

INSERT INTO nouns(word) VALUES
  ('cloud'),
  ('elephant'),
  ('gø language'),
  ('laptøp'),
  ('cøntainer'),
  ('micrø-service'),
  ('turtle'),
  ('whale'),
  ('gøpher'),
  ('møby døck'),
  ('server'),
  ('bicycle'),
  ('viking'),
  ('mermaid'),
  ('fjørd'),
  ('legø'),
  ('flødebolle'),
  ('smørrebrød');

INSERT INTO verbs(word) VALUES
  ('will drink'),
  ('smashes'),
  ('smøkes'),
  ('eats'),
  ('walks tøwards'),
  ('løves'),
  ('helps'),
  ('pushes'),
  ('debugs'),
  ('invites'),
  ('hides'),
  ('will ship');

INSERT INTO adjectives(word) VALUES
  ('the exquisite'),
  ('a pink'),
  ('the røtten'),
  ('a red'),
  ('the serverless'),
  ('a brøken'),
  ('a shiny'),
  ('the pretty'),
  ('the impressive'),
  ('an awesøme'),
  ('the famøus'),
  ('a gigantic'),
  ('the gløriøus'),
  ('the nørdic'),
  ('the welcøming'),
  ('the deliciøus');
```
