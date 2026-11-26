# P06 Wordsmith, first docs bundle (archived 2026-11-26, not analysed)

All model results for P06 made with the first docs_bundle, which lacked db/words.sql (the seed script the Compose
file mounts into the stock postgres image). The script was added to docs_bundle/ as db.words.sql (see
datasets/P06_wordsmith/internal/redaction_log.md) and P06 was generated and evaluated again for every model and
condition. Matching generations: generation/outputs/_P06_bundle_v1/, Claude relay prompts:
generation/relay/_P06_bundle_v1/. The human P06 result does not depend on the bundle and stays in results/.
