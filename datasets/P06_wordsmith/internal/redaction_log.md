# Redaction log: P06_wordsmith
Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.

## README.md -> docs_bundle/README.md
- **Kubernetes-headed section**: `You can deploy the same app to Kubernetes using the [Kustomize configuration](./kustomization.yaml). It will define all of the necessary Deployment and Service objects and a ConfigMap to provide the d`

## docker-compose.yml -> docs_bundle/docker-compose.yml
- **excluded fact: api replica count (also in README, excluded per the no-replica-count rule)**: `replicas: 5`

## api/Dockerfile -> docs_bundle/api.Dockerfile
- no redactions

## web/Dockerfile -> docs_bundle/web.Dockerfile
- no redactions

## db/words.sql -> docs_bundle/db.words.sql
- no redactions. Added 2026-11-26: docker-compose.yml mounts `./db` as the postgres init directory and the stock
  `postgres` image has no seed of its own, so the script is part of what the compose setup deploys (as n8n's
  `init-data.sh`, included from the start). It was missing from the first bundle although fact_sheet.md and
  provenance.md already cited it (design doc 4.4: every fact must trace to a file present in docs_bundle/).
  All P06 generations made with the first bundle were archived and re-run.
